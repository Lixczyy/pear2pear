import os
import uuid
from datetime import timedelta
from werkzeug.utils import secure_filename

from dotenv import load_dotenv
from flask import Flask, current_app, redirect, render_template, request, url_for, flash
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import BooleanField, IntegerField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional, ValidationError

from models import Friendship, Message, Notification, User, db

load_dotenv()

csrf    = CSRFProtect()
socketio = SocketIO()


def create_app() -> Flask:
    app = Flask(__name__)

    app.config["SECRET_KEY"]                     = os.environ["SECRET_KEY"]
    app.config["SQLALCHEMY_DATABASE_URI"]        = os.environ["DATABASE_URL"]
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["REMEMBER_COOKIE_DURATION"]       = timedelta(days=30)
    app.config["REMEMBER_COOKIE_HTTPONLY"]       = True
    app.config["REMEMBER_COOKIE_SAMESITE"]       = "Lax"

    UPLOAD_FOLDER = os.path.join(app.root_path, "static", "avatars")
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.config["UPLOAD_FOLDER"]       = UPLOAD_FOLDER
    app.config["MAX_CONTENT_LENGTH"]  = 4 * 1024 * 1024   # 4 MB (avatars only)

    db.init_app(app)
    csrf.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*", async_mode="eventlet")

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
    register_socket_events(app)
    return app


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------

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
    username       = StringField("Gebruikersnaam", validators=[DataRequired(), Length(min=3, max=30)])
    email          = StringField("E-mail",         validators=[DataRequired(), Email()])
    age            = IntegerField("Leeftijd",       validators=[Optional(), NumberRange(min=1, max=120)])
    location       = StringField("Locatie",         validators=[Optional(), Length(max=100)])
    is_public      = BooleanField("Profiel openbaar")
    friends_public = BooleanField("Vriendenlijst openbaar")
    submit         = SubmitField("Opslaan")

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


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def add_notification(user_id: int, body: str, link: str = None):
    db.session.add(Notification(user_id=user_id, body=body, link=link))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def register_routes(app: Flask) -> None:

    @app.route("/")
    @login_required
    def index():
        # Pass all users for recipient search (connections first, then rest)
        friends   = current_user.friends()
        all_users = User.query.filter(User.id != current_user.id).order_by(User.username).all()
        return render_template("index.html", friends=friends, all_users=all_users)

    # ── Auth ────────────────────────────────────────────────────────────────

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()
            if user and user.check_password(form.password.data):
                user.touch_login()
                db.session.commit()
                login_user(user, remember=form.remember.data)
                return redirect(url_for("index"))
            flash("Ongeldige gebruikersnaam of wachtwoord.", "error")
        return render_template("login.html", form=form)

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        form = RegisterForm()
        if form.validate_on_submit():
            user = User(username=form.username.data, email=form.email.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            login_user(user, remember=False)
            flash("Account aangemaakt! Welkom 🎉", "success")
            return redirect(url_for("index"))
        return render_template("register.html", form=form)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return render_template("logout.html")

    # ── Account ─────────────────────────────────────────────────────────────

    @app.route("/account", methods=["GET", "POST"])
    @login_required
    def account():
        form = EditProfileForm(
            current_user_id=current_user.id,
            data={
                "username":       current_user.username,
                "email":          current_user.email,
                "age":            current_user.age,
                "location":       current_user.location,
                "is_public":      current_user.is_public,
                "friends_public": current_user.friends_public,
            }
        )
        if form.validate_on_submit():
            current_user.username       = form.username.data
            current_user.email          = form.email.data
            current_user.age            = form.age.data
            current_user.location       = form.location.data
            current_user.is_public      = form.is_public.data
            current_user.friends_public = form.friends_public.data
            db.session.commit()
            flash("Profiel bijgewerkt!", "success")
            return redirect(url_for("account"))
        return render_template("account.html", user=current_user, form=form)

    @app.route("/account/avatar", methods=["POST"])
    @login_required
    @csrf.exempt
    def upload_avatar():
        file = request.files.get("avatar")
        if file and file.filename:
            ext = os.path.splitext(secure_filename(file.filename))[1].lower()
            if ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
                flash("Alleen afbeeldingen toegestaan (jpg, png, gif, webp).", "error")
                return redirect(url_for("account"))
            filename = f"{current_user.id}_{uuid.uuid4().hex}{ext}"
            path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            if current_user.avatar:
                old_path = os.path.join(current_app.config["UPLOAD_FOLDER"], current_user.avatar)
                if os.path.exists(old_path):
                    os.remove(old_path)
            file.save(path)
            current_user.avatar = filename
            db.session.commit()
        return redirect(url_for("account"))

    # ── Connecties ───────────────────────────────────────────────────────────

    @app.route("/connecties")
    @login_required
    def connecties():
        all_users = User.query.order_by(User.username).all()
        friends   = current_user.friends()
        pending   = current_user.pending_received()
        return render_template("connecties.html", users=all_users, friends=friends, pending=pending)

    @app.route("/profiles")
    @login_required
    def profiles():
        return redirect(url_for("connecties"))

    @app.route("/profile/<int:user_id>")
    @login_required
    def profile(user_id):
        user = db.get_or_404(User, user_id)
        if user.id == current_user.id:
            return redirect(url_for("account"))
        status = current_user.friendship_status_with(user.id)
        mutual_friends = []
        fof = []
        if user.friends_public:
            user_friends   = user.friends()
            my_friend_ids  = {f.id for f in current_user.friends()}
            mutual_friends = [f for f in user_friends if f.id in my_friend_ids]
            fof            = [f for f in user_friends if f.id not in my_friend_ids and f.id != current_user.id]
        return render_template("profile.html", user=user, status=status,
                               mutual_friends=mutual_friends, fof=fof)

    # ── Friend actions ───────────────────────────────────────────────────────

    @app.route("/friend/add/<int:user_id>", methods=["POST"])
    @login_required
    @csrf.exempt
    def friend_add(user_id):
        if user_id != current_user.id:
            existing = Friendship.query.filter_by(from_id=current_user.id, to_id=user_id).first()
            if not existing:
                db.session.add(Friendship(from_id=current_user.id, to_id=user_id))
                # No notification here — the pending badge on Connecties already shows this
                db.session.commit()
        return redirect(request.referrer or url_for("connecties"))

    @app.route("/friend/accept/<int:user_id>", methods=["POST"])
    @login_required
    @csrf.exempt
    def friend_accept(user_id):
        req = Friendship.query.filter_by(from_id=user_id, to_id=current_user.id, status="pending").first()
        if req:
            req.status = "accepted"
            add_notification(user_id,
                f"✅ {current_user.username} heeft je verzoek geaccepteerd. Jullie zijn nu connecties!",
                link=f"/profile/{current_user.id}")
            add_notification(current_user.id,
                f"✅ Jij en {db.session.get(User, user_id).username} zijn nu connecties!",
                link=f"/profile/{user_id}")
            db.session.commit()
        return redirect(request.referrer or url_for("connecties"))

    @app.route("/friend/decline/<int:user_id>", methods=["POST"])
    @login_required
    @csrf.exempt
    def friend_decline(user_id):
        req = Friendship.query.filter_by(from_id=user_id, to_id=current_user.id, status="pending").first()
        if req:
            db.session.delete(req)
            db.session.commit()
        return redirect(request.referrer or url_for("connecties"))

    @app.route("/friend/remove/<int:user_id>", methods=["POST"])
    @login_required
    @csrf.exempt
    def friend_remove(user_id):
        f = Friendship.query.filter(
            ((Friendship.from_id == current_user.id) & (Friendship.to_id == user_id)) |
            ((Friendship.from_id == user_id) & (Friendship.to_id == current_user.id))
        ).first()
        if f:
            db.session.delete(f)
            db.session.commit()
        return redirect(request.referrer or url_for("connecties"))

    @app.route("/friends")
    @login_required
    def friends():
        return redirect(url_for("connecties"))

    # ── Messages + notifications ──────────────────────────────────────────────

    @app.route("/messages")
    @login_required
    def messages():
        notifs = current_user.notifications.all()
        for n in notifs:
            if not n.read:
                n.read = True
        db.session.commit()

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

        return render_template("messages.html", notifs=notifs, conversations=list(conversations.values()))

    @app.route("/messages/<int:partner_id>", methods=["GET", "POST"])
    @login_required
    @csrf.exempt
    def conversation(partner_id):
        partner = db.get_or_404(User, partner_id)
        if request.method == "POST":
            body = request.form.get("body", "").strip()
            if body:
                db.session.add(Message(sender_id=current_user.id, receiver_id=partner_id, body=body))
                db.session.commit()
                # Push live update to receiver
                socketio.emit("new_message", {
                    "from_user_id": current_user.id,
                    "from_username": current_user.username,
                    "body": body,
                    "partner_id": current_user.id,
                }, to=f"user_{partner_id}")
                # Also push to sender's other tabs
                socketio.emit("new_message_sent", {
                    "body": body,
                    "partner_id": partner_id,
                }, to=f"user_{current_user.id}")
            return redirect(url_for("conversation", partner_id=partner_id))
        Message.query.filter_by(sender_id=partner_id, receiver_id=current_user.id, read=False).update({"read": True})
        db.session.commit()
        thread = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == partner_id)) |
            ((Message.sender_id == partner_id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.created_at.asc()).all()
        return render_template("conversation.html", partner=partner, thread=thread)

    @app.route("/messages/send/<int:user_id>", methods=["POST"])
    @login_required
    @csrf.exempt
    def send_message_from_profile(user_id):
        body = request.form.get("body", "").strip()
        if body:
            db.session.add(Message(sender_id=current_user.id, receiver_id=user_id, body=body))
            db.session.commit()
            socketio.emit("new_message", {
                "from_user_id": current_user.id,
                "from_username": current_user.username,
                "body": body,
                "partner_id": current_user.id,
            }, to=f"user_{user_id}")
        return redirect(url_for("conversation", partner_id=user_id))

    # ── File transfer API ─────────────────────────────────────────────────────

    @app.route("/api/users/search")
    @login_required
    def api_user_search():
        """Return JSON list of users matching query, for recipient search."""
        from flask import jsonify
        q = request.args.get("q", "").strip().lower()
        users = User.query.filter(
            User.id != current_user.id,
            User.username.ilike(f"%{q}%")
        ).limit(10).all()
        return jsonify([{"id": u.id, "username": u.username,
                         "avatar": u.avatar, "location": u.location} for u in users])


# ---------------------------------------------------------------------------
# WebRTC Signaling via SocketIO
# ---------------------------------------------------------------------------
# Room naming: "transfer_{min_id}_{max_id}" ensures both users join the same room.
# Signal flow:
#   sender  → offer       → server → receiver
#   receiver → answer     → server → sender
#   both    ↔ ice-candidate → server → other peer
# ---------------------------------------------------------------------------

# Maps user_id → socket sid (most recent connection)
user_sockets: dict[int, str] = {}


def register_socket_events(app: Flask) -> None:

    @socketio.on("connect")
    def on_connect():
        if current_user.is_authenticated:
            user_sockets[current_user.id] = request.sid
            # Join personal room so we can push events to this user anytime
            join_room(f"user_{current_user.id}")

    @socketio.on("disconnect")
    def on_disconnect():
        if current_user.is_authenticated:
            user_sockets.pop(current_user.id, None)

    # ── Sender initiates transfer ─────────────────────────────────────────────

    @socketio.on("transfer_offer")
    def on_transfer_offer(data):
        """
        data: { to_user_id, offer (SDP), file_meta: {name, size, type, encrypted} }
        """
        if not current_user.is_authenticated:
            return
        to_id = data.get("to_user_id")
        emit("transfer_incoming", {
            "from_user_id":   current_user.id,
            "from_username":  current_user.username,
            "from_avatar":    current_user.avatar,
            "offer":          data["offer"],
            "file_meta":      data["file_meta"],
        }, to=f"user_{to_id}")

    # ── Receiver accepts ─────────────────────────────────────────────────────

    @socketio.on("transfer_answer")
    def on_transfer_answer(data):
        """data: { to_user_id, answer (SDP) }"""
        if not current_user.is_authenticated:
            return
        emit("transfer_answer", {"answer": data["answer"]},
             to=f"user_{data['to_user_id']}")

    @socketio.on("transfer_decline")
    def on_transfer_decline(data):
        if not current_user.is_authenticated:
            return
        emit("transfer_declined", {"by": current_user.username},
             to=f"user_{data['to_user_id']}")

    # ── ICE candidates (both directions) ────────────────────────────────────

    @socketio.on("ice_candidate")
    def on_ice_candidate(data):
        """data: { to_user_id, candidate }"""
        if not current_user.is_authenticated:
            return
        emit("ice_candidate", {
            "candidate":   data["candidate"],
            "from_user_id": current_user.id,
        }, to=f"user_{data['to_user_id']}")

    # ── Transfer complete notification ───────────────────────────────────────

    @socketio.on("transfer_complete")
    def on_transfer_complete(data):
        """Sender tells server transfer is done; server notifies receiver."""
        if not current_user.is_authenticated:
            return
        emit("transfer_done", {
            "from_username": current_user.username,
            "file_name":     data.get("file_name"),
        }, to=f"user_{data['to_user_id']}")


# ---------------------------------------------------------------------------
app = create_app()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
