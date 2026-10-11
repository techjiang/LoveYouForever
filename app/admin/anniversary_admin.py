"""后台纪念日管理。

支持单个新建、批量录入（一行一个，方便一次性把生日、周年都填进去）、
置顶与删除。
"""
from datetime import date

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.admin import admin_bp
from app.extensions import db
from app.models import ANNIVERSARY_KINDS, Anniversary, Couple
from app.services import anniversary_service
from app.utils.helpers import admin_required


def _parse_date(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            from datetime import datetime

            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


@admin_bp.route("/couple/anniversaries")
@login_required
@admin_required
def anniversaries():
    c = Couple.query.first()
    items = anniversary_service.list_all(c)
    return render_template(
        "admin/anniversaries.html",
        couple=c,
        items=items,
        kinds=ANNIVERSARY_KINDS,
        humanize=anniversary_service.humanize,
        today=date.today(),
    )


@admin_bp.route("/couple/anniversaries/new", methods=["POST"])
@login_required
@admin_required
def anniversary_new():
    c = Couple.query.first()
    title = (request.form.get("title") or "").strip()
    anchor = _parse_date(request.form.get("anchor_on"))
    if not title:
        flash("请填一个名字", "error")
    elif not anchor:
        flash("日期格式不对，应该是 2024-05-20 这样", "error")
    else:
        anniversary_service.create(
            c,
            title,
            anchor,
            kind=request.form.get("kind") or "anniversary",
            repeat_yearly=bool(request.form.get("repeat_yearly")),
            note=request.form.get("note") or "",
            icon=request.form.get("icon") or "",
            is_pinned=bool(request.form.get("is_pinned")),
        )
        flash(f"「{title}」已记下", "success")
    return redirect(url_for("admin.anniversaries"))


@admin_bp.route("/couple/anniversaries/bulk", methods=["POST"])
@login_required
@admin_required
def anniversary_bulk():
    """批量录入。每行：日期 | 名字 | 类型（可选）

    一次性把一堆生日、周年都录进去，比一个个点表单快。
    """
    c = Couple.query.first()
    raw = request.form.get("bulk") or ""
    created, failed = 0, 0
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            failed += 1
            continue
        anchor = _parse_date(parts[0])
        title = parts[1]
        if not anchor or not title:
            failed += 1
            continue
        kind = parts[2] if len(parts) > 2 and parts[2] in ANNIVERSARY_KINDS else "anniversary"
        repeat = not (len(parts) > 3 and parts[3] in ("0", "no", "false", "否"))
        anniversary_service.create(c, title, anchor, kind=kind, repeat_yearly=repeat)
        created += 1

    if created:
        flash(f"成功录入 {created} 个" + (f"，{failed} 行没看懂已跳过" if failed else ""), "success")
    else:
        flash("没有解析出有效内容，格式是：日期 | 名字 | 类型", "error")
    return redirect(url_for("admin.anniversaries"))


@admin_bp.route("/couple/anniversaries/<int:item_id>/pin", methods=["POST"])
@login_required
@admin_required
def anniversary_pin(item_id: int):
    a = db.session.get(Anniversary, item_id)
    if a is None:
        flash("找不到这条", "error")
    else:
        a.is_pinned = not a.is_pinned
        db.session.commit()
        flash("已置顶" if a.is_pinned else "已取消置顶", "info")
    return redirect(url_for("admin.anniversaries"))


@admin_bp.route("/couple/anniversaries/<int:item_id>/delete", methods=["POST"])
@login_required
@admin_required
def anniversary_delete(item_id: int):
    a = db.session.get(Anniversary, item_id)
    if a is None:
        flash("找不到这条", "error")
    else:
        title = a.title
        db.session.delete(a)
        db.session.commit()
        flash(f"「{title}」已删除", "info")
    return redirect(url_for("admin.anniversaries"))
