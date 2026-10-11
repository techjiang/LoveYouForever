# 参与开发

欢迎提 Issue 和 PR。

## 本地跑起来

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install pytest
flask --app wsgi:app init
flask --app wsgi:app seed      # 可选：写入演示数据
python run.py
```

## 跑测试

```bash
python -m pytest tests/ -v
```

`tests/test_core.py` 覆盖了最要紧的那部分 —— 情侣关系的不可逆规则、
Markdown 安全、备份完整性、主题色标。改这几块之前先看测试。

## 代码约定

- 注释写「为什么」，不写「做了什么」。代码本身能说清楚的事不用注释。
- 中文注释，术语保留英文。
- 不引入前端构建步骤。CSS/JS 直接改，改完刷新。
- 新增依赖前先想想能不能用标准库解决。

## 目录该放哪

| 要改的东西 | 去哪 |
|---|---|
| 数据表 | `app/models/` |
| 前台页面 | `app/routes/` + `app/templates/` |
| 后台功能 | `app/admin/` + `app/templates/admin/` |
| 业务规则 | `app/services/` |
| 样式 | `app/static/css/style.css` |
| 交互 | `app/static/js/app.js` |
| 插件 | `app/plugins/` |

## 关于那两个不该动的东西

1. **全局署名** —— `app/__init__.py` 的 `POWERED_BY_HTML` 和
   `base.html` 的 `.footer-signature`。这是项目身份，别动。
2. **解绑功能** —— 不要加。这是设计。

---

**Powered by 科技酱 & LoveYouForever**
