"""纪念日的编排逻辑。

模板里不该做日期运算，所以排序、分组、文案都在这里算完再交出去。
"""
from datetime import date, timedelta

from app.extensions import db
from app.models import Anniversary, Couple

#: 未来 N 天内算「即将到来」，首页会单独拎出来提醒
SOON_DAYS = 30


def _sorted(items: list) -> list:
    """排序规则：今天的在最前，然后按剩余天数升序；没有下一次的排最后。

    置顶的永远压在最上面，其次才轮到时间。
    """
    def key(a: Anniversary):
        left = a.days_left()
        return (
            0 if a.is_pinned else 1,
            left if left is not None else 10**6,
            a.sort_order,
            a.id,
        )

    return sorted(items, key=key)


def list_all(couple: Couple | None = None) -> list:
    q = Anniversary.query
    if couple is not None:
        q = q.filter(Anniversary.couple_id == couple.id)
    return _sorted(q.all())


def upcoming(couple: Couple | None = None, within: int = SOON_DAYS, limit: int | None = None) -> list:
    """接下来 within 天内的日子（含今天）。"""
    out = []
    for a in list_all(couple):
        left = a.days_left()
        if left is not None and left <= within:
            out.append(a)
    return out[:limit] if limit else out


def todays(couple: Couple | None = None) -> list:
    return [a for a in list_all(couple) if a.is_today]


def next_one(couple: Couple | None = None) -> Anniversary | None:
    """最近的那个未来日子，给首页倒计时用。"""
    for a in list_all(couple):
        if a.days_left() is not None and not a.is_today:
            return a
    return None


def stats(couple: Couple | None = None) -> dict:
    items = list_all(couple)
    return {
        "total": len(items),
        "today": len(todays(couple)),
        "soon": len(upcoming(couple)),
        "next": next_one(couple),
    }


def create(couple: Couple | None, title: str, anchor_on: date, **kwargs) -> Anniversary:
    a = Anniversary(
        couple_id=couple.id if couple else None,
        title=title.strip(),
        anchor_on=anchor_on,
        kind=kwargs.get("kind") or "anniversary",
        repeat_yearly=bool(kwargs.get("repeat_yearly", True)),
        owner_id=kwargs.get("owner_id"),
        note=kwargs.get("note") or "",
        icon=kwargs.get("icon") or "",
        color=kwargs.get("color") or "",
        is_pinned=bool(kwargs.get("is_pinned", False)),
        sort_order=int(kwargs.get("sort_order") or 0),
    )
    db.session.add(a)
    db.session.commit()
    return a


def seed_defaults(couple: Couple) -> None:
    """绑定成功之后，先把「在一起」这一天记下来。

    只建一次：已经有了就不动，避免覆盖用户自己的编辑。
    """
    if couple is None or Anniversary.query.filter_by(couple_id=couple.id).count() > 0:
        return
    anchor = (couple.anniversary or (couple.bound_at.date() if couple.bound_at else None))
    if not anchor:
        return
    db.session.add(
        Anniversary(
            couple_id=couple.id,
            title="我们在一起",
            anchor_on=anchor,
            kind="anniversary",
            repeat_yearly=True,
            icon="💞",
            is_pinned=True,
            note="从这里开始，一年又一年。",
        )
    )
    db.session.commit()


def humanize(a: Anniversary, today: date | None = None) -> str:
    """倒计时的中文说法。

    `today` 只在测试里传，正式渲染时走 `date.today()`。
    """
    left = a.days_left(today)
    if left is None:
        return f"已过去 {a.days_passed(today)} 天"
    if left == 0:
        return "就是今天"
    if left == 1:
        return "明天"
    if left < 30:
        return f"还有 {left} 天"
    months = round(left / 30)
    return f"还有 {left} 天 · 约 {months} 个月"
