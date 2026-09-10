from datetime import datetime

from extensions import db


class Visit(db.Model):
    """Tracks who visits the application and which pages, for the owner's info."""
    __tablename__ = 'visits'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # nullable: anonymous visitors
    path = db.Column(db.String(255), nullable=False)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
