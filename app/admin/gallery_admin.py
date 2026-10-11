"""后台相册管理。"""
from datetime import date

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required
from werkzeug.utils import secure_filename

from app.admin import admin_bp
from app.extensions import db
from app.models import Album, Photo
from app.utils.helpers import admin_required, unique_slug


@admin_bp.route("/albums")
@login_required
@admin_required
def albums():
    return render_template("admin/albums.html", albums=Album.query.order_by(Album.sort_order, Album.id.desc()).all())


@admin_bp.route("/albums/new", methods=["POST"])
@login_required
@admin_required
def album_new():
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("相册名不能为空", "error")
        return redirect(url_for("admin.albums"))
    album = Album(
        title=title,
        slug=unique_slug(Album, title),
        description=(request.form.get("description") or "").strip(),
        location=(request.form.get("location") or "").strip(),
        cover=(request.form.get("cover") or "").strip(),
        is_public=bool(request.form.get("is_public", True)),
        taken_on=_parse_date(request.form.get("taken_on")),
    )
    db.session.add(album)
    db.session.commit()
    flash("相册已创建，去加照片吧", "success")
    return redirect(url_for("admin.album_detail", album_id=album.id))


@admin_bp.route("/albums/<int:album_id>")
@login_required
@admin_required
def album_detail(album_id: int):
    album = db.session.get(Album, album_id)
    if album is None:
        from flask import abort

        abort(404)
    return render_template("admin/album_detail.html", album=album)


@admin_bp.route("/albums/<int:album_id>/edit", methods=["POST"])
@login_required
@admin_required
def album_edit(album_id: int):
    album = db.session.get(Album, album_id)
    album.title = (request.form.get("title") or album.title).strip()
    album.description = (request.form.get("description") or "").strip()
    album.location = (request.form.get("location") or "").strip()
    album.cover = (request.form.get("cover") or "").strip()
    album.is_public = bool(request.form.get("is_public"))
    album.taken_on = _parse_date(request.form.get("taken_on"))
    db.session.commit()
    flash("相册已更新", "success")
    return redirect(url_for("admin.album_detail", album_id=album.id))


@admin_bp.route("/albums/<int:album_id>/delete", methods=["POST"])
@login_required
@admin_required
def album_delete(album_id: int):
    album = db.session.get(Album, album_id)
    db.session.delete(album)
    db.session.commit()
    flash("相册已删除", "info")
    return redirect(url_for("admin.albums"))


@admin_bp.route("/albums/<int:album_id>/photos", methods=["POST"])
@login_required
@admin_required
def photo_add(album_id: int):
    album = db.session.get(Album, album_id)
    urls = request.form.getlist("urls")
    caption = (request.form.get("caption") or "").strip()
    added = 0
    for url in urls:
        url = url.strip()
        if not url:
            continue
        db.session.add(
            Photo(album_id=album.id, url=url, caption=caption, taken_on=_parse_date(request.form.get("taken_on")))
        )
        added += 1
    db.session.commit()
    flash(f"已添加 {added} 张照片", "success")
    return redirect(url_for("admin.album_detail", album_id=album.id))


@admin_bp.route("/photos/<int:photo_id>/delete", methods=["POST"])
@login_required
@admin_required
def photo_delete(photo_id: int):
    photo = db.session.get(Photo, photo_id)
    album_id = photo.album_id
    db.session.delete(photo)
    db.session.commit()
    return redirect(url_for("admin.album_detail", album_id=album_id))


@admin_bp.route("/photos/<int:photo_id>/caption", methods=["POST"])
@login_required
@admin_required
def photo_caption(photo_id: int):
    photo = db.session.get(Photo, photo_id)
    photo.caption = (request.form.get("caption") or "").strip()
    db.session.commit()
    return redirect(url_for("admin.album_detail", album_id=photo.album_id))


def _parse_date(raw):
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None
