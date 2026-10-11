"""运行时配置。

配置优先从环境变量读取，其次从 instance/config.json 读取（安装脚本会写它），
最后回落到这里的默认值。这样小白用户也能靠 install.sh 一把梭。
"""
import json
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
CONFIG_FILE = INSTANCE_DIR / "config.json"


def _load_file_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _secret_key() -> str:
    """密钥落盘保存，避免每次重启都让所有人掉登录。"""
    env = os.environ.get("LYF_SECRET_KEY")
    if env:
        return env
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    key_file = INSTANCE_DIR / "secret_key"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    key = secrets.token_urlsafe(48)
    key_file.write_text(key, encoding="utf-8")
    key_file.chmod(0o600)
    return key


class Config:
    file_config = _load_file_config()

    SECRET_KEY = _secret_key()
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "LYF_DATABASE_URI",
        file_config.get("database_uri", f"sqlite:///{INSTANCE_DIR / 'loveyouforever.db'}"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    SITE_NAME = os.environ.get("LYF_SITE_NAME", file_config.get("site_name", "永远爱你"))

    # 上传
    UPLOAD_FOLDER = str(BASE_DIR / "app" / "static" / "uploads")
    MAX_CONTENT_LENGTH = int(os.environ.get("LYF_MAX_UPLOAD_MB", "32")) * 1024 * 1024
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg", "avif"}

    # 备份
    BACKUP_FOLDER = str(BASE_DIR / "backups")
    BACKUP_KEEP = int(os.environ.get("LYF_BACKUP_KEEP", "30"))

    # 会话
    REMEMBER_COOKIE_DURATION = 60 * 60 * 24 * 30
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 14

    # 默认语言/时区
    TIMEZONE = os.environ.get("LYF_TIMEZONE", "Asia/Shanghai")

    @classmethod
    def get(cls, key: str, default=None):
        return getattr(cls, key, default)


class DevelopmentConfig(Config):
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True


class ProductionConfig(Config):
    DEBUG = False


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
