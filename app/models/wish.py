"""每日一提 / 夫妻寄语：贴在门上的一句话。

这不是「文章」，也不是「瞬间」。它是首页最上面的一行字 ——
今天想对你说的话，随时能改，改完就生效，不留历史包袱。

设计上只保留最近 N 条（见 `prune`），因为它要的是「此刻」，
不是「档案」。真要留档，写篇文章就好。
"""
from app.extensions import db
from app.models.mixins import TimestampMixin

#: 心情标签，和瞬间共用一套语义但更轻
MOODS = {
    "sweet": ("💗", "甜"),
    "miss": ("🌙", "想你"),
    "cheer": ("🌟", "加油"),
    "sorry": ("🍃", "对不起"),
    "daily": ("☕", "日常"),
}


class DailyWish(TimestampMixin, db.Model):
    """首页顶上的一句话。"""

    __tablename__ = "daily_wishes"

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    mood = db.Column(db.String(16), default="sweet", index=True)

    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    # 只给两个人看：默认公开（首页可见），可关掉
    is_public = db.Column(db.Boolean, default=True, nullable=False)

    author = db.relationship("User")

    @property
    def mood_icon(self) -> str:
        return MOODS.get(self.mood, MOODS["sweet"])[0]

    @property
    def mood_label(self) -> str:
        return MOODS.get(self.mood, MOODS["sweet"])[1]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DailyWish #{self.id}>"
