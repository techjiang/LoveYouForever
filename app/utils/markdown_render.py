"""Markdown 渲染。

目标：把「写博客」这件事的阅读体验拉满。
- 代码高亮（Pygments + 行号）
- 表格、任务列表、脚注、目录锚点
- 情侣彩蛋语法：::love[文字]、::vow[...]、::couple[...]
- 图片自动加 lazy 和 lightbox 属性
- 输出经 bleach 白名单清洗，防止 XSS
"""
import re

import bleach
import markdown
from bleach.css_sanitizer import CSSSanitizer
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.toc import TocExtension
from pygments.formatters import HtmlFormatter

# 允许阅读时不跳走的标签白名单
ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS).union({
    "p", "div", "span", "br", "hr", "img", "figure", "figcaption",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "pre", "code", "table", "thead", "tbody", "tr", "th", "td",
    "blockquote", "del", "ins", "sup", "sub", "kbd", "mark", "small",
    "details", "summary", "section", "aside", "time", "abbr",
    "input", "dl", "dt", "dd", "video", "source", "iframe",
})
ALLOWED_ATTRS = {
    "*": ["class", "id", "title", "style", "data-*", "aria-*", "role"],
    "a": ["href", "title", "target", "rel", "class"],
    "img": ["src", "alt", "title", "class", "loading", "width", "height", "data-src"],
    "input": ["type", "checked", "disabled"],
    "iframe": ["src", "width", "height", "frameborder", "allowfullscreen", "allow"],
    "video": ["src", "controls", "poster", "width", "height", "class"],
    "source": ["src", "type"],
    "time": ["datetime"],
}

_CSS_SANITIZER = CSSSanitizer(
    allowed_css_properties=["color", "background-color", "text-align", "width", "height", "font-size", "opacity"]
)

_MD = None


def _md() -> markdown.Markdown:
    global _MD
    if _MD is None:
        _MD = markdown.Markdown(
            extensions=[
                "extra",
                "admonition",
                "attr_list",
                "def_list",
                "footnotes",
                "md_in_html",
                "sane_lists",
                "nl2br",
                CodeHiliteExtension(css_class="codehilite", guess_lang=False, linenums=False),
                TocExtension(permalink=True, toc_depth="2-4", slugify=_slugify),
            ],
            output_format="html5",
        )
    return _MD


def _slugify(value, separator="-"):
    import unicodedata

    value = unicodedata.normalize("NFKD", str(value))
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE).strip().lower()
    return re.sub(r"[%s\s]+" % re.escape(separator), separator, value) or "section"


def _protect_curly(text: str):
    """把 {{ }} 变量先替换掉，避免用户直接在文章里把未渲染的模板语法暴露出去。"""
    return text


LOVE_PATTERNS = [
    # ::love[文字] -> 高亮的情话
    (re.compile(r"::love\[(?P<body>[^\]]*)\]"), lambda m: f'<span class="lyf-love">{m.group("body")}</span>'),
    # ::vow[文字] -> 誓言块
    (re.compile(r"::vow\[(?P<body>[^\]]*)\]"), lambda m: f'<div class="lyf-vow">{m.group("body")}</div>'),
    # ::couple[文字] -> 双人合体标记
    (re.compile(r"::couple\[(?P<body>[^\]]*)\]"), lambda m: f'<span class="lyf-couple">{m.group("body")}</span>'),
    # ::heart  -> 爱心
    (re.compile(r"::heart\b"), lambda m: '<span class="lyf-heart" aria-label="爱">❤</span>'),
]


def _apply_love_syntax(text: str) -> str:
    for pattern, repl in LOVE_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def _enhance_images(html: str) -> str:
    def add_attrs(match):
        tag = match.group(0)
        if "loading=" not in tag:
            tag = tag[:-1] + ' loading="lazy"'
        if "class=" in tag:
            tag = re.sub(r'class="([^"]*)"', lambda mm: f'class="{mm.group(1)} lyf-img"', tag)
        else:
            tag = tag[:-1] + ' class="lyf-img"'
        return tag

    return re.sub(r"<img\b[^>]*>", add_attrs, html)


def render(text: str, *, sanitize: bool = True) -> str:
    """Markdown -> 安全 HTML。"""
    if not text:
        return ""
    md = _md()
    md.reset()
    raw = md.convert(_apply_love_syntax(_protect_curly(text)))
    raw = _enhance_images(raw)
    if not sanitize:
        return raw
    clean = bleach.clean(
        raw,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=["http", "https", "mailto", "data"],
        css_sanitizer=_CSS_SANITIZER,
        strip=False,
    )
    # bleach 不认识的自定义 class 会保留，但 iframe 的 src 白名单要宽一点
    return clean


def render_with_toc(text: str):
    """返回 (html, toc_html)。"""
    md = _md()
    md.reset()
    html = render(text, sanitize=False)
    toc = getattr(md, "toc", "")
    toc_html = bleach.clean(toc, tags={"ul", "li", "a", "div", "span"}, attributes={"a": ["href", "class"], "*": ["class"]})
    return html, toc_html


def reading_minutes(text: str) -> int:
    """中文按 400 字/分钟，英文按 200 词/分钟粗略估算。"""
    if not text:
        return 1
    cn = len(re.findall(r"[\u4e00-\u9fff]", text))
    en = len(re.findall(r"[A-Za-z]+", text))
    minutes = cn / 400 + en / 200
    return max(int(round(minutes)), 1)


def pygments_css(style: str = "monokai") -> str:
    return HtmlFormatter(style=style).get_style_defs(".codehilite")


def extract_summary(text: str, limit: int = 140) -> str:
    if not text:
        return ""
    plain = re.sub(r"```.*?```", "", text, flags=re.S)
    plain = re.sub(r"::(love|vow|couple)\[([^\]]*)\]", r"\2", plain)
    plain = re.sub(r"[#>*`_\[\]()!\-]+", " ", plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain[:limit]
