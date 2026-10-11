"""文章、分类、标签、页面。"""
import re

from app.extensions import db
from app.models.mixins import TimestampMixin, utcnow

post_tags = db.Table(
    "post_tags",
    db.Column("post_id", db.Integer, db.ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Category(TimestampMixin, db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    slug = db.Column(db.String(96), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), default="")
    cover = db.Column(db.String(300), default="")
    color = db.Column(db.String(16), default="")
    icon = db.Column(db.String(48), default="")
    sort_order = db.Column(db.Integer, default=0)

    posts = db.relationship("Post", back_populates="category", lazy="dynamic")

    @property
    def post_count(self) -> int:
        return self.posts.filter_by(status="published").count()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Category {self.name}>"


class Tag(TimestampMixin, db.Model):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    slug = db.Column(db.String(96), unique=True, nullable=False, index=True)
    color = db.Column(db.String(16), default="")

    @property
    def post_count(self) -> int:
        return (
            Post.query.filter(Post.tags.any(id=self.id), Post.status == "published").count()
        )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Tag {self.name}>"


class Post(TimestampMixin, db.Model):
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    summary = db.Column(db.String(500), default="")
    content_md = db.Column(db.Text, default="")
    content_html = db.Column(db.Text, default="")
    cover = db.Column(db.String(300), default="")

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    status = db.Column(db.String(16), default="published", index=True)  # draft/published/private
    is_pinned = db.Column(db.Boolean, default=False, nullable=False)
    allow_comment = db.Column(db.Boolean, default=True, nullable=False)

    # 「夫妻共创」：一篇文章可以由两个人一起写，各自留下署名与段落
    co_written = db.Column(db.Boolean, default=False, nullable=False)
    co_author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    views = db.Column(db.Integer, default=0, nullable=False)
    likes = db.Column(db.Integer, default=0, nullable=False)
    reading_minutes = db.Column(db.Integer, default=1)
    published_at = db.Column(db.DateTime, default=utcnow, index=True)

    # 内容互联：手动指定「相关内容」，也可以自动按标签推荐
    related_ids = db.Column(db.String(255), default="")

    # 归属标记：老公 / 老婆 / 自定义（写入时快照，改称呼不影响历史文章）
    owner_label = db.Column(db.String(32), default="")

    category = db.relationship("Category", back_populates="posts")
    author = db.relationship("User", foreign_keys=[author_id], back_populates="posts")
    co_author = db.relationship("User", foreign_keys=[co_author_id])
    tags = db.relationship("Tag", secondary=post_tags, lazy="joined", backref=db.backref("posts", lazy="dynamic"))

    def bump_view(self) -> None:
        self.views = (self.views or 0) + 1

    @property
    def authors(self):
        out = [self.author] if self.author else []
        if self.co_author and self.co_author.id != (self.author_id or 0):
            out.append(self.co_author)
        return out

    @property
    def author_line(self) -> str:
        names = []
        for a in self.authors:
            label = a.role_text
            names.append(f"{a.display_name}（{label}）" if label else a.display_name)
        return " & ".join(names)

    @property
    def plain_excerpt(self) -> str:
        if self.summary:
            return self.summary
        text = re.sub(r"[#>*`\[\]!\-]", "", self.content_md or "")
        return text.strip().replace("\n", " ")[:140]

    @property
    def tag_names(self) -> list:
        return [t.name for t in self.tags]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Post {self.title!r}>"


class Page(TimestampMixin, db.Model):
    """内建单页：关于我们、关于本站等，内容可后台改。"""

    __tablename__ = "pages"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(48), unique=True, nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    content_md = db.Column(db.Text, default="")
    content_html = db.Column(db.Text, default="")
    is_system = db.Column(db.Boolean, default=False, nullable=False)
    show_in_nav = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Page {self.key}>"


class CustomPage(TimestampMixin, db.Model):
    """自定义页面：用户自己加的新页面，可挂组件区块。"""

    __tablename__ = "custom_pages"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    content_md = db.Column(db.Text, default="")
    content_html = db.Column(db.Text, default="")
    cover = db.Column(db.String(300), default="")
    show_in_nav = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    status = db.Column(db.String(16), default="published")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CustomPage {self.slug}>"
