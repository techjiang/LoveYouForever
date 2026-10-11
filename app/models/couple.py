"""情侣关系：绑定、永恒、约定、时间线。

设计要点
--------
1. `Couple` 一旦 `is_complete`（双方都进来）就锁死：不允许解绑、不允许换人。
   这条规则由 `app/services/couple_service.py` 强制执行，后台也不给开关。
2. `sealed`（永封）之后连数据库层面的边都焊死了，只留「纪念日」与「约定」可增补。
3. 双方都必须使用本博客系统：绑定通过一次性握手码 + 对方站点接口校验（见 couple_service）。
"""
from app.extensions import db
from app.models.mixins import TimestampMixin, utcnow


class Couple(TimestampMixin, db.Model):
    __tablename__ = "couples"

    id = db.Column(db.Integer, primary_key=True)
    # 关系名，比如「江 & 酱 的小窝」
    name = db.Column(db.String(96), default="我们")
    slogan = db.Column(db.String(255), default="")

    # 双方 user id（唯一约束保证一个人只能在一条关系里）
    user_a_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    user_b_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # 纪念日
    anniversary = db.Column(db.Date, nullable=True)
    # 绑定成功的时间（也是永恒计时起点）
    bound_at = db.Column(db.DateTime, nullable=True)

    # 永封：不可解、不可改、不可遮
    sealed = db.Column(db.Boolean, default=False, nullable=False)
    sealed_at = db.Column(db.DateTime, nullable=True)
    seal_hash = db.Column(db.String(128), default="")

    theme_color = db.Column(db.String(16), default="#ff5c8a")
    cover = db.Column(db.String(300), default="")
    note = db.Column(db.Text, default="")

    vows = db.relationship("Vow", back_populates="couple", cascade="all, delete-orphan")
    events = db.relationship(
        "CoupleEvent", back_populates="couple", cascade="all, delete-orphan",
        order_by="CoupleEvent.happened_on.desc()",
    )

    @property
    def members(self):
        from app.models.user import User

        out = []
        for uid in (self.user_a_id, self.user_b_id):
            if uid:
                u = db.session.get(User, uid)
                if u:
                    out.append(u)
        return out

    @property
    def is_complete(self) -> bool:
        return bool(self.user_a_id and self.user_b_id)

    def other_side_of(self, user_id: int):
        if user_id == self.user_a_id:
            return self.user_b_id
        if user_id == self.user_b_id:
            return self.user_a_id
        return None

    @property
    def days_together(self) -> int:
        start = self.bound_at or self.created_at
        if not start:
            return 0
        return max((utcnow() - start).days, 0)

    @property
    def status_text(self) -> str:
        if self.sealed:
            return "已永封 · 生生世世"
        if self.is_complete:
            return "已绑定 · 不可解除"
        return "等待另一半加入"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Couple #{self.id} {self.name}>"


class Vow(TimestampMixin, db.Model):
    """情侣约定 / 誓言。双方各自签名后生效。"""

    __tablename__ = "vows"

    id = db.Column(db.Integer, primary_key=True)
    couple_id = db.Column(db.Integer, db.ForeignKey("couples.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    content = db.Column(db.Text, default="")
    # promise(承诺) / rule(约法) / wish(愿望) / contract(契约)
    kind = db.Column(db.String(24), default="promise", index=True)

    # 是否必须双方签署
    require_both = db.Column(db.Boolean, default=True, nullable=False)
    signed_a_at = db.Column(db.DateTime, nullable=True)
    signed_b_at = db.Column(db.DateTime, nullable=True)

    # 契约指纹：内容 + 双方签名时间生成，防止事后偷偷改内容
    fingerprint = db.Column(db.String(128), default="")

    couple = db.relationship("Couple", back_populates="vows")

    @property
    def signed_a(self) -> bool:
        return self.signed_a_at is not None

    @property
    def signed_b(self) -> bool:
        return self.signed_b_at is not None

    @property
    def is_effective(self) -> bool:
        if self.require_both:
            return self.signed_a and self.signed_b
        return self.signed_a or self.signed_b

    @property
    def progress(self) -> str:
        return f"{int(self.signed_a) + int(self.signed_b)}/2"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Vow {self.title!r}>"


class CoupleEvent(TimestampMixin, db.Model):
    """两个人的时间线节点：第一次见面、第一次旅行……"""

    __tablename__ = "couple_events"

    id = db.Column(db.Integer, primary_key=True)
    couple_id = db.Column(db.Integer, db.ForeignKey("couples.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    detail = db.Column(db.Text, default="")
    happened_on = db.Column(db.Date, nullable=True, index=True)
    # milestone(里程碑) / trip(旅行) / daily(日常) / anniversary(纪念)
    kind = db.Column(db.String(24), default="daily", index=True)
    cover = db.Column(db.String(300), default="")
    location = db.Column(db.String(160), default="")

    couple = db.relationship("Couple", back_populates="events")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CoupleEvent {self.title!r}>"


class BindToken(TimestampMixin, db.Model):
    """一次性绑定握手码。

    因为要求「双方必须都用本博客项目」，绑定流程是：
    A 站生成 token -> 把 token 和站点地址告诉 B -> B 用自己站点账号确认
    -> 两边通过 /api/couple/handshake 校验 token 与站点指纹 -> 建立关系。
    token 只能成功消费一次，防止被第三人抢绑。
    """

    __tablename__ = "bind_tokens"

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    issuer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    site_url = db.Column(db.String(255), default="")
    site_fingerprint = db.Column(db.String(128), default="")
    used = db.Column(db.Boolean, default=False, nullable=False)
    used_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)

    @property
    def alive(self) -> bool:
        if self.used:
            return False
        if self.expires_at and utcnow() > self.expires_at:
            return False
        return True

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BindToken {self.token[:8]}…>"
