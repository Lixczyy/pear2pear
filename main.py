import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, url_for
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

from models import User, db

load_dotenv()  # reads .env file into os.environ

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> Flask:
    app = Flask(__name__)

    # -- Config --------------------------------------------------------------
    app.config["SECRET_KEY"]                     = os.environ["SECRET_KEY"]
    app.config["SQLALCHEMY_DATABASE_URI"]        = os.environ["DATABASE_URL"]
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["REMEMBER_COOKIE_DURATION"]       = timedelta(days=30)
    app.config["REMEMBER_COOKIE_HTTPONLY"]       = True
    app.config["REMEMBER_COOKIE_SAMESITE"]       = "Lax"

    # -- Extensions ----------------------------------------------------------
    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view             = "login"
    login_manager.login_message          = "Log in om deze pagina te bekijken."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        return db.session.get(User, int(user_id))

    # -- Create tables (run once on startup) ---------------------------------
    with app.app_context():
        db.create_all()

    # -- Routes --------------------------------------------------------------
    register_routes(app)

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
    username = StringField(
        "Gebruikersnaam",
        validators=[DataRequired(), Length(min=3, max=30)],
    )
    email = StringField(
        "E-mail",
        validators=[DataRequired(), Email()],
    )
    password = PasswordField(
        "Wachtwoord",
        validators=[DataRequired(), Length(min=6)],
    )
    confirm = PasswordField(
        "Herhaal wachtwoord",
        validators=[DataRequired(), EqualTo("password", message="Wachtwoorden komen niet overeen.")],
    )
    submit = SubmitField("Registreren")

    # Inline DB-validaties
    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError("Gebruikersnaam is al in gebruik.")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError("E-mailadres is al geregistreerd.")


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_routes(app: Flask) -> None:

    @app.route("/")
    def index():
        return render_template("index.html")

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

    @app.route("/account")
    @login_required
    def account():
        return render_template("account.html", user=current_user)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return render_template("logout.html")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
