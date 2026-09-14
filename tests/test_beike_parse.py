# -*- coding: utf-8 -*-
"""贝壳解析测试（夹具为 2026-09 真实页面裁剪 + 合成导航）。"""
import pathlib

from house_radar.scrapers.beike import (_parse_district_nav, _parse_listing_page,
                                        _price_segments)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

HZ_NAV = """
<a href="/zufang/xiaoshanqu/">萧山区</a>
<a href="/zufang/binjiangqu/">滨江区</a>
<a href="/zufang/xihuqu4/">西湖区</a>
<a href="/zufang/ab200306001917/">宅一起新青年社区</a>
<a href="/zufang/c1811053667858/">同城印象花苑西区</a>
<a href="/zufang/">不限</a>
"""


def test_parse_listing_basic():
    items = _parse_listing_page(FIXTURES.joinpath("beike_list.html").read_text(encoding="utf-8"),
                                "https://hz.zu.ke.com")
    assert 4 <= len(items) <= 6                  # 夹具含 6 个条目标记，末个可能截断
    for x in items:
        assert x.price > 0
        assert x.house_id
        assert x.title
        if x.url:
            assert x.url.startswith("https://hz.zu.ke.com/zufang/")


def test_parse_district_nav_excludes_brand():
    d = _parse_district_nav(HZ_NAV)
    assert d["萧山区"] == "xiaoshanqu"
    assert d["滨江区"] == "binjiangqu"
    assert d["西湖区"] == "xihuqu4"              # 数字尾缀 slug 不丢
    assert "宅一起新青年社区" not in d            # 品牌公寓以"区"结尾，靠长度排除
    assert "同城印象花苑西区" not in d
    assert "不限" not in d


def test_price_segments():
    assert _price_segments(1000, 1700) == ["rp2", "rp3"]
    assert _price_segments(0, 0) == []
    assert _price_segments(500, 900) == ["rp1"]
    assert _price_segments(3000, 8000) == ["rp5", "rp6", "rp7"]
    assert _price_segments(20000, 30000) == ["rp8"]
