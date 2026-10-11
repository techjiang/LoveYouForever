"""首页寄语的取用规则。

只有一条要紧的：**每天只露一条脸**。
两个人各贴一句，如果全堆上首页，那块地方就变成公告栏了。
"""
from app.extensions import db
from app.models import DailyWish
from app.models.mixins import utcnow


def current() -> DailyWish | None:
    """今天首页该显示的那条。

    优先今天的；今天没人贴，就退回最近一条 —— 门口一直空着也不好看。
    """
    today = utcnow().date()
    today_items = (
        DailyWish.query.filter(DailyWish.is_public.is_(True))
        .filter(db.func.date(DailyWish.created_at) == today.isoformat())
        .order_by(DailyWish.created_at.desc())
        .all()
    )
    if today_items:
        return today_items[0]
    return (
        DailyWish.query.filter(DailyWish.is_public.is_(True))
        .order_by(DailyWish.created_at.desc())
        .first()
    )


def recent(limit: int = 12) -> list:
    return (
        DailyWish.query.order_by(DailyWish.created_at.desc())
        .limit(limit)
        .all()
    )


def post(user, content: str, mood: str = "sweet") -> DailyWish | None:
    content = (content or "").strip()
    if not content:
        return None
    wish = DailyWish(content=content[:280], mood=mood or "sweet", author_id=user.id)
    db.session.add(wish)
    db.session.commit()
    return wish


def delete(wish_id: int) -> bool:
    wish = db.session.get(DailyWish, wish_id)
    if wish is None:
        return False
    db.session.delete(wish)
    db.session.commit()
    return True


def is_today(wish: DailyWish | None) -> bool:
    if wish is None:
        return False
    return wish.created_at.date() == utcnow().date()
