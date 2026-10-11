"""相册。"""
from flask import Blueprint, render_template

from app.models import Album, Photo

gallery_bp = Blueprint("gallery", __name__, url_prefix="/gallery")


@gallery_bp.route("/")
def index():
    albums = Album.query.filter_by(is_public=True).order_by(Album.sort_order, Album.id.desc()).all()
    total_photos = Photo.query.count()
    return render_template("gallery/index.html", albums=albums, total_photos=total_photos)


@gallery_bp.route("/<slug>")
def album(slug: str):
    album_obj = Album.query.filter_by(slug=slug).first_or_404()
    if not album_obj.is_public:
        from flask_login import current_user

        if not current_user.is_authenticated:
            from flask import abort

            abort(404)
    others = (
        Album.query.filter(Album.id != album_obj.id, Album.is_public.is_(True))
        .order_by(Album.sort_order)
        .limit(6)
        .all()
    )
    return render_template("gallery/album.html", album=album_obj, others=others)
