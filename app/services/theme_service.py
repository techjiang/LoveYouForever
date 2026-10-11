"""主题与配色。

设计上把所有颜色收敛成一组 CSS 变量，主题只是一个 JSON 文件。
用户既可以在后台选预设，也可以自己调色，还能存成自己的主题。
"""
import json
from pathlib import Path

from flask import current_app

THEME_DIR = Path(__file__).resolve().parent.parent.parent / "themes"

#: 变量名 -> 中文说明，后台配色面板按这个渲染
COLOR_TOKENS = {
    "primary": "主色（按钮、链接、强调）",
    "primary_soft": "主色浅底",
    "accent": "点缀色（爱心、标签）",
    "bg": "页面背景",
    "surface": "卡片背景",
    "surface_alt": "次级卡片背景",
    "text": "正文颜色",
    "text_muted": "次要文字",
    "border": "描边颜色",
    "hero_from": "首屏渐变起始色",
    "hero_to": "首屏渐变结束色",
}

DEFAULT_LIGHT = {
    "primary": "#ff5c8a",
    "primary_soft": "#ffe8ef",
    "accent": "#ff9f43",
    "bg": "#fff8fa",
    "surface": "#ffffff",
    "surface_alt": "#fff1f5",
    "text": "#2c2430",
    "text_muted": "#8a7f88",
    "border": "#f2d9e2",
    "hero_from": "#ff8fb1",
    "hero_to": "#ff5c8a",
}

DEFAULT_DARK = {
    "primary": "#ff7aa2",
    "primary_soft": "#3a2029",
    "accent": "#ffb057",
    "bg": "#17121a",
    "surface": "#211a26",
    "surface_alt": "#2a2130",
    "text": "#f3ecf1",
    "text_muted": "#a89aa6",
    "border": "#3a2f42",
    "hero_from": "#4a1f33",
    "hero_to": "#2a1420",
}

BUILTIN_THEMES = {
    "sakura": {
        "title": "樱花粉",
        "description": "经典情侣粉，甜而不腻",
        "mode": "light",
        "colors": DEFAULT_LIGHT,
    },
    "midnight": {
        "title": "午夜玫瑰",
        "description": "深色模式，晚上看不刺眼",
        "mode": "dark",
        "colors": DEFAULT_DARK,
    },
    "ocean": {
        "title": "深海蓝",
        "description": "冷静克制，适合长文阅读",
        "mode": "light",
        "colors": {
            **DEFAULT_LIGHT,
            "primary": "#3d7dff",
            "primary_soft": "#e6efff",
            "accent": "#22c1c3",
            "bg": "#f6f9ff",
            "surface_alt": "#eef4ff",
            "border": "#d9e4fb",
            "hero_from": "#7fb0ff",
            "hero_to": "#3d7dff",
        },
    },
    "matcha": {
        "title": "抹茶绿",
        "description": "清爽自然，像春天",
        "mode": "light",
        "colors": {
            **DEFAULT_LIGHT,
            "primary": "#3fae7a",
            "primary_soft": "#e6f7ee",
            "accent": "#f0a63c",
            "bg": "#f5fbf7",
            "surface_alt": "#ecf7f1",
            "border": "#d5ecdf",
            "hero_from": "#8fd9b4",
            "hero_to": "#3fae7a",
        },
    },
    "sunset": {
        "title": "落日橘",
        "description": "温暖的黄昏色调",
        "mode": "light",
        "colors": {
            **DEFAULT_LIGHT,
            "primary": "#ff7043",
            "primary_soft": "#ffeee6",
            "accent": "#ffc107",
            "bg": "#fff9f5",
            "surface_alt": "#fff1e8",
            "border": "#f8dfd0",
            "hero_from": "#ffb08a",
            "hero_to": "#ff7043",
        },
    },
    "lavender": {
        "title": "薰衣草",
        "description": "淡紫，安静又浪漫",
        "mode": "light",
        "colors": {
            **DEFAULT_LIGHT,
            "primary": "#8b6cf0",
            "primary_soft": "#efeaff",
            "accent": "#ff8fb1",
            "bg": "#f9f7ff",
            "surface_alt": "#f2efff",
            "border": "#e2daf8",
            "hero_from": "#b9a5ff",
            "hero_to": "#8b6cf0",
        },
    },
}


def load_user_themes() -> dict:
    themes = {}
    if not THEME_DIR.exists():
        return themes
    for f in THEME_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            themes[f.stem] = data
        except (json.JSONDecodeError, OSError):
            continue
    return themes


def all_themes() -> dict:
    out = dict(BUILTIN_THEMES)
    out.update(load_user_themes())
    return out


def get_theme(key: str) -> dict:
    themes = all_themes()
    return themes.get(key) or themes["sakura"]


def save_theme(key: str, data: dict) -> Path:
    THEME_DIR.mkdir(parents=True, exist_ok=True)
    path = THEME_DIR / f"{key}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def delete_theme(key: str) -> bool:
    path = THEME_DIR / f"{key}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def css_variables(colors: dict) -> str:
    lines = [":root {"]
    for token, value in colors.items():
        lines.append(f"  --lyf-{token.replace('_', '-')}: {value};")
    lines.append("}")
    return "\n".join(lines)


def resolve_colors(theme_key: str, overrides: dict | None = None) -> dict:
    theme = get_theme(theme_key)
    colors = dict(theme.get("colors") or DEFAULT_LIGHT)
    if overrides:
        for k, v in overrides.items():
            if k in COLOR_TOKENS and v:
                colors[k] = v
    return colors
