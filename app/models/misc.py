"""友链、插件记录、备份记录、小纸条。"""
from app.extensions import db
from app.models.mixins import TimestampMixin


class FriendLink(TimestampMixin, db.Model):
    __tablename__ = "friend_links"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(96), nullable=False)
    url = db.Column(db.String(300), nullable=False)
    avatar = db.Column(db.String(300), default="")
    description = db.Column(db.String(255), default="")
    # 友链也可以是「情侣站」，标记出来可以互相展示
    is_couple_site = db.Column(db.Boolean, default=False, nullable=False)
    is_approved = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    email = db.Column(db.String(160), default="")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FriendLink {self.name}>"


class PluginRecord(TimestampMixin, db.Model):
    """插件启停状态与配置。"""

    __tablename__ = "plugin_records"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(96), unique=True, nullable=False, index=True)
    version = db.Column(db.String(32), default="1.0.0")
    enabled = db.Column(db.Boolean, default=False, nullable=False)
    config_json = db.Column(db.Text, default="{}")
    author = db.Column(db.String(96), default="")
    description = db.Column(db.String(255), default="")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PluginRecord {self.name}>"


class BackupRecord(TimestampMixin, db.Model):
    __tablename__ = "backup_records"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    kind = db.Column(db.String(24), default="manual")  # manual/auto/scheduled/import
    size_bytes = db.Column(db.Integer, default=0)
    checksum = db.Column(db.String(128), default="")
    note = db.Column(db.String(255), default="")
    includes_uploads = db.Column(db.Boolean, default=True, nullable=False)
    status = db.Column(db.String(24), default="ok")

    @property
    def size_human(self) -> str:
        n = float(self.size_bytes or 0)
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024 or unit == "GB":
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} GB"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BackupRecord {self.filename}>"
