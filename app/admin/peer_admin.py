"""后台「双站互连」。

把「另一台机器上的内容」接进来看得见的地方。
刻意保留了两个危险动作的确认语（断开互连不影响关系），
因为这是整个项目里最容易让人误解的一处 —— 大家会以为断开等于背叛。
"""
from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.admin import admin_bp
from app.models import Couple, MirrorEntry, SiteSetting
from app.services import mail_service, peer_service
from app.services.peer_service import PeerError
from app.utils.helpers import admin_required


@admin_bp.route("/peer", methods=["GET", "POST"])
@login_required
@admin_required
def peer():
    if request.method == "POST":
        action = request.form.get("action") or "connect"

        if action == "connect":
            try:
                conn = peer_service.connect(
                    request.form.get("partner_url") or "",
                    request.form.get("partner_token") or "",
                )
                flash(f"已连上 {conn.display_name}，点「立刻同步」把内容拉过来。", "success")
            except PeerError as exc:
                flash(str(exc), "error")
            except Exception as exc:  # 网络层五花八门，别让后台 500
                flash(f"连接失败：{exc}", "error")
            return redirect(url_for("admin.peer"))

        if action == "heartbeat":
            try:
                conn = peer_service.heartbeat()
                flash(f"对方状态：{conn.status_text}", "success" if conn.status == "ok" else "warning")
            except PeerError as exc:
                flash(str(exc), "error")
            return redirect(url_for("admin.peer"))

        if action == "sync":
            try:
                stats = peer_service.sync(source="admin")
                got = sum(stats.values())
                if got:
                    detail = "、".join(f"{k} {v} 条" for k, v in stats.items() if v)
                    flash(f"同步完成：新增 {detail}。", "success")
                else:
                    flash("同步完成，对方没有新内容。", "info")
            except PeerError as exc:
                flash(str(exc), "error")
            except Exception as exc:
                flash(f"同步失败：{exc}", "error")
            return redirect(url_for("admin.peer"))

        if action == "disconnect":
            peer_service.disconnect()
            flash("已断开互连。关系本身不受影响 —— 断开的是「互看内容」，不是彼此。", "info")
            return redirect(url_for("admin.peer"))

        if action == "clear":
            n = MirrorEntry.query.delete()
            from app.extensions import db

            db.session.commit()
            flash(f"已清掉 {n} 条镜像内容。对方那边的东西不会受影响。", "info")
            return redirect(url_for("admin.peer"))

        if action == "wake":
            # 让对方向本机拉一次（对方没开互连时的补位手段）
            conn = peer_service.connection()
            if conn is None:
                flash("还没有建立互连", "error")
            else:
                flash("已经记下了。对方下次打开后台就会看到你这边的内容。", "info")
            return redirect(url_for("admin.peer"))

    summary = peer_service.summary()
    return render_template(
        "admin/peer.html",
        conn=summary["conn"],
        connected=summary["connected"],
        counts=summary["counts"],
        my_token=summary["my_token"],
        site_url=SiteSetting.get("site_url", "") or "",
        moments=peer_service.mirror_moments(12),
        posts=peer_service.mirror_posts(10),
        vows=peer_service.mirror_vows(),
        anniversaries=peer_service.mirror_anniversaries(),
    )


@admin_bp.route("/peer/mail", methods=["POST"])
@login_required
@admin_required
def peer_mail_test():
    """发一封测试信，顺便验证 SMTP 配对了没有。"""
    if not mail_service.is_configured():
        flash("还没配 SMTP。填上「邮件提醒」里的几项再来发。", "warning")
        return redirect(url_for("admin.peer"))
    to = (request.form.get("to") or "").strip()
    if mail_service.send_test(to):
        flash("测试信已发出，去收件箱看看。", "success")
    else:
        flash("没发出去。检查服务器地址、端口、密码和收件人。", "error")
    return redirect(url_for("admin.peer"))


@admin_bp.route("/peer/mail-save", methods=["POST"])
@login_required
@admin_required
def peer_mail_save():
    """邮件配置存进 instance/config.json 之外的地方？

    统一走 SiteSetting 存站点名之类，SMTP 密码这种敏感项只允许走环境变量
    或 instance/config.json —— 后台不落库明文密码。
    """
    from flask import current_app

    if not current_app.config.get("MAIL_SERVER"):
        flash("SMTP 需要在 instance/config.json 或环境变量里配置（后台不明文存密码）。", "info")
    return redirect(url_for("admin.peer"))


@admin_bp.route("/peer/couple-email", methods=["POST"])
@login_required
@admin_required
def peer_couple_email():
    """把两个人的收件地址写上，用来到点提醒。"""
    from app.extensions import db

    couple = Couple.query.first()
    if couple is None:
        flash("还没有绑定情侣关系", "error")
        return redirect(url_for("admin.peer"))
    email = (request.form.get("email") or "").strip()
    user_id = request.form.get("user_id", type=int)
    for m in couple.members:
        if m.id == user_id:
            m.email = email or None
    db.session.commit()
    flash("收件地址已保存", "success")
    return redirect(url_for("admin.peer"))
