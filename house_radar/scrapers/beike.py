# -*- coding: utf-8 -*-
"""贝壳租房抓取器（zu.ke.com）。

匿名状态只能拿首页约 30 条（筛选/翻页强制登录）；
用户在 --cookie 里提供浏览器登录态后，解锁区域/价格/翻页全量能力。
"""
import re
from urllib.parse import urljoin

from .base import get_html, new_session, clean_ws
from ..models import Listing, ScrapeResult


def _parse_cookie_string(s: str) -> dict:
    """'k1=v1; k2=v2' -> dict"""
    out = {}
    for part in (s or "").split(";"):
        if "=" in part:
            k, _, v = part.strip().partition("=")
            out[k.strip()] = v.strip()
    return out


def _parse_listing_page(html: str, base: str) -> list:
    """解析贝壳租房列表页 -> Listing 列表。"""
    listings = []
    # 按 data-house_code 切条目，规避嵌套标签干扰
    chunks = re.split(r'<div[^>]+data-house_code="([A-Z0-9]+)"', html)
    # chunks: [前文, code1, html1, code2, html2, ...]
    for i in range(1, len(chunks) - 1, 2):
        code, seg = chunks[i], chunks[i + 1]
        m_href = re.search(r'class="content__list--item--title"[^>]*>.*?href="([^"]+)"', seg, re.S) \
            or re.search(r'href="(/zufang/' + re.escape(code) + r'\.html)"', seg)
        if not m_href:
            continue
        url = urljoin(base, m_href.group(1))

        m_title = re.search(r'class="content__list--item--title"[^>]*>\s*<a[^>]*>(.*?)</a>', seg, re.S) \
            or re.search(r'title="([^"]+)"', seg)
        title = clean_ws(re.sub(r"<[^>]+>", "", m_title.group(1))) if m_title else ""

        m_img = re.search(r'data-src="([^"]+)"', seg) or re.search(r'src="(https://[^"]+ljcdn[^"]+)"', seg)
        img = (m_img.group(1) if m_img else "").split("?")[0]

        m_price = re.search(r'content__list--item-price"><em>(\d+)</em>', seg)
        price = int(m_price.group(1)) if m_price else 0
        if price <= 0:
            continue

        # 描述行：区-商圈-小区 / 面积 / 朝向 / 户型 [/ 楼层]
        m_des = re.search(r'class="content__list--item--des">(.*?)(?:content__list--item--bottom|</p>)', seg, re.S)
        district = bizarea = community = orientation = layout = floor_desc = ""
        area = 0.0
        if m_des:
            des = m_des.group(1)
            links = re.findall(r'<a[^>]*>([^<]+)</a>', des)
            if len(links) >= 3:
                district, bizarea, community = links[0], links[1], links[2]
            elif len(links) == 2:
                district, bizarea = links[0], links[1]
            elif len(links) == 1:
                district = links[0]
            parts = [clean_ws(re.sub(r"<[^>]+>", "", x)) for x in
                     re.findall(r'<i>/</i>([^<]+)', des)]
            plain = clean_ws(re.sub(r"<[^>]+>", " ", des))
            m_area = re.search(r'([\d.]+)㎡', plain)
            if m_area:
                area = float(m_area.group(1))
            tail = plain.split("㎡", 1)[1] if "㎡" in plain else ""
            tail_parts = [p.strip(" /") for p in tail.split("/") if p.strip(" /")]
            if tail_parts:
                orientation = tail_parts[0]
            if len(tail_parts) > 1:
                layout = tail_parts[1]
            m_floor = re.search(r'([\u4e00-\u9fa5]+楼层)\s*（(\d+层)）', plain)
            if m_floor:
                floor_desc = f"{m_floor.group(1)}({m_floor.group(2)})"

        tags = [clean_ws(t) for t in re.findall(
            r'class="content__item__tag[^"]*">([^<]+)</i>', seg)]
        m_brand = re.search(r'<span class="brand">\s*([^<]+?)\s*</span>', seg)
        m_time = re.search(r'content__list--item--time[^"]*">\s*([^<]+?)\s*<', seg)
        rent_type = "整租" if title.startswith("整租") else ("合租" if title.startswith("合租") else "")

        listings.append(Listing(
            platform="贝壳", house_id=code, title=title, url=url, image=img,
            price=price, unit_price=round(price / area, 2) if area else 0,
            rent_type=rent_type, district=district, bizarea=bizarea,
            community=community, area_sqm=area, orientation=orientation,
            layout=layout, floor_desc=floor_desc, tags=tags,
            brand=(clean_ws(m_brand.group(1)) if m_brand else ""),
            maintain=(clean_ws(m_time.group(1)) if m_time else ""),
            has_vr="vr-logo" in seg,
        ))
    return listings


class BeikeScraper:
    name = "贝壳"

    def __init__(self, cookie: str = ""):
        self.cookie = cookie

    def search(self, city_slug: str, price_min: int = 0, price_max: int = 0,
               districts: list = None, rent_type: str = "", max_pages: int = 3) -> ScrapeResult:
        """抓取贝壳租房。

        匿名：仅首页。带 cookie：支持价格(brp/erp query)+区域(slug)+分页(pg)。
        """
        s = new_session()
        if self.cookie:
            s.cookies.update(_parse_cookie_string(self.cookie))
        base = f"https://{city_slug}.zu.ke.com"

        # 匿名仅首页可用；带 cookie 走 rs 区名搜索 + brp/erp 价格筛选，均可 /pg{n}/ 翻页
        q = []
        if price_min:
            q.append(f"brp={price_min}")
        if price_max:
            q.append(f"erp={price_max}")
        qs = ("?" + "&".join(q)) if q else ""
        if self.cookie:
            urls = [f"{base}/zufang/rs{d}/{qs}" for d in (districts or [])] \
                or [f"{base}/zufang/{qs}"]
        else:
            urls = [f"{base}/zufang/"]

        all_l, seen = [], set()
        total = 0
        for u in urls:
            for page in range(1, max_pages + 1):
                # 匿名仅首页可用；带 cookie 时 rs 搜索路径可加 /pg{n}/ 翻页
                pu = u if page == 1 else u.rstrip("/") + f"/pg{page}/"
                html = get_html(s, pu, mark="content__list")
                if not html:
                    break
                m_total = re.search(r'data-total="(\d+)"', html)
                if m_total:
                    total = max(total, int(m_total.group(1)))
                items = _parse_listing_page(html, base)
                if not items:
                    break
                new = 0
                for it in items:
                    if it.url not in seen:
                        seen.add(it.url)
                        all_l.append(it)
                        new += 1
                if new == 0:
                    break

        return ScrapeResult(city=city_slug, platform=self.name, listings=all_l,
                            total_on_site=total,
                            ok=len(all_l) > 0,
                            message="" if all_l else "贝壳匿名状态仅能获取首页，建议提供登录 Cookie 以解锁全量")
