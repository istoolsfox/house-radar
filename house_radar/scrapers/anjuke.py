# -*- coding: utf-8 -*-
"""安居客租房抓取器（{city}.zu.anjuke.com）。

安居客反爬强：首次访问可能给全量页，随后返回 700 字节空壳软墙。
本抓取器尽力而为，被软墙时静默返回失败，不影响其他源。
"""
import re
from urllib.parse import urljoin

from .base import get_html, new_session, clean_ws
from ..models import Listing, ScrapeResult

# 安居客价格段枚举（从导航实测）：zj201~208
ZJ_SEGMENTS = [
    (0, 500, "zj201"), (500, 800, "zj202"), (800, 1000, "zj203"),
    (1000, 1500, "zj204"), (1500, 2000, "zj205"), (2000, 3000, "zj206"),
    (3000, 5000, "zj207"), (5000, 10 ** 9, "zj208"),
]


def _price_segments(pmin: int, pmax: int) -> list:
    """用户区间覆盖到的价格段代码。"""
    if not pmin and not pmax:
        return []
    segs = []
    for lo, hi, code in ZJ_SEGMENTS:
        if hi > pmin and lo < pmax:
            segs.append(code)
    return segs or ["zj204"]


def _parse_listing_page(html: str, base: str) -> list:
    listings = []
    chunks = re.split(r'<div[^>]+class="zu-itemmod[^"]*"[^>]*>', html)
    for seg in chunks[1:]:
        m_href = re.search(r'href="(https?://[^"]*anjuke\.com/fangyuan/[^"]+)"', seg) \
            or re.search(r'href="(/fangyuan/\d+[^"]*)"', seg)
        if not m_href:
            continue
        url = urljoin(base, m_href.group(1))
        m_title = re.search(r'<h3[^>]*>\s*<a[^>]*>(.*?)</a>', seg, re.S) \
            or re.search(r'title="([^"]{8,80})"', seg)
        title = clean_ws(re.sub(r"<[^>]+>", "", m_title.group(1))) if m_title else ""
        m_price = re.search(r'<b[^>]*>(\d+)</b>\s*<span[^>]*>元', seg) \
            or re.search(r'class="price">\s*<b>(\d+)</b>', seg)
        if not (title and m_price):
            continue
        m_img = re.search(r'(?:data-src|data-original|src)="(https?://[^"]+(?:ajkimg|pic)[^"]+)"', seg)
        m_details = re.search(r'class="details-item[^"]*"[^>]*>(.*?)</p>', seg, re.S)
        district = bizarea = ""
        if m_details:
            names = re.findall(r"<span>([^<]{1,12})</span>", m_details.group(1))
            if names:
                district = names[0]
            if len(names) > 1:
                bizarea = names[1]
        listings.append(Listing(
            platform="安居客", house_id=url.rstrip("/").split("/")[-1].split("?")[0],
            title=title, url=url, image=m_img.group(1) if m_img else "",
            price=int(m_price.group(1)), district=district, bizarea=bizarea,
        ))
    return listings


class AnjukeScraper:
    name = "安居客"

    def search(self, city_slug: str, price_min: int = 0, price_max: int = 0,
               districts: list = None, max_pages: int = 1, **kw) -> ScrapeResult:
        s = new_session()
        root = f"https://{city_slug}.zu.anjuke.com"
        segs = []
        zj = _price_segments(price_min, price_max)
        if zj and len(zj) <= 2:          # 段太多时 URL 组合复杂，交给本地过滤
            segs.extend(zj)
        if districts:
            import urllib.parse
            segs.append("g" + urllib.parse.quote(districts[0]))  # 安居客区域为拼音，兜底由本地过滤
        path = "/fangyuan/" + ("/".join(segs) + "/" if segs else "")
        all_l, seen = [], set()
        for page in range(1, max_pages + 1):
            u = root + (path if page == 1 else path.rstrip("/") + f"/p{page}/")
            html = get_html(s, u, mark="fangyuan", retries=2)
            if not html:
                break
            items = _parse_listing_page(html, root)
            if not items:
                break
            for it in items:
                if it.url not in seen:
                    seen.add(it.url)
                    all_l.append(it)
        # 本地精确过滤
        if price_min:
            all_l = [x for x in all_l if x.price >= price_min]
        if price_max:
            all_l = [x for x in all_l if x.price <= price_max]
        if districts:
            all_l = [x for x in all_l
                     if any(d and (d in x.district + x.bizarea or x.district in d)
                            for d in districts)]
        return ScrapeResult(city=city_slug, platform=self.name, listings=all_l,
                            ok=len(all_l) > 0,
                            message="" if all_l else "安居客触发反爬软墙（正常现象，已跳过该源）")
