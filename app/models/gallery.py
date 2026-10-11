"""相册与照片。"""
from app.extensions import db
from app.models.mixins import TimestampMixin


class Album(TimestampMixin, db.Model):
    __tablename__ = "albums"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default="")
    cover = db.Column(db.String(300), default="")
    location = db.Column(db.String(160), default="")
    taken_on = db.Column(db.Date, nullable=True)
    is_public = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0)

    photos = db.relationship(
        "Photo", back_populates="album", cascade="all, delete-orphan",
        order_by="Photo.sort_order, Photo.id",
    )

    @property
    def photo_count(self) -> int:
        return len(self.photos)

    @property
    def display_cover(self) -> str:
        if self.cover:
            return self.cover
        first = self.photos[0] if self.photos else None
        return first.url if first else ""

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Album {self.title}>"


class Photo(TimestampMixin, db.Model):
    __tablename__ = "photos"

    id = db.Column(db.Integer, primary_key=True)
    album_id = db.Column(db.Integer, db.ForeignKey("albums.id", ondelete="CASCADE"), nullable=False, index=True)
    url = db.Column(db.String(400), nullable=False)
    caption = db.Column(db.String(255), default="")
    # 拍摄于 / 谁拍的
    taken_on = db.Column(db.Date, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    width = db.Column(db.Integer, default=0)
    height = db.Column(db.Integer, default=0)
    sort_order = db.Column(db.Integer, default=0)

    album = db.relationship("Album", back_populates="photos")
    owner = db.relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Photo {self.id}>"
