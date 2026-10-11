"""所有模型统一出口。"""
from app.models.user import User, SiteSetting
from app.models.couple import Couple, Vow, CoupleEvent, BindToken
from app.models.content import Category, Tag, Post, Page, CustomPage
from app.models.gallery import Album, Photo
from app.models.moment import Moment, MomentComment, MomentLike
from app.models.anniversary import Anniversary, KINDS as ANNIVERSARY_KINDS
from app.models.misc import FriendLink, PluginRecord, BackupRecord
from app.models.note import Note

__all__ = [
    "User", "SiteSetting",
    "Couple", "Vow", "CoupleEvent", "BindToken",
    "Category", "Tag", "Post", "Page", "CustomPage",
    "Album", "Photo",
    "Moment", "MomentComment", "MomentLike",
    "FriendLink", "PluginRecord", "BackupRecord",
    "Note",
    "Anniversary", "ANNIVERSARY_KINDS",
]
