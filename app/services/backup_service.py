"""备份服务：把数据当传家宝对待。

策略：
- 全量快照（数据库 + 上传文件）打包成 tar.gz，记录 sha256 校验值；
- 支持 SQLite 原生 backup API（在线安全备份，不会因并发写损坏）；
- 支持站点级 JSON 导出（便于迁移/审阅），也可从 JSON 导入；
- 自动轮转，保留最近 N 份；
- 恢复前自动先做一份「恢复前快照」，手滑也能救回来。
"""
import hashlib
import io
import json
import os
import shutil
import sqlite3
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app
from sqlalchemy import inspect, text

from app.extensions import db
from app.models import BackupRecord
from app.models.mixins import utcnow


def backup_dir() -> Path:
    p = Path(current_app.config["BACKUP_FOLDER"])
    p.mkdir(parents=True, exist_ok=True)
    return p


def _db_path() -> Path | None:
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    if uri.startswith("sqlite:///"):
        return Path(uri.replace("sqlite:///", "", 1))
    return None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _snapshot_sqlite(dest: Path) -> None:
    """用 sqlite3 在线备份 API，保证一致性。"""
    src = _db_path()
    if not src or not src.exists():
        return
    db.session.remove()
    src_conn = sqlite3.connect(str(src))
    dst_conn = sqlite3.connect(str(dest))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()


def create_backup(kind: str = "manual", note: str = "", include_uploads: bool = True) -> BackupRecord:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    name = f"lyf-backup-{stamp}-{kind}.tar.gz"
    target = backup_dir() / name

    with tarfile.open(target, "w:gz") as tar:
        db_file = _db_path()
        if db_file and db_file.exists():
            tmp = backup_dir() / f".tmp-{stamp}.sqlite"
            _snapshot_sqlite(tmp)
            tar.add(tmp, arcname=f"database/{db_file.name}")
            tmp.unlink(missing_ok=True)
        else:
            # 非 SQLite：导成 JSON 落袋为安
            dump = export_json()
            data = json.dumps(dump, ensure_ascii=False, indent=2).encode("utf-8")
            info = tarfile.TarInfo("database/dump.json")
            info.size = len(data)
            info.mtime = int(datetime.now(timezone.utc).timestamp())
            tar.addfile(info, io.BytesIO(data))

        if include_uploads:
            uploads = Path(current_app.config["UPLOAD_FOLDER"])
            if uploads.exists():
                tar.add(uploads, arcname="uploads")

        # 备份元信息
        meta = {
            "site": current_app.config["SITE_NAME"],
            "created_at": utcnow().isoformat(),
            "kind": kind,
            "note": note,
            "app": "LoveYouForever",
        }
        meta_bytes = json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8")
        info = tarfile.TarInfo("meta.json")
        info.size = len(meta_bytes)
        tar.addfile(info, io.BytesIO(meta_bytes))

    record = BackupRecord(
        filename=name,
        kind=kind,
        size_bytes=target.stat().st_size,
        checksum=_sha256(target),
        note=note,
        includes_uploads=include_uploads,
        status="ok",
    )
    db.session.add(record)
    db.session.commit()
    prune_backups()
    return record


def _freeze_backup(src: Path, checksum: str) -> None:
    """把即将用于恢复的文件标记为「不参与轮转」。"""
    frozen = backup_dir() / f".frozen-{src.name}"
    if not frozen.exists():
        shutil.copy2(src, frozen)


def _cleanup_frozen() -> None:
    for f in backup_dir().glob(".frozen-*.tar.gz"):
        f.unlink(missing_ok=True)


def prune_backups(keep: int | None = None) -> int:
    keep = keep or current_app.config["BACKUP_KEEP"]
    records = BackupRecord.query.order_by(BackupRecord.created_at.desc()).all()
    removed = 0
    for rec in records[keep:]:
        f = backup_dir() / rec.filename
        if (backup_dir() / f".frozen-{rec.filename}").exists():
            continue  # 正在被恢复使用
        if f.exists():
            try:
                f.unlink()
            except OSError:
                continue
        db.session.delete(rec)
        removed += 1
    if removed:
        db.session.commit()
    return removed


def verify_backup(filename: str) -> dict:
    f = backup_dir() / filename
    if not f.exists():
        return {"ok": False, "reason": "文件不存在"}
    record = BackupRecord.query.filter_by(filename=filename).first()
    checksum = _sha256(f)
    ok = (record is None) or (record.checksum == checksum) or not record.checksum
    try:
        with tarfile.open(f, "r:gz") as tar:
            names = tar.getnames()[:50]
    except tarfile.TarError as exc:
        return {"ok": False, "reason": f"压缩包损坏: {exc}"}
    return {"ok": ok, "checksum": checksum, "expected": record.checksum if record else "", "members": names}


def restore_backup(filename: str, restore_uploads: bool = True) -> dict:
    """从快照恢复。恢复前会自动再做一份安全备份。"""
    candidate = Path(filename)
    # 依次尝试：绝对路径 -> 相对当前工作目录 -> 备份目录下的文件名
    probes = [candidate, Path.cwd() / candidate, backup_dir() / Path(filename).name]
    src = next((p for p in probes if p.is_file()), None)
    if src is None:
        raise FileNotFoundError(filename)
    filename = src.name

    # 先算校验值，免得自动备份时把源文件轮转删掉
    checksum = _sha256(src)
    _freeze_backup(src, checksum)

    create_backup(kind="pre-restore", note=f"恢复 {filename} 前自动备份")

    if not src.exists():
        # 极端情况下仍被轮转删除，用冻结副本恢复
        src = backup_dir() / f".frozen-{filename}"
    if not src.exists():
        raise FileNotFoundError(filename)

    db_file = _db_path()
    db.session.remove()

    with tarfile.open(src, "r:gz") as tar:
        members = tar.getnames()
        # 数据库
        db_member = next((m for m in members if m.startswith("database/") and m.endswith((".sqlite", ".sqlite3", ".db"))), None)
        if db_file and db_member:
            extracted = tar.extractfile(db_member)
            if extracted:
                db_file.parent.mkdir(parents=True, exist_ok=True)
                with db_file.open("wb") as out:
                    shutil.copyfileobj(extracted, out)

        # 上传目录
        if restore_uploads:
            uploads = Path(current_app.config["UPLOAD_FOLDER"])
            tmp_extract = backup_dir() / ".restore-uploads"
            if tmp_extract.exists():
                shutil.rmtree(tmp_extract, ignore_errors=True)
            for m in members:
                if m.startswith("uploads/") and not m.endswith("/"):
                    try:
                        _safe_extract(tar, m, tmp_extract.parent)
                    except (tarfile.TarError, OSError, ValueError):
                        continue
            extracted_uploads = backup_dir() / "uploads"
            if extracted_uploads.exists():
                for item in extracted_uploads.iterdir():
                    dst = uploads / item.name
                    if dst.exists():
                        shutil.rmtree(dst, ignore_errors=True) if dst.is_dir() else dst.unlink()
                    shutil.move(str(item), str(dst))
                extracted_uploads.rmdir()

    _cleanup_frozen()
    db.session.remove()
    return {"ok": True, "restored": filename}


def _safe_extract(tar: tarfile.TarFile, member: str, dest: Path) -> None:
    """只解压到目标目录内，挡住 ../ 之类的路径穿越。"""
    target = (dest / member).resolve()
    if not str(target).startswith(str(dest.resolve())):
        raise ValueError(f"拒绝解压越界路径: {member}")
    try:
        tar.extract(member, path=dest, filter="data")
    except TypeError:
        # Python < 3.12 没有 filter 参数
        tar.extract(member, path=dest)


# --------------------------------------------------------------------------
# JSON 导出 / 导入
# --------------------------------------------------------------------------
EXPORT_MODELS = [
    "User", "Couple", "Vow", "CoupleEvent", "Category", "Tag", "Post",
    "Page", "CustomPage", "Album", "Photo", "Moment", "MomentComment",
    "MomentLike", "FriendLink", "Note", "SiteSetting", "PluginRecord",
]

SENSITIVE_FIELDS = {"password_hash", "seal_hash"}


def export_json(include_sensitive: bool = False) -> dict:
    from app import models as model_module

    out = {"meta": {"app": "LoveYouForever", "exported_at": utcnow().isoformat(), "version": 1}, "tables": {}}
    for name in EXPORT_MODELS:
        model = getattr(model_module, name, None)
        if model is None:
            continue
        rows = []
        for obj in model.query.all():
            row = {}
            for col in inspect(obj).mapper.columns:
                key = col.key
                if key in SENSITIVE_FIELDS and not include_sensitive:
                    continue
                val = getattr(obj, key)
                if hasattr(val, "isoformat"):
                    val = val.isoformat()
                elif isinstance(val, (bytes, bytearray)):
                    val = val.decode("utf-8", "ignore")
                row[key] = val
            # 多对多关系（文章标签）
            if name == "Post":
                row["_tags"] = [t.name for t in obj.tags]
            rows.append(row)
        out["tables"][name] = rows
    return out


def import_json(payload: dict, wipe: bool = False) -> dict:
    """从 JSON 导入。默认追加，wipe=True 时先清空业务表。"""
    from app import models as model_module
    from app.extensions import db as _db

    tables = payload.get("tables") or {}
    stats = {}

    if wipe:
        for name in reversed(EXPORT_MODELS):
            model = getattr(model_module, name, None)
            if model is not None and name not in {"User"}:
                _db.session.query(model).delete()
        _db.session.commit()

    for name, rows in tables.items():
        model = getattr(model_module, name, None)
        if model is None:
            continue
        added = 0
        for row in rows:
            data = {k: v for k, v in row.items() if not k.startswith("_") and k != "tags"}
            if "id" in data and _db.session.get(model, data["id"]):
                continue
            try:
                obj = model(**{k: v for k, v in data.items() if hasattr(model, k)})
            except TypeError:
                continue
            _db.session.add(obj)
            added += 1
        _db.session.commit()
        stats[name] = added
    return stats


def list_backups() -> list:
    records = BackupRecord.query.order_by(BackupRecord.created_at.desc()).all()
    alive = []
    for rec in records:
        if (backup_dir() / rec.filename).exists():
            alive.append(rec)
    return alive


def disk_usage() -> dict:
    d = backup_dir()
    total = 0
    count = 0
    for f in d.glob("*.tar.gz"):
        total += f.stat().st_size
        count += 1
    free = shutil.disk_usage(d).free if d.exists() else 0
    return {"total_bytes": total, "count": count, "free_bytes": free,
            "total_human": _human(total), "free_human": _human(free)}


def _human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"
