from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False)
    username = db.Column(db.String(100), nullable=True)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    is_banned = db.Column(db.Boolean, default=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    total_downloads = db.Column(db.Integer, default=0)
    downloads = db.relationship('Download', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.telegram_id}>'

class Download(db.Model):
    __tablename__ = 'downloads'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    url = db.Column(db.String(2048), nullable=False)
    platform = db.Column(db.String(50), nullable=True)
    title = db.Column(db.String(500), nullable=True)
    file_type = db.Column(db.String(20), nullable=True)  # video, audio, round
    status = db.Column(db.String(20), default='pending')  # pending, success, failed
    error_msg = db.Column(db.String(1000), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Download {self.id}>'

class BotStats(db.Model):
    __tablename__ = 'bot_stats'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=datetime.utcnow().date, unique=True)
    total_requests = db.Column(db.Integer, default=0)
    successful_downloads = db.Column(db.Integer, default=0)
    failed_downloads = db.Column(db.Integer, default=0)
    new_users = db.Column(db.Integer, default=0)

class AdminUser(db.Model):
    __tablename__ = 'admin_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BroadcastMessage(db.Model):
    __tablename__ = 'broadcast_messages'
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    sent_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')
