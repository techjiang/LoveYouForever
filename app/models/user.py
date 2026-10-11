"""用户与站点设置。"""
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager
from app.models.mixins import TimestampMixin, utcnow


class User(UserMixin, TimestampMixin, db.Model):
    """站点的使用者。情侣站里一般就两个人，但结构上不限制。"""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(160), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)

    nickname = db.Column(db.String(64), nullable=False, default="")
    avatar = db.Column(db.String(300), default="")
    bio = db.Column(db.String(500), default="")

    # 在情侣关系里的称呼：老公 / 老婆 / 男朋友 / 女朋友 / 自定义
    role_label = db.Column(db.String(32), default="")
    # 情侣专属称号，比如「宇宙第一可爱」
    pet_title = db.Column(db.String(64), default="")
    theme_color = db.Column(db.String(16), default="")

    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    last_login_at = db.Column(db.DateTime, nullable=True)
    last_login_ip = db.Column(db.String(64), default="")

    # 永远爱你功能：账号一旦绑定情侣关系，这个字段被写入 couple_id，
    # 并由服务层保证不可解除、不可更换。
    couple_id = db.Column(db.Integer, db.ForeignKey("couples.id"), nullable=True, index=True)
    # 是否已签署「永不解绑」承诺（签了就彻底焊死）
    sealed = db.Column(db.Boolean, default=False, nullable=False)
    sealed_at = db.Column(db.DateTime, nullable=True)

    posts = db.relationship(
        "Post", back_populates="author", lazy="dynamic", foreign_keys="Post.author_id"
    )
    co_posts = db.relationship(
        "Post", back_populates="co_author", lazy="dynamic", foreign_keys="Post.co_author_id"
    )
    moments = db.relationship(
        "Moment", back_populates="author", lazy="dynamic", foreign_keys="Moment.author_id"
    )

    # ---- 密码 ----
    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw, method="pbkdf2:sha256:600000")

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    # ---- 展示 ----
    @property
    def display_name(self) -> str:
        return self.nickname or self.username

    @property
    def couple(self):
        if self.couple_id is None:
            return None
        from app.models.couple import Couple

        return db.session.get(Couple, self.couple_id)

    @property
    def partner(self):
        c = self.couple
        if not c:
            return None
        other_id = c.other_side_of(self.id)
        return db.session.get(User, other_id) if other_id else None

    @property
    def is_bound(self) -> bool:
        if not self.couple_id:
            return False
        c = self.couple
        return bool(c and c.is_complete)

    @property
    def role_text(self) -> str:
        """给文章/瞬间打标签用，比如「老婆」「男朋友」。"""
        return self.role_label or ("宝贝" if self.is_bound else "")

    def can_bind(self) -> bool:
        """已经被绑定（尤其是已封存）的账号不允许再动关系。"""
        if self.sealed:
            return False
        c = self.couple
        return not (c and c.is_complete)

    def touch_login(self, ip: str = "") -> None:
        self.last_login_at = utcnow()
        self.last_login_ip = ip or ""

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.username}>"


@login_manager.user_loader
def load_user(user_id: str):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


class SiteSetting(TimestampMixin, db.Model):
    """键值对形式的站点设置，后台可视化编辑。"""

    __tablename__ = "site_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(96), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, default="")
    group = db.Column(db.String(48), default="general", index=True)
    label = db.Column(db.String(96), default="")
    hint = db.Column(db.String(255), default="")

    @staticmethod
    def get(key: str, default=None):
        row = SiteSetting.query.filter_by(key=key).first()
        if row is None or row.value is None:
            return default
        return row.value

    @staticmethod
    def set(key: str, value, group: str = "general", label: str = "", hint: str = ""):
        row = SiteSetting.query.filter_by(key=key).first()
        if row is None:
            row = SiteSetting(key=key, group=group)
            db.session.add(row)
        row.value = "" if value is None else str(value)
        if label:
            row.label = label
        if hint:
            row.hint = hint
        return row

    @staticmethod
    def as_dict() -> dict:
        return {r.key: r.value for r in SiteSetting.query.all()}

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SiteSetting {self.key}>"
