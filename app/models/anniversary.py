"""纪念日与倒数日。

和 `CoupleEvent`（流水式的时间线）不一样，这里记的是**会被反复数着过的日子**：
在一起的周年、生日、领证日、下次见面的日子。

两类：
- `repeat_yearly=True`  —— 每年都会再来一次（生日、周年）。倒计时永远指向下一个。
- `repeat_yearly=False` —— 只发生一次（婚礼、旅行、约定见面的那天）。过了就归档。

倒计时在 `days_left` 里算，展示层直接读，不要在模板里做日期运算。
"""
from datetime import date, timedelta

from app.extensions import db
from app.models.mixins import TimestampMixin

KINDS = {
    "anniversary": "纪念日",
    "birthday": "生日",
    "festival": "节日",
    "countdown": "倒数日",
    "custom": "自定义",
}


class Anniversary(TimestampMixin, db.Model):
    __tablename__ = "anniversaries"

    id = db.Column(db.Integer, primary_key=True)
    couple_id = db.Column(db.Integer, db.ForeignKey("couples.id"), nullable=True, index=True)

    title = db.Column(db.String(120), nullable=False)
    # 纪念日锚定的那一天（第一次发生的日期），倒计时以它为基准推
    anchor_on = db.Column(db.Date, nullable=False, index=True)
    kind = db.Column(db.String(24), default="anniversary", index=True)
    repeat_yearly = db.Column(db.Boolean, default=True, nullable=False)

    # 属于谁：空 = 两个人的共同日子
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    note = db.Column(db.Text, default="")
    icon = db.Column(db.String(16), default="")
    color = db.Column(db.String(16), default="")
    is_pinned = db.Column(db.Boolean, default=False, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)

    couple = db.relationship("Couple", backref=db.backref("anniversaries", cascade="all, delete-orphan"))

    @property
    def kind_label(self) -> str:
        return KINDS.get(self.kind, "纪念日")

    def _next_occurrence(self, today: date) -> date | None:
        """下一次到哪天。不重复的日子过去了就没有下一次。"""
        if not self.repeat_yearly:
            return self.anchor_on if self.anchor_on >= today else None
        try:
            nxt = self.anchor_on.replace(year=today.year)
        except ValueError:  # 2/29 落在平年
            nxt = date(today.year, 2, 28)
        if nxt < today:
            try:
                nxt = nxt.replace(year=today.year + 1)
            except ValueError:
                nxt = date(today.year + 1, 2, 28)
        return nxt

    def days_left(self, today: date | None = None) -> int | None:
        """离下一次还有几天。0 就是今天。没有下一次返回 None。"""
        today = today or date.today()
        nxt = self._next_occurrence(today)
        return None if nxt is None else (nxt - today).days

    def days_passed(self, today: date | None = None) -> int:
        """从锚点那天起过了多少天。"""
        today = today or date.today()
        return max((today - self.anchor_on).days, 0)

    def next_date(self, today: date | None = None) -> date | None:
        return self._next_occurrence(today or date.today())

    @property
    def is_today(self) -> bool:
        return self.days_left() == 0

    @property
    def years_count(self) -> int:
        """第几个年头，用来写「三周年」。"""
        today = date.today()
        n = today.year - self.anchor_on.year
        if (today.month, today.day) < (self.anchor_on.month, self.anchor_on.day):
            n -= 1
        return max(n, 0)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Anniversary {self.title!r}>"
