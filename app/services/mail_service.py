"""邮件发送：纪念日提醒用。

这个站没有后台常驻进程，所以不做「定时推送」—— 那需要引入定时器依赖，
对一个两个人的站来说是杀鸡用牛刀。改成：

- 谁访问前台，就顺手判断一下今天该不该发提醒（每天最多发一次，记在设置里）；
- 命令行 `flask remind` 也能手动触发，配 crontab 就是定时提醒。

没配 SMTP 就什么都不做，只在体检里提醒一句「想收提醒就去配一下」。
"""
import smtplib
from email.header import Header
from email.mime.text import MIMEText

from flask import current_app

from app.extensions import db
from app.models import SiteSetting
from app.models.mixins import utcnow

#: 每类提醒每天只发一次的标记
_SENT_KEY = "reminder_sent_on"


def is_configured() -> bool:
    cfg = current_app.config
    return bool(cfg.get("MAIL_SERVER") and cfg.get("MAIL_USERNAME"))


def send(to: str, subject: str, body: str, html: str = "") -> bool:
    """发一封信。没配 SMTP 就返回 False，不抛异常 —— 提醒失败不该影响站点。"""
    if not is_configured():
        return False
    if not to:
        return False

    cfg = current_app.config
    sender = cfg.get("MAIL_SENDER") or cfg.get("MAIL_USERNAME")
    msg = MIMEText(html or body, "html" if html else "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = sender
    msg["To"] = to

    try:
        if cfg.get("MAIL_USE_SSL"):
            server = smtplib.SMTP_SSL(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=10)
        else:
            server = smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=10)
            server.starttls()
        with server:
            server.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
            server.sendmail(sender, [to], msg.as_string())
        return True
    except Exception as exc:  # 网络/账号问题都算发信失败，站点继续跑
        current_app.logger.warning("纪念日提醒发送失败: %s", exc)
        return False


def recipients() -> list:
    """收件人：后台配的地址，没配就用两个人的邮箱。"""
    configured = (current_app.config.get("MAIL_TO") or "").strip()
    if configured:
        return [x.strip() for x in configured.replace(";", ",").split(",") if x.strip()]

    from app.models import Couple

    couple = Couple.query.first()
    if couple is None:
        return []
    return [m.email for m in couple.members if m.email]


def build_digest(couple, items: list) -> tuple[str, str, str]:
    """把「今天/明天/三天内」的事拼成一封通读的信。"""
    from app.services import anniversary_service

    site = SiteSetting.get("site_name", "永远爱你")
    lines = []
    titles = []
    for a in items:
        human = anniversary_service.humanize(a)
        lines.append(f"{a.icon or '💞'} {a.title} —— {human}")
        titles.append(a.title)

    if not titles:
        return "", "", ""

    subject = f"「{site}」忘了不要紧：{'、'.join(titles[:2])}"
    body = "\n".join(lines) + "\n\n—— 永远爱你"
    html = (
        "<div style='font-family:-apple-system,Segoe UI,sans-serif;line-height:1.9'>"
        f"<p style='color:#8a7f88;font-size:13px'>{site} · 日子提醒</p>"
        + "".join(f"<p style='font-size:16px;margin:6px 0'>{x}</p>" for x in lines)
        + "<p style='color:#8a7f88;font-size:13px;margin-top:18px'>Powered by 科技酱 &amp; LoveYouForever</p>"
        "</div>"
    )
    return subject, body, html


def due_items(couple, days: int = 3) -> list:
    """今天、明天、未来 N 天内（含已经过去的今天）该提醒的日子。"""
    from app.services import anniversary_service

    out = []
    for a in anniversary_service.list_all(couple):
        left = a.days_left()
        if left is not None and left <= days:
            out.append(a)
    return out


def maybe_send_daily(couple) -> bool:
    """每天最多发一次。返回 True 表示这次真的发出去了。"""
    if couple is None or not is_configured():
        return False
    today = utcnow().date().isoformat()
    if SiteSetting.get(_SENT_KEY) == today:
        return False
    items = due_items(couple)
    if not items:
        SiteSetting.set(_SENT_KEY, today)
        db.session.commit()
        return False

    subject, body, html = build_digest(couple, items)
    sent = any(send(to, subject, body, html) for to in recipients())
    SiteSetting.set(_SENT_KEY, today)
    db.session.commit()
    return sent


def send_test(to: str = "") -> bool:
    """后台「发一封试试」用。"""
    targets = [to] if to else recipients()
    if not targets:
        return False
    site = SiteSetting.get("site_name", "永远爱你")
    subject = f"「{site}」邮件提醒已就绪"
    body = "这一封是测试信。以后重要的日子到了，这里会提醒你。"
    html = (
        "<div style='font-family:-apple-system,Segoe UI,sans-serif;line-height:1.9'>"
        f"<p>{body}</p>"
        "<p style='color:#8a7f88;font-size:13px'>Powered by 科技酱 &amp; LoveYouForever</p></div>"
    )
    return any(send(t, subject, body, html) for t in targets)
