"""小纸条：情侣之间的悄悄话，可定时「未来寄出」。"""
from app.extensions import db
from app.models.mixins import TimestampMixin


class Note(TimestampMixin, db.Model):
    __tablename__ = "notes"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    content = db.Column(db.Text, nullable=False)
    mood = db.Column(db.String(32), default="")
    # 定时信：到点才可见
    deliver_at = db.Column(db.DateTime, nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)
    is_public = db.Column(db.Boolean, default=False, nullable=False)

    sender = db.relationship("User", foreign_keys=[sender_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Note #{self.id}>"
