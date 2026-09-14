# -*- coding: utf-8 -*-
"""评分引擎测试：串串房硬规则、信号词、性价比基准。"""
from house_radar.models import Listing
from house_radar.scoring import score_all


def _li(**kw):
    base = dict(platform="贝壳", house_id="x", title="普通房源", price=1500,
                area_sqm=50, unit_price=30, layout="1室1厅", orientation="南",
                tags=[], url="https://e/x")
    base.update(kw)
    return Listing(**base)


def test_hard_flag_new_decor_below_market():
    """新装修词 + 单价 < 基准75% → 疑似串串房，总分封顶55。"""
    pool = [_li(house_id=f"n{i}", title=f"小区普通房{i}", price=3000,
                area_sqm=50, unit_price=60) for i in range(6)]
    trap = _li(house_id="trap", title="精装修 首次出租 拎包入住",
               price=2000, area_sqm=100, unit_price=20)
    scored, _ = score_all(pool + [trap])
    t = next(x for x in scored if x.house_id == "trap")
    assert t.score["hard_flag"] is True
    assert t.score["total"] <= 55
    assert t.score["emoji"] == "🔴"


def test_normal_no_hard_flag():
    pool = [_li(house_id=f"n{i}", title=f"小区房{i}") for i in range(5)]
    scored, _ = score_all(pool)
    assert all(not x.score["hard_flag"] for x in scored)


def test_partition_word_penalized():
    pool = [_li(house_id=f"n{i}") for i in range(5)]
    cut = _li(house_id="cut", title="隔断单间 独立卫生")
    scored, _ = score_all(pool + [cut])
    c = next(x for x in scored if x.house_id == "cut")
    assert any("隔断" in m for m in c.score["minus"])
    normal = next(x for x in scored if x.house_id == "n0")
    assert c.score["risk"] < normal.score["risk"]


def test_subway_boosts_conv():
    pool = [_li(house_id=f"n{i}") for i in range(5)]
    metro = _li(house_id="metro", tags=["近地铁"])
    scored, _ = score_all(pool + [metro])
    m = next(x for x in scored if x.house_id == "metro")
    n = next(x for x in scored if x.house_id == "n0")
    assert m.score["conv"] > n.score["conv"]


def test_value_full_score_at_median():
    scored, _ = score_all([_li(house_id="only")])
    assert scored[0].score["value"] == 100       # 单条样本 ratio=1.0 甜蜜点
    assert 0 <= scored[0].score["total"] <= 100
