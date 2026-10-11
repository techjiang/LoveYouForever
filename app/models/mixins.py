"""复用的小工具。"""
from datetime import datetime, timezone

from app.extensions import db


def utcnow() -> datetime:
    """统一的「现在」。

    存进数据库时去掉时区信息：SQLite 不保存 tzinfo，混用 aware/naive
    在做时间差运算时会直接抛 TypeError。全站统一用 naive UTC，展示层再本地化。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)
