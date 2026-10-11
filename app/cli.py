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
    @with_appcontext
    def seed_cmd():
        """写入一批演示内容，方便第一次看到效果。"""
        from app.utils.seed import seed_demo

        seed_demo()
        click.secho("演示数据已写入", fg="green")

    @app.cli.command("doctor")
    @with_appcontext
    def doctor_cmd():
        """体检：检查目录权限、数据库、配置是否正常。"""
        import os

        from app.extensions import db
        from app.models import Couple, Post, User

        click.echo("=== LoveYouForever 体检报告 ===")
        click.echo(f"数据库: {app.config['SQLALCHEMY_DATABASE_URI']}")
        click.echo(f"上传目录: {app.config['UPLOAD_FOLDER']} 可写={os.access(app.config['UPLOAD_FOLDER'], os.W_OK)}")
        click.echo(f"备份目录: {app.config['BACKUP_FOLDER']} 可写={os.access(app.config['BACKUP_FOLDER'], os.W_OK)}")
        click.echo(f"用户数: {User.query.count()}  文章数: {Post.query.count()}")
        couple = Couple.query.first()
        click.echo(f"情侣关系: {'已绑定 ' + couple.status_text if couple else '未绑定'}")
        click.secho("检查完毕。", fg="green")
