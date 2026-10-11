"""双站互连：连接记录与镜像内容。

两台机器各跑一套系统，各自有自己的数据库。这里存的是「对方那边的东西
在我这边的副本」—— 带来源标记，只读，绝不允许被本机的编辑流程改到。

特意没有做成双向同步：镜像过来的内容不能反向写回对方站。原因很简单，
对面那台机器不在我们手上，我们没资格替它改数据。
"""
from app.extensions import db
from app.models.mixins import TimestampMixin


class PeerConnection(TimestampMixin, db.Model):
    """和对方站点的连接。全局只有一条。"""

    __tablename__ = "peer_connections"

    id = db.Column(db.Integer, primary_key=True)
    partner_url = db.Column(db.String(300), default="")
    partner_name = db.Column(db.String(160), default="")   # 对方的关系名
    partner_names = db.Column(db.String(160), default="")  # 对方两个人的昵称
    partner_site = db.Column(db.String(160), default="")
    #: 对方后台会显示一个互连令牌，填进来可以挡住乱灌数据的路人
    partner_token = db.Column(db.String(96), default="")
    partner_sealed = db.Column(db.Boolean, default=False, nullable=False)

    enabled = db.Column(db.Boolean, default=True, nullable=False)
    status = db.Column(db.String(24), default="new")  # new/ok/error/off
    last_error = db.Column(db.String(300), default="")
    last_seen_at = db.Column(db.DateTime, nullable=True)
    last_sync_at = db.Column(db.DateTime, nullable=True)

    @property
    def is_connected(self) -> bool:
        return bool(self.partner_url and self.status == "ok")

    @property
    def display_name(self) -> str:
        return self.partner_name or self.partner_names or self.partner_url or "对方站点"

    @property
    def status_text(self) -> str:
        return {
            "ok": "已连通",
            "error": "连不上",
            "off": "已断开",
            "new": "还没连过",
        }.get(self.status, "未知")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PeerConnection {self.partner_url}>"


class MirrorEntry(TimestampMixin, db.Model):
    """对方站点内容的本地副本。

    kind + remote_id 唯一：同一条内容同步多少次都只有一行。
    """

    __tablename__ = "peer_mirrors"
    __table_args__ = (db.UniqueConstraint("kind", "remote_id", name="uq_peer_mirror"),)

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(24), nullable=False, index=True)  # moment/post/vow/anniversary
    remote_id = db.Column(db.String(64), nullable=False)
    title = db.Column(db.String(200), default="")
    summary = db.Column(db.String(500), default="")
    author = db.Column(db.String(96), default="")
    remote_url = db.Column(db.String(400), default="")
    #: 已经缓存到本机的图片地址（见 peer_service.fetch_image）
    image_url = db.Column(db.String(400), default="")
    thumb_url = db.Column(db.String(400), default="")
    payload_json = db.Column(db.Text, default="{}")
    published_at = db.Column(db.DateTime, nullable=True, index=True)

    @property
    def payload(self) -> dict:
        import json

        try:
            return json.loads(self.payload_json or "{}")
        except json.JSONDecodeError:
            return {}

    @property
    def kind_label(self) -> str:
        return {
            "moment": "瞬间",
            "post": "文章",
            "vow": "约定",
            "anniversary": "日子",
        }.get(self.kind, self.kind)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "summary": self.summary,
            "author": self.author,
            "image": self.image_url,
            "remote_url": self.remote_url,
            "published_at": self.published_at,
            "payload": self.payload,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MirrorEntry {self.kind}#{self.remote_id}>"
