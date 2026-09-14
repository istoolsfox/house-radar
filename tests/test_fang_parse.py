# -*- coding: utf-8 -*-
"""房天下解析测试（夹具为 2026-09 真实页面裁剪）。"""
import pathlib
import sys

from house_radar.scrapers.fang import (_parse_district_nav, _parse_listing_page,
                                       mark_owner_direct)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _load(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_listing_basic():
    items = _parse_listing_page(_load("fang_list.html"), "https://zu.fang.com/cd/house/")
    assert len(items) >= 8                       # 夹具含 11 个条目段
    for x in items:
        assert x.price > 0
        assert x.url.startswith("https://zu.fang.com/cd/chuzu/")
        assert x.house_id


def test_parse_district_from_bare_text():
    """个人房源地区行区名是链接外裸文本（高新-<a>商圈</a>-<a>小区</a>），
    旧版只抓 span 会把商圈错当区名——本用例锁定该修复。"""
    items = _parse_listing_page(_load("fang_list.html"), "https://zu.fang.com/cd/house/")
    with_district = [x for x in items if x.district]
    assert with_district, "应解析出区名"
    assert all(x.district == "高新" for x in with_district)   # 夹具取自高新 a016749 页
    assert any(x.bizarea for x in items), "商圈应被解析到 bizarea 而非 district"


def test_parse_district_nav():
    d = _parse_district_nav(_load("fang_district_nav.html"), "cd")
    assert d.get("高新") == "a016749"
    assert "不限" not in d and "全部房源" not in d
    assert len(d) >= 20                          # 成都区导航 20+ 项


def test_mark_owner_direct():
    from house_radar.models import Listing
    a = Listing(platform="房天下", house_id="1")
    b = Listing(platform="房天下", house_id="2", tags=["业主直租"])
    mark_owner_direct([a, b])
    assert a.tags == ["业主直租"]
    assert b.tags == ["业主直租"]                # 不重复追加
