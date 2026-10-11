"""后台备份管理。"""
from flask import flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import login_required

from app.admin import admin_bp
from app.models import SiteSetting
from app.services import backup_service
from app.utils.helpers import admin_required


@admin_bp.route("/backup")
@login_required
@admin_required
def backup():
    return render_template(
        "admin/backup.html",
        records=backup_service.list_backups(),
        disk=backup_service.disk_usage(),
        settings=SiteSetting.as_dict(),
    )


@admin_bp.route("/backup/create", methods=["POST"])
@login_required
@admin_required
def backup_create():
    note = (request.form.get("note") or "").strip()
    include_uploads = bool(request.form.get("include_uploads", True))
    rec = backup_service.create_backup(kind="manual", note=note, include_uploads=include_uploads)
    flash(f"备份完成：{rec.filename}（{rec.size_human}）", "success")
    return redirect(url_for("admin.backup"))


@admin_bp.route("/backup/<int:backup_id>/download")
@login_required
@admin_required
def backup_download(backup_id: int):
    from app.extensions import db
    from app.models import BackupRecord

    rec = db.session.get(BackupRecord, backup_id)
    if rec is None:
        flash("备份记录不存在", "error")
        return redirect(url_for("admin.backup"))
    path = backup_service.backup_dir() / rec.filename
    if not path.exists():
        flash("备份文件已不存在", "error")
        return redirect(url_for("admin.backup"))
    return send_file(path, as_attachment=True, download_name=rec.filename)


@admin_bp.route("/backup/<int:backup_id>/verify")
@login_required
@admin_required
def backup_verify(backup_id: int):
    from app.extensions import db
    from app.models import BackupRecord

    rec = db.session.get(BackupRecord, backup_id)
    if rec is None:
        return jsonify({"ok": False, "reason": "备份记录不存在"}), 404
    return jsonify(backup_service.verify_backup(rec.filename))


@admin_bp.route("/backup/<int:backup_id>/restore", methods=["POST"])
@login_required
@admin_required
def backup_restore(backup_id: int):
    from app.extensions import db
    from app.models import BackupRecord

    rec = db.session.get(BackupRecord, backup_id)
    if rec is None:
        flash("备份记录不存在", "error")
        return redirect(url_for("admin.backup"))
    try:
        backup_service.restore_backup(rec.filename, restore_uploads=bool(request.form.get("restore_uploads", True)))
        flash("恢复完成。为避免会话错乱，请重新登录。", "success")
        return redirect(url_for("auth.login"))
    except Exception as exc:
        flash(f"恢复失败：{exc}", "error")
        return redirect(url_for("admin.backup"))


@admin_bp.route("/backup/<int:backup_id>/delete", methods=["POST"])
@login_required
@admin_required
def backup_delete(backup_id: int):
    from app.extensions import db
    from app.models import BackupRecord

    rec = db.session.get(BackupRecord, backup_id)
    if rec is None:
        flash("备份记录不存在", "error")
        return redirect(url_for("admin.backup"))
    path = backup_service.backup_dir() / rec.filename
    if path.exists():
        path.unlink()
    db.session.delete(rec)
    db.session.commit()
    flash("备份已删除", "info")
    return redirect(url_for("admin.backup"))


@admin_bp.route("/backup/export.json")
@login_required
@admin_required
def backup_export_json():
    import json

    payload = backup_service.export_json()
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    from flask import Response

    return Response(
        body,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=loveyouforever-export.json"},
    )


@admin_bp.route("/backup/import", methods=["POST"])
@login_required
@admin_required
def backup_import():
    import json

    file = request.files.get("file")
    if file is None:
        flash("请选择要导入的 JSON 文件", "error")
        return redirect(url_for("admin.backup"))
    try:
        payload = json.loads(file.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        flash(f"文件解析失败：{exc}", "error")
        return redirect(url_for("admin.backup"))

    backup_service.create_backup(kind="pre-import", note="导入前自动备份")
    stats = backup_service.import_json(payload, wipe=bool(request.form.get("wipe")))
    flash(f"导入完成：{', '.join(f'{k} {v} 条' for k, v in stats.items()) or '没有可导入的数据'}", "success")
    return redirect(url_for("admin.backup"))
