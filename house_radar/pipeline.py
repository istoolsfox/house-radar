# -*- coding: utf-8 -*-
"""pipeline：抓取 → 合并去重 → 评分 → 报告。"""
import io
import os
import sys
import time

def _force_utf8_stdout():
    if sys.stdout and hasattr(sys.stdout, "buffer") and \
            (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


_force_utf8_stdout()

from .models import Listing
from .scrapers.fang import FangScraper
from .scrapers.beike import BeikeScraper
from .scrapers.wb58 import WB58Scraper
from .scrapers.anjuke import AnjukeScraper
from .scoring import score_all
from .report import build_html
from . import cities


def _dedup(listings):
    """跨平台去重：同小区+同面积(±0.5㎡)+同户型 视为同一房源，保留评分补全更多的一条。"""
    out, seen = [], {}
    for x in sorted(listings, key=lambda v: -len(v.tags or [])):
        if not x.community or not x.area_sqm:
            out.append(x)
            continue
        key = (x.community, round(x.area_sqm * 2) / 2, x.layout)
        if key in seen:
            continue
        seen[key] = x
        out.append(x)
    return out


def run(city, price_min=0, price_max=0, districts=None, rent_type="",
        cookie="", owner_only=False, max_pages=2, out_dir=None, quiet=False):
    """端到端执行，返回 (报告路径, listings, 统计)。"""
    slug = cities.resolve_city(city)
    if not slug:
        raise SystemExit(f"暂不支持城市：{city}。支持：{'、'.join(cities.SUPPORTED_CITIES[:12])} 等")
    city_cn = cities.SLUG_CITY.get(slug, slug)
    districts = [d for d in (districts or []) if d]
    out_dir = out_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
    os.makedirs(out_dir, exist_ok=True)

    def log(msg):
        if not quiet:
            print(msg, flush=True)

    all_l, source_stats, failed = [], {}, []
    scrapers = [
        ("房天下", FangScraper(), dict(max_pages=max_pages, owner_only=owner_only)),
        ("贝壳", BeikeScraper(cookie=cookie), dict(max_pages=2 if cookie else 1)),
        ("安居客", AnjukeScraper(), {}),
        ("58同城", WB58Scraper(), {}),
    ]
    for name, sc, kw in scrapers:
        log(f"→ 正在抓取 {name} …")
        t0 = time.time()
        try:
            r = sc.search(slug, price_min=price_min, price_max=price_max,
                          districts=districts, rent_type=rent_type, **kw)
        except Exception as e:                       # 任何单源异常不拖垮整体
            failed.append(name)
            log(f"  ✗ {name} 异常：{str(e)[:60]}")
            continue
        dt = time.time() - t0
        if r.ok and r.listings:
            source_stats[name] = len(r.listings)
            all_l.extend(r.listings)
            log(f"  ✓ {name} {len(r.listings)} 条（{dt:.1f}s）" + (f"｜{r.message}" if r.message else ""))
        else:
            failed.append(name)
            log(f"  ✗ {name}: {r.message or '无数据'}")
        time.sleep(1.0)

    if not all_l:
        raise SystemExit("所有数据源都没有返回结果。建议：①放宽价格区间 ②换个区域 ③提供贝壳 Cookie 解锁全量。")

    # 本地兜底过滤：匿名抓的多是全城流，价格/整租合租/区域统一本地筛
    if price_min:
        all_l = [x for x in all_l if x.price >= price_min]
    if price_max:
        all_l = [x for x in all_l if x.price <= price_max]
    if rent_type:
        all_l = [x for x in all_l if rent_type in (x.rent_type or "") or rent_type in x.title]
    if districts:
        def _in_target(x):
            loc = (x.district or "") + (x.bizarea or "") + (x.community or "")
            return any(d and (d in loc or (x.district and x.district in d))
                       for d in districts)
        all_l = [x for x in all_l if _in_target(x)]
    if not all_l:
        tip = f"区间 {price_min}~{price_max}" if price_min or price_max else "当前筛选"
        if districts:
            tip += f" / 区域 {'、'.join(districts)}"
        raise SystemExit(f"过滤后无房源（{tip}）。可放宽价格或更换区域再试。")

    n0 = len(all_l)
    all_l = _dedup(all_l)
    log(f"合并去重：{n0} → {len(all_l)} 条")
    source_stats = {}
    for x in all_l:
        source_stats[x.platform] = source_stats.get(x.platform, 0) + 1

    listings, baseline = score_all(all_l, user_districts=districts, rent_type=rent_type)
    listings.sort(key=lambda x: -(x.score["total"] if x.score else 0))

    fname = f"租房雷达_{city_cn}_{time.strftime('%Y%m%d_%H%M')}.html"
    out_path = os.path.join(out_dir, fname)
    build_html(city_cn, districts, price_min, price_max, rent_type,
               listings, baseline, source_stats, out_path)

    # 数据存档：供后续对比价格走势 / 复用分析
    import json
    data_dir = os.path.join(os.path.dirname(out_dir), "data")
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, f"房源_{city_cn}_{time.strftime('%Y%m%d_%H%M')}.json"),
              "w", encoding="utf-8") as f:
        json.dump([{**x.to_dict(), "search": {"city": city_cn, "pmin": price_min,
                                              "pmax": price_max, "districts": districts}}
                   for x in listings], f, ensure_ascii=False, indent=1)

    stats = {"source": source_stats, "failed": failed, "baseline": baseline,
             "green": sum(1 for x in listings if x.score["emoji"] == "🟢"),
             "red": sum(1 for x in listings if x.score["emoji"] == "🔴"),
             "hard": sum(1 for x in listings if x.score.get("hard_flag"))}
    return out_path, listings, stats
