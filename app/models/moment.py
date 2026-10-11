"""瞬间：两个人的共同朋友圈。

和普通博客的「说说」不同，这里的瞬间是双人共享的：
一条瞬间可以指定「发布者」，也可以选择「一起发」，
评论和点赞都记在两个人的共同空间里。
"""
from app.extensions import db
from app.models.mixins import TimestampMixin, utcnow


class Moment(TimestampMixin, db.Model):
    __tablename__ = "moments"

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, default="")
    images = db.Column(db.Text, default="")  # 多图用换行分隔
    location = db.Column(db.String(160), default="")
    mood = db.Column(db.String(32), default="")  # 心情 emoji

    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    # 是否「一起发」：双方共同署名
    co_authored = db.Column(db.Boolean, default=False, nullable=False)
    co_author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    is_public = db.Column(db.Boolean, default=True, nullable=False)
    is_pinned = db.Column(db.Boolean, default=False, nullable=False)

    like_count = db.Column(db.Integer, default=0, nullable=False)
    comment_count = db.Column(db.Integer, default=0, nullable=False)

    author = db.relationship("User", foreign_keys=[author_id], back_populates="moments")
    co_author = db.relationship("User", foreign_keys=[co_author_id])
    comments = db.relationship(
        "MomentComment", back_populates="moment", cascade="all, delete-orphan",
        order_by="MomentComment.created_at",
    )

    @property
    def image_list(self) -> list:
        if not self.images:
            return []
        return [x.strip() for x in self.images.replace(",", "\n").split("\n") if x.strip()]

    @property
    def authors(self):
        out = [self.author] if self.author else []
        if self.co_author and self.co_author.id != (self.author_id or 0):
            out.append(self.co_author)
        return out

    @property
    def author_line(self) -> str:
        if self.co_authored and len(self.authors) > 1:
            a, b = self.authors[0], self.authors[1]
            return f"{a.display_name} & {b.display_name}"
        return self.author.display_name if self.author else ""

    @property
    def time_group(self) -> str:
        now = utcnow()
        delta = (now - self.created_at).total_seconds()
        if delta < 3600:
            return f"{max(int(delta // 60), 1)} 分钟前"
        if delta < 86400:
            return f"{int(delta // 3600)} 小时前"
        if delta < 86400 * 7:
            return f"{int(delta // 86400)} 天前"
        return self.created_at.strftime("%Y-%m-%d")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Moment #{self.id}>"


class MomentComment(TimestampMixin, db.Model):
    __tablename__ = "moment_comments"

    id = db.Column(db.Integer, primary_key=True)
    moment_id = db.Column(db.Integer, db.ForeignKey("moments.id", ondelete="CASCADE"), nullable=False, index=True)
    # 允许游客评论（填昵称），也允许登录用户评论
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    guest_name = db.Column(db.String(64), default="")
    guest_site = db.Column(db.String(255), default="")
    content = db.Column(db.Text, nullable=False)
    reply_to_id = db.Column(db.Integer, db.ForeignKey("moment_comments.id"), nullable=True)

    moment = db.relationship("Moment", back_populates="comments")
    author = db.relationship("User")
    reply_to = db.relationship("MomentComment", remote_side=[id], post_update=True)

    @property
    def display_name(self) -> str:
        if self.author:
            return self.author.display_name
        return self.guest_name or "匿名"

    @property
    def role_text(self) -> str:
        return self.author.role_text if self.author else ""

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MomentComment #{self.id}>"


class MomentLike(TimestampMixin, db.Model):
    __tablename__ = "moment_likes"
    __table_args__ = (db.UniqueConstraint("moment_id", "user_id", "guest_key", name="uq_moment_like"),)

    id = db.Column(db.Integer, primary_key=True)
    moment_id = db.Column(db.Integer, db.ForeignKey("moments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    guest_key = db.Column(db.String(64), default="")  # 游客用 ip hash 去重

    moment = db.relationship("Moment")
    user = db.relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MomentLike #{self.id}>"
