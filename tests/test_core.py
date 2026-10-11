"""核心行为测试。

重点覆盖「永远爱你」那套不可逆规则 —— 这是项目最不能出错的地方。
运行：python -m pytest tests/ -v
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def app(tmp_path):
    """每个测试一个独立数据库。

    配置在 create_app 之前塞进 config.json 的替代方案：直接用环境变量，
    并且用完就删掉，避免测试之间相互污染。
    """
    db_path = tmp_path / "test.db"
    os.environ["LYF_DATABASE_URI"] = f"sqlite:///{db_path}"
    os.environ["LYF_ENV"] = "development"

    # 清掉可能被上一个测试污染的模块缓存
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]

    from app import create_app

    application = create_app("development")
    application.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    yield application

    os.environ.pop("LYF_DATABASE_URI", None)
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth(app):
    with app.app_context():
        from app.extensions import db
        from app.models import User

        def make(username, **kw):
            u = User(username=username, nickname=kw.pop("nickname", username), **kw)
            u.set_password("pass1234")
            db.session.add(u)
            db.session.commit()
            return u.id

        yield make


# --------------------------------------------------------------------- 基础
def test_homepage_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "科技酱" in r.get_data(as_text=True)


def test_locked_signature_on_every_page(client):
    """全局锁定署名必须在全站底部出现。"""
    html = client.get("/").get_data(as_text=True)
    assert 'data-lyf-signature="locked"' in html
    assert "Powered by" in html
    assert 'href="https://docs.asoe.cn"' in html
    assert 'href="https://github.com/techjiang/LoveYouForever"' in html


def test_404(client):
    assert client.get("/definitely-not-here").status_code == 404


def test_api_stats(client):
    assert client.get("/api/stats").status_code == 200


# --------------------------------------------------------------------- 情侣
def test_bind_rejects_self(app, client, auth):
    """不能和自己绑定。"""
    from app.extensions import db
    from app.models import User
    from app.services import couple_service

    uid = auth("solo")
    with app.app_context():
        user = db.session.get(User, uid)
        token = couple_service.create_bind_token(user)
        with pytest.raises(couple_service.CoupleError):
            couple_service.accept_bind_token(user, token.token)


def test_bind_locks_after_complete(app, auth):
    """绑定完成后不能再发起或接受绑定。"""
    from app.extensions import db
    from app.models import User
    from app.services import couple_service

    a_id = auth("a1")
    b_id = auth("b1")
    with app.app_context():
        a = db.session.get(User, a_id)
        b = db.session.get(User, b_id)
        token = couple_service.create_bind_token(a)
        couple = couple_service.accept_bind_token(b, token.token)
        assert couple.is_complete

        assert not a.can_bind()
        assert not b.can_bind()
        with pytest.raises(couple_service.CoupleError):
            couple_service.create_bind_token(b)


def test_token_single_use(app, auth):
    """握手码只能用一次。"""
    from app.extensions import db
    from app.models import User
    from app.services import couple_service

    a_id = auth("a2")
    b_id = auth("b2")
    c_id = auth("c2")
    with app.app_context():
        a = db.session.get(User, a_id)
        b = db.session.get(User, b_id)
        c = db.session.get(User, c_id)
        token = couple_service.create_bind_token(a)
        couple_service.accept_bind_token(b, token.token)
        with pytest.raises(couple_service.CoupleError):
            couple_service.accept_bind_token(c, token.token)


def test_seal_is_irreversible(app, auth):
    """永封之后指纹可校验，成员不能再改。"""
    from app.extensions import db
    from app.models import Couple, User
    from app.services import couple_service

    a_id = auth("a3")
    b_id = auth("b3")
    with app.app_context():
        a = db.session.get(User, a_id)
        b = db.session.get(User, b_id)
        token = couple_service.create_bind_token(a)
        couple = couple_service.accept_bind_token(b, token.token)
        couple_service.seal_couple(couple, a)

        couple = Couple.query.first()
        assert couple.sealed
        assert couple.seal_hash
        assert not couple_service.detect_tamper(couple)

        # 篡改成员 -> 指纹对不上
        couple.user_b_id = None
        db.session.commit()
        assert couple_service.detect_tamper(couple)


def test_cannot_seal_incomplete(app, auth):
    from app.extensions import db
    from app.models import Couple, User
    from app.services import couple_service

    a_id = auth("a4")
    with app.app_context():
        a = db.session.get(User, a_id)
        couple = Couple(name="half", user_a_id=a.id)
        db.session.add(couple)
        db.session.commit()
        with pytest.raises(couple_service.CoupleError):
            couple_service.seal_couple(couple, a)


# --------------------------------------------------------------------- 内容
def test_markdown_love_syntax():
    from app.utils.markdown_render import render

    html = render("::love[我爱你]\n\n::vow[永不分离]\n\n::heart")
    assert 'class="lyf-love"' in html
    assert 'class="lyf-vow"' in html
    assert "lyf-heart" in html


def test_markdown_strips_script():
    from app.utils.markdown_render import render

    html = render('<script>alert("xss")</script>\n\n正文')
    assert "<script>" not in html
    assert "正文" in html


def test_reading_minutes():
    from app.utils.markdown_render import reading_minutes

    assert reading_minutes("") == 1
    assert reading_minutes("中" * 800) >= 2


def test_slugify():
    from app.utils.helpers import slugify

    assert slugify("Hello World") == "hello-world"
    assert slugify("我们的春天") == "我们的春天"
    assert slugify("") == "item"


# --------------------------------------------------------------------- 备份
def test_backup_and_verify(app):
    from app.services import backup_service

    with app.app_context():
        rec = backup_service.create_backup(kind="test", note="pytest")
        assert rec.filename.endswith(".tar.gz")
        assert rec.size_bytes > 0
        result = backup_service.verify_backup(rec.filename)
        assert result["ok"] is True


def test_export_json(app):
    from app.services import backup_service

    with app.app_context():
        payload = backup_service.export_json()
        assert "tables" in payload
        assert "SiteSetting" in payload["tables"]
        # 密码不该被导出去
        for row in payload["tables"].get("User", []):
            assert "password_hash" not in row


# --------------------------------------------------------------------- 主题
def test_theme_resolve(app):
    from app.services import theme_service

    colors = theme_service.resolve_colors("sakura")
    assert colors["primary"].startswith("#")

    overridden = theme_service.resolve_colors("sakura", {"primary": "#123456"})
    assert overridden["primary"] == "#123456"


def test_all_themes_have_required_tokens(app):
    from app.services import theme_service

    for key, theme in theme_service.all_themes().items():
        for token in theme_service.COLOR_TOKENS:
            assert token in theme["colors"], f"{key} 缺少 {token}"


# ----------------------------------------------------------------- 纪念日
def _make_anniversary(app, title, anchor, **kw):
    from app.services import anniversary_service

    with app.app_context():
        from app.models import Anniversary, Couple

        couple = Couple.query.first()
        a = anniversary_service.create(couple, title, anchor, **kw)
        return a.id


def test_yearly_anniversary_rolls_to_next_year(app):
    """每年重复的日子，过了今年就该指向明年，而不是显示负数。"""
    from datetime import date

    from app.models import Anniversary
    from app.services import anniversary_service

    with app.app_context():
        anchor = date(2020, 5, 20)
        a = anniversary_service.create(None, "周年", anchor, repeat_yearly=True)

        # 锚点当天：就是今天
        assert a.days_left(date(2026, 5, 20)) == 0
        # 锚点次日：指向明年 5/20
        assert a.days_left(date(2026, 5, 21)) == 364 or a.days_left(date(2026, 5, 21)) == 365
        # 永远是正数
        assert a.days_left(date(2030, 1, 1)) > 0
        assert a.next_date(date(2026, 5, 21)) == date(2027, 5, 20)


def test_one_off_countdown_expires(app):
    """一次性的倒数日，过了就没有下一次。"""
    from datetime import date

    from app.services import anniversary_service

    with app.app_context():
        a = anniversary_service.create(None, "领证", date(2026, 12, 31), repeat_yearly=False)
        assert a.days_left(date(2026, 12, 1)) == 30
        assert a.days_left(date(2026, 12, 31)) == 0
        assert a.days_left(date(2027, 1, 1)) is None
        assert "已过去" in anniversary_service.humanize(a, date(2027, 1, 1))


def test_leap_day_anniversary_does_not_crash(app):
    """2/29 出生的人，在平年不能被除零/值错误打死。"""
    from datetime import date

    from app.services import anniversary_service

    with app.app_context():
        a = anniversary_service.create(None, "闰日生日", date(2000, 2, 29))
        left = a.days_left(date(2026, 3, 1))
        assert left is not None and left > 0


def test_anniversary_ordering_pins_today_first(app):
    """今天的排最前，置顶其次，剩下的按天数升序。"""
    from datetime import date, timedelta

    from app.services import anniversary_service

    with app.app_context():
        today = date.today()
        anniversary_service.create(None, "很久以后", today + timedelta(days=200))
        anniversary_service.create(None, "明天", today + timedelta(days=1))
        anniversary_service.create(None, "就是今天", today)

        items = anniversary_service.list_all(None)
        assert items[0].title == "就是今天"
        assert items[1].title == "明天"

        stats = anniversary_service.stats(None)
        assert stats["today"] == 1
        assert stats["next"].title == "明天"


def test_binding_seeds_first_anniversary(app):
    """绑定之后首页不该是空的，自动记下「我们在一起」。"""
    from app.services import anniversary_service, couple_service

    with app.app_context():
        from app.extensions import db
        from app.models import User

        a = User(username="a", nickname="A")
        a.set_password("pass1234")
        b = User(username="b", nickname="B")
        b.set_password("pass1234")
        db.session.add_all([a, b])
        db.session.commit()

        token = couple_service.create_bind_token(a)
        couple = couple_service.accept_bind_token(b, token.token)

        assert couple.is_complete
        items = anniversary_service.list_all(couple)
        assert len(items) == 1
        assert items[0].title == "我们在一起"
        assert items[0].is_pinned


def test_seed_does_not_invent_partner(app):
    """默认 seed 不该凭空造一个「小可爱」出来。"""
    from app.utils.seed import seed_demo

    with app.app_context():
        from app.models import User

        # bootstrap 已经建好了默认 admin，直接拿来用
        admin = User.query.filter_by(is_admin=True).first()
        assert admin is not None

        seed_demo()  # 默认不建假人

        assert User.query.filter_by(username="partner").first() is None
        from app.models import Post

        posts = Post.query.all()
        assert posts, "演示文章还是应该写入"
        assert all(p.author_id == admin.id for p in posts)


def test_homepage_never_leaks_anniversaries(app, client):
    """首页是公开的，纪念日只属于两个人，不该出现在门外。"""
    from datetime import date, timedelta

    from app.extensions import db
    from app.models import Couple, User
    from app.services import anniversary_service

    with app.app_context():
        u = User(username="solo", nickname="Solo")
        u.set_password("pass1234")
        db.session.add(u)
        db.session.commit()
        c = Couple(name="我们")
        db.session.add(c)
        db.session.commit()
        anniversary_service.create(c, "她的生日", date.today() + timedelta(days=9))

    html = client.get("/").get_data(as_text=True)
    assert "她的生日" not in html
    assert "值得数着的日子" not in html


def test_homepage_has_no_setup_wizard(app, client):
    """首页不是安装向导：空站就说空站，别教人改密码、别催人绑定。"""
    html = client.get("/").get_data(as_text=True)
    assert "改掉默认密码" not in html
    assert "和对方绑定" not in html
    assert "还没有文章" in html


def test_homepage_does_not_pretend_a_couple(app, client):
    """没有另一半的时候，首页不该摆出「我们的小站」这种不存在的戏。"""
    html = client.get("/").get_data(as_text=True)
    assert "我们的小站" not in html
    assert "天相伴" not in html
