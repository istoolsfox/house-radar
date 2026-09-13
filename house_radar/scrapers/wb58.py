# -*- coding: utf-8 -*-
"""58同城租房抓取器（{city}.58.com/chuzu）——匿名首页约30条，作补充源。"""
import re
from urllib.parse import urljoin

from .base import get_html, new_session, clean_ws
from ..models import Listing, ScrapeResult


def _parse_listing_page(html: str, base: str) -> list:
    listings = []
    # 58 列表条目通常以 house-card / list-item 容器出现，按链接锚切
    chunks = re.split(r'(?=(?:<a[^>]+)?href="(https?://[^"]*\.58\.com/chuzu/\d+x[^"]*)")', html)
    seen = set()
    for i in range(1, len(chunks) - 1, 2):
        url = chunks[i]
        seg = chunks[i + 1] if i + 1 < len(chunks) else ""
        if url in seen:
            continue
        seen.add(url)
        seg_all = html  # 58 结构多变，用全局兜底提取
        m_title = re.search(r'title="([^"]{8,80})"', seg)
        title = clean_ws(m_title.group(1)) if m_title else ""
        if not title:
            continue
        m_price = re.search(r'class="money">\s*<b>([\d.]+)</b>', seg) or \
                  re.search(r'<b class="strongbox">([\d.]+)</b>', seg)
        if not m_price:
            continue
        price = int(float(m_price.group(1)))
        m_img = re.search(r'(?:data-original|data-src|src)="(https?://[^"]+(?:58cdn|58v5)[^"]+\.(?:jpg|png|jpeg|webp)[^"]*)"', seg, re.I)
        img = m_img.group(1) if m_img else ""

        listings.append(Listing(
            platform="58同城", house_id=url.rstrip("/").split("/")[-1],
            title=title, url=url, image=img, price=price,
        ))
    return listings


class WB58Scraper:
    name = "58同城"

    def search(self, city_slug: str, **kw) -> ScrapeResult:
        s = new_session()
        url = f"https://{city_slug}.58.com/chuzu/"
        html = get_html(s, url, mark="chuzu")
        items = _parse_listing_page(html, url) if html else []
        # 本地过滤价格（58 匿名无法 URL 筛选）
        pmin, pmax = kw.get("price_min", 0), kw.get("price_max", 0)
        if pmin or pmax:
            items = [x for x in items if (not pmin or x.price >= pmin)
                     and (not pmax or x.price <= pmax)]
        rt = kw.get("rent_type", "")
        if rt:
            items = [x for x in items if rt in x.title or rt in x.rent_type]
        return ScrapeResult(city=city_slug, platform=self.name, listings=items,
                            ok=len(items) > 0,
                            message="" if items else "58同城未返回可用数据（可能无相关房源或被限流）")
