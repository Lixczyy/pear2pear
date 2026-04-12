import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, PasswordField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional, ValidationError

from models import Friendship, Message, User, db

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__)

    app.config["SECRET_KEY"]                     = os.environ["SECRET_KEY"]
    app.config["SQLALCHEMY_DATABASE_URI"]        = os.environ["DATABASE_URL"]
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["REMEMBER_COOKIE_DURATION"]       = timedelta(days=30)
    app.config["REMEMBER_COOKIE_HTTPONLY"]       = True
    app.config["REMEMBER_COOKIE_SAMESITE"]       = "Lax"

    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view             = "login"
    login_manager.login_message          = "Log in om deze pagina te bekijken."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    with app.app_context():
        db.create_all()

    register_routes(app)
    return app


# Forms :)

class LoginForm(FlaskForm):
    username = StringField("Gebruikersnaam", validators=[DataRequired()])
    password = PasswordField("Wachtwoord",   validators=[DataRequired()])
    remember = BooleanField("Onthoud mij")
    submit   = SubmitField("Inloggen")


class RegisterForm(FlaskForm):
    username = StringField("Gebruikersnaam", validators=[DataRequired(), Length(min=3, max=30)])
    email    = StringField("E-mail",         validators=[DataRequired(), Email()])
    password = PasswordField("Wachtwoord",   validators=[DataRequired(), Length(min=6)])
    confirm  = PasswordField("Herhaal wachtwoord", validators=[DataRequired(), EqualTo("password", message="Wachtwoorden komen niet overeen.")])
    submit   = SubmitField("Registreren")

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError("Gebruikersnaam is al in gebruik.")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError("E-mailadres is al geregistreerd.")


class EditProfileForm(FlaskForm):
    username  = StringField("Gebruikersnaam", validators=[DataRequired(), Length(min=3, max=30)])
    email     = StringField("E-mail",         validators=[DataRequired(), Email()])
    age       = IntegerField("Leeftijd",       validators=[Optional(), NumberRange(min=1, max=120)])
    location  = StringField("Locatie",         validators=[Optional(), Length(max=100)])
    is_public = BooleanField("Profiel openbaar")
    submit    = SubmitField("Opslaan")

    def __init__(self, current_user_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_user_id = current_user_id

    def validate_username(self, field):
        user = User.query.filter_by(username=field.data).first()
        if user and user.id != self._current_user_id:
            raise ValidationError("Gebruikersnaam is al in gebruik.")

    def validate_email(self, field):
        user = User.query.filter_by(email=field.data).first()
        if user and user.id != self._current_user_id:
            raise ValidationError("E-mailadres is al geregistreerd.")


class MessageForm(FlaskForm):
    body   = TextAreaField("Bericht", validators=[DataRequired(), Length(max=1000)])
    submit = SubmitField("Versturen")


# hier staan de routes :)

def register_routes(app: Flask) -> None:

    @app.route("/")
    def index():
        return render_template("index.html")

    # authenticate :)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("account"))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()
            if user and user.check_password(form.password.data):
                user.touch_login()
                db.session.commit()
                login_user(user, remember=form.remember.data)
                return redirect(url_for("account"))
            flash("Ongeldige gebruikersnaam of wachtwoord.", "error")
        return render_template("login.html", form=form)

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("account"))
        form = RegisterForm()
        if form.validate_on_submit():
            user = User(username=form.username.data, email=form.email.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            login_user(user, remember=False)
            flash("Account aangemaakt! Welkom 🎉", "success")
            return redirect(url_for("account"))
        return render_template("register.html", form=form)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return render_template("logout.html")

    # account pagina :)

    @app.route("/account", methods=["GET", "POST"])
    @login_required
    def account():
        form = EditProfileForm(
            current_user_id=current_user.id,
            data={
                "username":  current_user.username,
                "email":     current_user.email,
                "age":       current_user.age,
                "location":  current_user.location,
                "is_public": current_user.is_public,
            }
        )
        if form.validate_on_submit():
            current_user.username  = form.username.data
            current_user.email     = form.email.data
            current_user.age       = form.age.data
            current_user.location  = form.location.data
            current_user.is_public = form.is_public.data
            db.session.commit()
            flash("Profiel bijgewerkt!", "success")
            return redirect(url_for("account"))
        return render_template("account.html", user=current_user, form=form)

    # profiles pagina :)

    @app.route("/profiles")
    @login_required
    def profiles():
        all_users = User.query.order_by(User.username).all()
        return render_template("profiles.html", users=all_users)

    # eigen profiel pagina :)

    @app.route("/profile/<int:user_id>")
    @login_required
    def profile(user_id):
        user = db.get_or_404(User, user_id)
        if user.id == current_user.id:
            return redirect(url_for("account"))
        status = current_user.friendship_status_with(user.id)
        msg_form = MessageForm()
        return render_template("profile.html", user=user, status=status, msg_form=msg_form)

    # friendship routes :)

    @app.route("/friend/add/<int:user_id>", methods=["POST"])
    @login_required
    def friend_add(user_id):
        if user_id == current_user.id:
            return redirect(url_for("profiles"))
        existing = Friendship.query.filter_by(from_id=current_user.id, to_id=user_id).first()
        if not existing:
            db.session.add(Friendship(from_id=current_user.id, to_id=user_id))
            db.session.commit()
            flash("Vriendschapsverzoek verzonden!", "success")
        return redirect(request.referrer or url_for("profiles"))

    @app.route("/friend/accept/<int:user_id>", methods=["POST"])
    @login_required
    def friend_accept(user_id):
        req = Friendship.query.filter_by(from_id=user_id, to_id=current_user.id, status="pending").first_or_404()
        req.status = "accepted"
        db.session.commit()
        flash("Vriendschapsverzoek geaccepteerd!", "success")
        return redirect(request.referrer or url_for("friends"))

    @app.route("/friend/decline/<int:user_id>", methods=["POST"])
    @login_required
    def friend_decline(user_id):
        req = Friendship.query.filter_by(from_id=user_id, to_id=current_user.id, status="pending").first_or_404()
        db.session.delete(req)
        db.session.commit()
        flash("Verzoek geweigerd.", "info")
        return redirect(request.referrer or url_for("friends"))

    @app.route("/friend/remove/<int:user_id>", methods=["POST"])
    @login_required
    def friend_remove(user_id):
        f = Friendship.query.filter(
            ((Friendship.from_id == current_user.id) & (Friendship.to_id == user_id)) |
            ((Friendship.from_id == user_id) & (Friendship.to_id == current_user.id))
        ).first()
        if f:
            db.session.delete(f)
            db.session.commit()
        return redirect(request.referrer or url_for("friends"))

    # friends pagina :)

    @app.route("/friends")
    @login_required
    def friends():
        friend_list = current_user.friends()
        pending     = current_user.pending_received()
        return render_template("friends.html", friends=friend_list, pending=pending)

    # messages pagina :)

    @app.route("/messages")
    @login_required
    def messages():
        # Get unique conversation partners
        all_msgs = Message.query.filter(
            (Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id)
        ).order_by(Message.created_at.desc()).all()

        conversations = {}
        for msg in all_msgs:
            partner_id = msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
            if partner_id not in conversations:
                conversations[partner_id] = {
                    "user":   db.session.get(User, partner_id),
                    "latest": msg,
                    "unread": 0,
                }
            if msg.receiver_id == current_user.id and not msg.read:
                conversations[partner_id]["unread"] += 1

        return render_template("messages.html", conversations=conversations.values())

    @app.route("/messages/<int:partner_id>", methods=["GET", "POST"])
    @login_required
    def conversation(partner_id):
        partner  = db.get_or_404(User, partner_id)
        msg_form = MessageForm()

        if msg_form.validate_on_submit():
            msg = Message(sender_id=current_user.id, receiver_id=partner_id, body=msg_form.body.data)
            db.session.add(msg)
            db.session.commit()
            return redirect(url_for("conversation", partner_id=partner_id))

        # Mark received messages as read
        Message.query.filter_by(sender_id=partner_id, receiver_id=current_user.id, read=False).update({"read": True})
        db.session.commit()

        thread = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == partner_id)) |
            ((Message.sender_id == partner_id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.created_at.asc()).all()

        return render_template("conversation.html", partner=partner, thread=thread, msg_form=msg_form)

    @app.route("/messages/send/<int:user_id>", methods=["POST"])
    @login_required
    def send_message_from_profile(user_id):
        form = MessageForm()
        if form.validate_on_submit():
            msg = Message(sender_id=current_user.id, receiver_id=user_id, body=form.body.data)
            db.session.add(msg)
            db.session.commit()
            flash("Bericht verzonden!", "success")
        return redirect(url_for("conversation", partner_id=user_id))


app = create_app()
# debug nog uitzetten :)
if __name__ == "__main__":
    app.run(debug=True)
