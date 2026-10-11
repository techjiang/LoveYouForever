"""命令行工具：lyf init / backup / restore / export / import / seed。

设计目标是让不会写代码的人也能靠几行命令完成运维。
"""
import json
from pathlib import Path

import click
from flask import Flask
from flask.cli import with_appcontext


def register_cli(app: Flask) -> None:
    @app.cli.command("init")
    @click.option("--force", is_flag=True, help="强制重建默认数据")
    @with_appcontext
    def init_cmd(force):
        """初始化站点（建表 + 默认设置 + 默认管理员）。"""
        from app.extensions import db
        from app.services.bootstrap import init_site

        db.create_all()
        if force:
            from app.models import SiteSetting

            SiteSetting.query.delete()
            db.session.commit()
        init_site(app)
        click.secho("初始化完成。默认账号 admin / loveyou，请尽快改密码。", fg="green")

    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    @click.option("--nickname", default="")
    @with_appcontext
    def create_admin(username, password, nickname):
        """新建一个管理员账号。"""
        from app.extensions import db
        from app.models import User

        if User.query.filter_by(username=username).first():
            click.secho("用户名已存在", fg="red")
            return
        u = User(username=username, nickname=nickname or username, is_admin=True)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        click.secho(f"管理员 {username} 创建成功", fg="green")

    @app.cli.command("reset-password")
    @click.option("--username", prompt=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    @with_appcontext
    def reset_password(username, password):
        """重置某个账号的密码。"""
        from app.extensions import db
        from app.models import User

        u = User.query.filter_by(username=username).first()
        if u is None:
            click.secho("找不到这个用户", fg="red")
            return
        u.set_password(password)
        db.session.commit()
        click.secho("密码已重置", fg="green")

    @app.cli.command("backup")
    @click.option("--note", default="", help="备注")
    @click.option("--no-uploads", is_flag=True, help="不包含上传的图片")
    @with_appcontext
    def backup_cmd(note, no_uploads):
        """立刻做一份全量备份。"""
        from app.services import backup_service

        rec = backup_service.create_backup(kind="cli", note=note, include_uploads=not no_uploads)
        click.secho(f"备份完成：{rec.filename}（{rec.size_human}）", fg="green")

    @app.cli.command("backup-list")
    @with_appcontext
    def backup_list():
        """列出所有备份。"""
        from app.services import backup_service

        for r in backup_service.list_backups():
            click.echo(f"{r.filename}\t{r.size_human}\t{r.kind}\t{r.created_at}")

    @app.cli.command("restore")
    @click.argument("filename")
    @click.option("--no-uploads", is_flag=True)
    @with_appcontext
    def restore_cmd(filename, no_uploads):
        """从备份恢复。恢复前会自动再备份一份。"""
        from app.services import backup_service

        try:
            backup_service.restore_backup(filename, restore_uploads=not no_uploads)
            click.secho("恢复完成。为避免会话错乱，请重新登录。", fg="green")
        except FileNotFoundError:
            click.secho(f"找不到备份文件：{filename}", fg="red")
            click.echo("用 `flask backup-list` 查看可用的备份。")

    @app.cli.command("export")
    @click.option("--out", default="loveyouforever-export.json")
    @with_appcontext
    def export_cmd(out):
        """导出站点数据为 JSON。"""
        from app.services import backup_service

        payload = backup_service.export_json()
        Path(out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        click.secho(f"已导出到 {out}", fg="green")

    @app.cli.command("import")
    @click.argument("path")
    @click.option("--wipe", is_flag=True, help="导入前清空现有业务数据")
    @with_appcontext
    def import_cmd(path, wipe):
        """从 JSON 导入数据。"""
        from app.services import backup_service

        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        stats = backup_service.import_json(payload, wipe=wipe)
        click.secho(f"导入完成：{stats}", fg="green")

    @app.cli.command("seed")
    @click.option("--with-partner", is_flag=True, help="额外建一个演示用的「另一半」账号，方便看双人效果")
    @with_appcontext
    def seed_cmd(with_partner):
        """写入一批演示内容，方便第一次看到效果。

        默认不造假人：演示文章全部归到站长名下。加 --with-partner 才会
        创建一个 partner 账号（密码 loveyou）和一条演示绑定关系。
        """
        from app.utils.seed import seed_demo

        stats = seed_demo(with_partner=with_partner)
        wrote = "、".join(f"{k} {v}" for k, v in stats.items() if v)
        if wrote:
            click.secho(f"新增：{wrote}", fg="green")
        else:
            click.secho("演示内容已经齐了，这次没有新增。", fg="green")
        click.echo("这条命令是补全而不是重建：已经有的内容不会重复写，也不会被覆盖。")
        if with_partner:
            click.secho("含演示用的另一半账号 partner / loveyou，上线前请删除", fg="yellow")
        else:
            click.secho("未创建虚拟另一半，可用 --with-partner 查看双人效果", fg="yellow")

    @app.cli.command("doctor")
    @with_appcontext
    def doctor_cmd():
        """体检：检查目录权限、数据库、配置是否正常。"""
        import os

        from app.models import Couple, Post, User

        click.echo("=== LoveYouForever 体检报告 ===")
        click.echo(f"数据库: {app.config['SQLALCHEMY_DATABASE_URI']}")
        click.echo(f"上传目录: {app.config['UPLOAD_FOLDER']} 可写={os.access(app.config['UPLOAD_FOLDER'], os.W_OK)}")
        click.echo(f"备份目录: {app.config['BACKUP_FOLDER']} 可写={os.access(app.config['BACKUP_FOLDER'], os.W_OK)}")
        click.echo(f"用户数: {User.query.count()}  文章数: {Post.query.count()}")
        couple = Couple.query.first()
        click.echo(f"情侣关系: {'已绑定 ' + couple.status_text if couple else '未绑定'}")

        from app.services import anniversary_service

        stats = anniversary_service.stats(couple)
        click.echo(f"纪念日: {stats['total']} 个（今天 {stats['today']} 个，未来 30 天 {stats['soon']} 个）")
        nxt = stats["next"]
        if nxt:
            click.echo(f"下一个: {nxt.title} —— {anniversary_service.humanize(nxt)}")

        # 体检项和后台「站点体检」共用一套判断，不各写一遍
        from app.services import health_service

        report = health_service.run_all()
        click.echo("")
        click.echo(f"--- 体检：{report['headline']} ---")
        marks = {"ok": "✓", "warn": "!", "error": "✗"}
        colors = {"ok": "green", "warn": "yellow", "error": "red"}
        for row in report["rows"]:
            click.secho(f"  {marks[row['level']]} {row['title']}", fg=colors[row["level"]])
            if row["detail"]:
                click.echo(f"      {row['detail']}")
            if row["fix"] and row["level"] != "ok":
                click.echo(f"      → {row['fix']}")

        if report["errors"]:
            click.secho("有需要立刻处理的问题。", fg="red")
        elif report["warnings"]:
            click.secho("体检通过，有几项建议看一下。", fg="yellow")
        else:
            click.secho("检查完毕，一切正常。", fg="green")

    @app.cli.command("remind")
    @click.option("--force", is_flag=True, help="绕过「今天已经发过」的判断，直接发")
    @with_appcontext
    def remind_cmd(force):
        """检查快到的纪念日，该提醒就发一封邮件。

        配进 crontab 就是定时提醒：0 9 * * * flask remind
        """
        from app.models import Couple
        from app.services import mail_service

        couple = Couple.query.first()
        if couple is None:
            click.secho("还没有绑定情侣关系，没什么可提醒的。", fg="yellow")
            return
        if not mail_service.is_configured():
            click.secho("没配 SMTP（instance/config.json 或 LYF_MAIL_* 环境变量），跳过。", fg="yellow")
            return

        items = mail_service.due_items(couple)
        if not items:
            click.secho("三天内没有要提醒的日子。", fg="green")
            return
        for a in items:
            click.echo(f"  · {a.title}")

        if force:
            from app.models import SiteSetting
            from app.extensions import db

            SiteSetting.set("reminder_sent_on", "")
            db.session.commit()
        sent = mail_service.maybe_send_daily(couple)
        click.secho("已发出提醒。" if sent else "今天已经发过了（加 --force 可强发）。",
                    fg="green" if sent else "yellow")

    @app.cli.command("peer")
    @click.option("--url", default="", help="对方站点地址")
    @click.option("--token", default="", help="对方的互连令牌")
    @click.option("--sync", is_flag=True, help="连接后立刻同步一次")
    @with_appcontext
    def peer_cmd(url, token, sync):
        """连接另一台「永远爱你」，把对方的内容接过来。

        例子：flask peer --url https://ta.example.com --sync
        """
        from app.services import peer_service
        from app.services.peer_service import PeerError

        try:
            conn = peer_service.connect(url, token)
        except PeerError as exc:
            click.secho(f"连接失败：{exc}", fg="red")
            return
        click.secho(f"已连上 {conn.display_name}", fg="green")
        click.echo(f"本机互连令牌（发给对方）：{peer_service.summary()['my_token']}")

        if sync:
            stats = peer_service.sync(source="cli")
            wrote = "、".join(f"{k} {v}" for k, v in stats.items() if v) or "没有新内容"
            click.secho(f"同步完成：{wrote}", fg="green")

    @app.cli.command("peer-demo")
    @with_appcontext
    def peer_demo_cmd():
        """在本机造一个「对方站点」，用来演示 / 自测互连效果。

        会起一个临时的假站点对象（不联网），往镜像表里写一批带 demo 标记的内容。
        只用于演示，正式站别跑 —— 真实互连请用 `flask peer`。
        """
        from app.services import peer_service

        stats = peer_service.seed_demo_peer()
        wrote = "、".join(f"{k} {v}" for k, v in stats.items() if v) or "已经造过了"
        click.secho(f"演示互连已就绪：{wrote}", fg="green")
        click.echo("打开后台「双站互连」或情侣页就能看到效果。")
        click.echo("（正式站要连真站点：flask peer --url https://ta.example.com）")

    @app.cli.command("peer-demo-clear")
    @with_appcontext
    def peer_demo_clear_cmd():
        """清掉 `flask peer-demo` 造的演示互连数据。"""
        from app.services import peer_service

        n = peer_service.clear_demo_peer()
        click.secho(f"已清掉演示互连数据（{n} 条）。", fg="green")
