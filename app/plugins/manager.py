"""插件管理器：扫描、加载、启停、派发钩子。"""
from __future__ import annotations

import importlib
import json
import pkgutil
from pathlib import Path

from flask import Blueprint, current_app

from app.extensions import db
from app.models import PluginRecord
from app.plugins.base import Plugin


class PluginManager:
    def __init__(self):
        self.plugins: dict[str, Plugin] = {}
        self._loaded = False
        self._rendering_footer = False

    # ---- 发现 ----
    def discover(self) -> dict:
        """扫描 app/plugins 目录下的模块，找出定义了 PLUGIN 的。"""
        found = {}
        pkg_dir = Path(__file__).resolve().parent
        for mod in pkgutil.iter_modules([str(pkg_dir)]):
            if mod.name.startswith("_") or mod.name in {"base", "manager"}:
                continue
            try:
                module = importlib.import_module(f"app.plugins.{mod.name}")
            except Exception as exc:  # 插件坏了不能拖垮整站
                current_app.logger.warning("插件 %s 加载失败: %s", mod.name, exc)
                continue
            inst = getattr(module, "PLUGIN", None)
            if isinstance(inst, Plugin):
                inst.name = inst.name if inst.name != "unnamed" else mod.name
                found[inst.name] = inst
        return found

    # ---- 启动时加载已启用的插件 ----
    def bootstrap(self, app):
        self._loaded = True
        found = self.discover()
        enabled = {r.name: r for r in PluginRecord.query.all()}

        for name, plugin in found.items():
            plugin.app = app
            record = enabled.get(name)
            if record is None:
                record = PluginRecord(
                    name=name,
                    version=plugin.version,
                    enabled=False,
                    author=plugin.author,
                    description=plugin.description,
                    config_json="{}",
                )
                db.session.add(record)
                db.session.commit()
            else:
                record.version = plugin.version
                record.description = plugin.description
                record.author = plugin.author
                db.session.commit()

            plugin.configure(json.loads(record.config_json or "{}"))
            if record.enabled:
                self._activate(plugin)

        app.extensions["lyf_plugins"] = self
        return self.plugins

    def _activate(self, plugin: Plugin):
        app = current_app
        bp = plugin.register_blueprint()
        if isinstance(bp, Blueprint):
            if bp.name not in app.blueprints:
                app.register_blueprint(bp)
        try:
            plugin.on_enable(ctx={"app": app})
        except Exception as exc:
            app.logger.warning("插件 %s on_enable 出错: %s", plugin.name, exc)
        self.plugins[plugin.name] = plugin

    # ---- 后台操作 ----
    def enable(self, name: str) -> bool:
        found = self.discover()
        plugin = found.get(name)
        if plugin is None:
            return False
        record = PluginRecord.query.filter_by(name=name).first()
        if record is None:
            record = PluginRecord(name=name, version=plugin.version)
            db.session.add(record)
        record.enabled = True
        plugin.configure(json.loads(record.config_json or "{}"))
        db.session.commit()
        try:
            plugin.on_install(ctx={})
        except Exception:
            pass
        return True

    def disable(self, name: str) -> bool:
        record = PluginRecord.query.filter_by(name=name).first()
        if record is None:
            return False
        record.enabled = False
        db.session.commit()
        plugin = self.plugins.pop(name, None)
        if plugin:
            try:
                plugin.on_disable(ctx={})
            except Exception:
                pass
        return True

    def save_config(self, name: str, config: dict) -> bool:
        record = PluginRecord.query.filter_by(name=name).first()
        if record is None:
            return False
        record.config_json = json.dumps(config or {}, ensure_ascii=False)
        db.session.commit()
        if name in self.plugins:
            self.plugins[name].configure(config or {})
        return True

    # ---- 钩子派发 ----
    def dispatch_post_render(self, post, html: str) -> str:
        for plugin in self.plugins.values():
            try:
                html = plugin.on_post_render(post, html) or html
            except Exception as exc:
                current_app.logger.warning("插件 %s 渲染 Hook 出错: %s", plugin.name, exc)
        return html

    def collect_nav_items(self) -> list:
        items = []
        for plugin in self.plugins.values():
            try:
                items.extend(plugin.nav_items() or [])
            except Exception:
                pass
        return items

    def collect_footer_html(self) -> str:
        """收集插件页脚片段。

        加了个重入锁：footer_html 有可能间接触发模板渲染，
        没有这个锁的话上下文处理器会自己调自己，直接栈溢出。
        """
        if self._rendering_footer:
            return ""
        self._rendering_footer = True
        try:
            chunks = []
            for plugin in self.plugins.values():
                try:
                    html = plugin.footer_html()
                    if html:
                        chunks.append(html)
                except Exception:
                    pass
            return "\n".join(chunks)
        finally:
            self._rendering_footer = False

    def collect_dashboard_cards(self, ctx: dict) -> list:
        cards = []
        for plugin in self.plugins.values():
            try:
                cards.extend(plugin.dashboard_cards(ctx) or [])
            except Exception:
                pass
        return cards


manager = PluginManager()
