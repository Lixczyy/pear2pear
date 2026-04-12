from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Friendship(db.Model):
    __tablename__ = "friendships"

    id         = db.Column(db.Integer, primary_key=True)
    from_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    to_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status     = db.Column(db.String(10), default="pending", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("from_id", "to_id"),)


class Notification(db.Model):
    """Persistent system notifications shown in the messages page."""
    __tablename__ = "notifications"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body       = db.Column(db.String(300), nullable=False)
    link       = db.Column(db.String(200), nullable=True)   # optional click-through
    read       = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Message(db.Model):
    __tablename__ = "messages"

    id          = db.Column(db.Integer, primary_key=True)
    sender_id   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body        = db.Column(db.Text, nullable=False)
    read        = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    sender   = db.relationship("User", foreign_keys=[sender_id],   backref="sent_messages")
    receiver = db.relationship("User", foreign_keys=[receiver_id], backref="received_messages")


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(30),  unique=True, nullable=False, index=True)
    email         = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    age            = db.Column(db.Integer,     nullable=True)
    avatar         = db.Column(db.String(200),   nullable=True)
    location       = db.Column(db.String(100), nullable=True)
    is_public      = db.Column(db.Boolean, default=True,  nullable=False)
    friends_public = db.Column(db.Boolean, default=False, nullable=False)

    sent_requests     = db.relationship("Friendship", foreign_keys=[Friendship.from_id], backref="from_user", lazy="dynamic")
    received_requests = db.relationship("Friendship", foreign_keys=[Friendship.to_id],   backref="to_user",   lazy="dynamic")
    notifications     = db.relationship("Notification", foreign_keys=[Notification.user_id], backref="owner", lazy="dynamic", order_by=Notification.created_at.desc())

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def touch_login(self) -> None:
        self.last_login = datetime.utcnow()

    def friendship_status_with(self, other_id: int):
        sent = Friendship.query.filter_by(from_id=self.id, to_id=other_id).first()
        if sent:
            return "friends" if sent.status == "accepted" else "pending_sent"
        received = Friendship.query.filter_by(from_id=other_id, to_id=self.id).first()
        if received:
            return "friends" if received.status == "accepted" else "pending_received"
        return None

    def friends(self):
        accepted_sent     = Friendship.query.filter_by(from_id=self.id, status="accepted").all()
        accepted_received = Friendship.query.filter_by(to_id=self.id,   status="accepted").all()
        friend_ids = [f.to_id for f in accepted_sent] + [f.from_id for f in accepted_received]
        return User.query.filter(User.id.in_(friend_ids)).all()

    def pending_received(self):
        reqs = Friendship.query.filter_by(to_id=self.id, status="pending").all()
        return User.query.filter(User.id.in_([r.from_id for r in reqs])).all()

    def unread_message_count(self):
        return Message.query.filter_by(receiver_id=self.id, read=False).count()

    def unread_notification_count(self):
        return Notification.query.filter_by(user_id=self.id, read=False).count()

    def total_inbox_count(self):
        """Badge number shown on Berichten nav item."""
        return self.unread_message_count() + self.unread_notification_count()

    def __repr__(self) -> str:
        return f"<User {self.username!r}>"
