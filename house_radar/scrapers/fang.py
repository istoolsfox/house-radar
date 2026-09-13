# -*- coding: utf-8 -*-
"""房天下租房抓取器（zu.fang.com）——匿名全功能主力源。

URL 规律（实测）：
  城市页   https://zu.fang.com/{slug}/house/
  自定义价格 c2{min}-d2{max}（min=0 写 c20）
  区域     a{区代码}[-b{商圈代码}]（区域列表从城市页导航解析）
  整租     n3-100   户型 g2{1..5}  个人房源 a21
  分页     i3{页码}
多段以 - 连接，顺序宽容。
"""
import re
from urllib.parse import urljoin

from .base import get_html, new_session, clean_ws
from ..models import Listing, ScrapeResult


def fetch_districts(city_slug: str) -> dict:
    """解析城市页导航，返回 {区中文名: a代码}。"""
    s = new_session()
    html = get_html(s, f"https://zu.fang.com/{city_slug}/house/", mark="house")
    out = {}
    if html:
        for code, name in re.findall(
                r'href="(?:https?://zu\.fang\.com)?/' + city_slug +
                r'/house/(a\d+)/"[^>]*>([^<]{1,10})<', html):
            name = clean_ws(name)
            if name and name not in ("不限", "全部房源") and code not in out:
                out[name] = code
    return out


def _https(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    return url


def _parse_listing_page(html: str, base: str) -> list:
    """解析房天下列表页 -> Listing 列表。"""
    listings = []
    chunks = re.split(r'<dl class="list[^"]*"[^>]*>', html)
    for seg in chunks[1:]:
        m_href = re.search(r'href="(/[^"]+?/chuzu/[^"]+?\.htm)"', seg)
        if not m_href:
            continue
        url = urljoin("https://zu.fang.com", m_href.group(1))

        m_title = re.search(r'class="title"[^>]*>\s*<a[^>]*title="([^"]+)"', seg)
        title = clean_ws(m_title.group(1)) if m_title else ""

        m_img = re.search(r'data-original="([^"]+)"', seg)
        img = _https(m_img.group(1)).split("?")[0] if m_img else ""

        m_price = re.search(r'class="price">(\d+)</span>', seg)
        price = int(m_price.group(1)) if m_price else 0
        if price <= 0:
            continue

        # 信息行：整租|3室2厅|105㎡|朝南北
        m_info = re.search(r'class="font15[^"]*"[^>]*>(.*?)</p>', seg, re.S)
        rent_type = layout = orientation = ""
        area = 0.0
        if m_info:
            info = clean_ws(re.sub(r"<[^>]+>", "|", m_info.group(1)))
            parts = [p for p in info.split("|") if p.strip()]
            if parts:
                rent_type = parts[0].strip()
            for p in parts:
                m_a = re.match(r"([\d.]+)㎡", p.strip())
                if m_a:
                    area = float(m_a.group(1))
                elif "室" in p and "厅" in p:
                    layout = p.strip()
                elif ("朝" in p or p.strip() in ("南北", "东西", "南", "北", "东", "西")):
                    orientation = p.strip().replace("朝", "")

        # 区域行：区-商圈-小区
        m_loc = re.search(r'class="gray6[^"]*"[^>]*>(.*?)</p>', seg, re.S)
        district = bizarea = community = ""
        if m_loc:
            names = re.findall(r"<span>([^<]+)</span>", m_loc.group(1))
            if len(names) >= 3:
                district, bizarea, community = names[0], names[1], names[2]
            elif len(names) == 2:
                district, bizarea = names
            elif len(names) == 1:
                district = names[0]

        direct = 'class="smrz"' in seg           # 业主直租
        verified = "未经政府平台权属核验" not in seg and "icon_hy" in seg
        has_video = "video_icon" in seg

        listings.append(Listing(
            platform="房天下", house_id=(re.search(r'_(\d+)_1\.htm', url) or [None, ""])[1] if True else "",
            title=title, url=url, image=img, price=price,
            unit_price=round(price / area, 2) if area else 0,
            rent_type=rent_type, district=district, bizarea=bizarea,
            community=community, area_sqm=area, orientation=orientation,
            layout=layout,
            tags=(["业主直租"] if direct else []) + (["权属核验"] if verified else [])
                 + (["有视频"] if has_video else []),
            maintain="",
            has_vr=has_video,
        ))
        listings[-1].house_id = (re.search(r'_(\d+)_1\.htm', url) or [None, ""])[1] or url
        listings[-1].has_vr = has_video
    return listings


class FangScraper:
    name = "房天下"

    def search(self, city_slug: str, price_min: int = 0, price_max: int = 0,
               districts: list = None, rent_type: str = "", max_pages: int = 3,
               owner_only: bool = False) -> ScrapeResult:
        s = new_session()
        base = f"https://zu.fang.com/{city_slug}/house/"

        segs_master = []
        if price_min or price_max:
            segs_master.append(f"c2{price_min}-d2{price_max}" if price_min
                               else f"c20-d2{price_max}")
        if rent_type == "整租":
            segs_master.append("n3-100")
        if owner_only:
            segs_master.append("a21")

        # 区域：把用户给的区名匹配到房天下的 a 代码；匹配不到就把区名并入待抓列表
        dist_codes = []
        all_d = fetch_districts(city_slug) if districts else {}
        for d in (districts or []):
            hit = None
            for name, code in all_d.items():
                if d in name or name in d:
                    hit = code
                    break
            if hit:
                dist_codes.append(hit)

        urls = []
        if dist_codes:
            for c in dist_codes:
                for page in range(1, max_pages + 1):
                    segs = ([c] if c else []) + segs_master + [f"i3{page}"]
                    urls.append(base.rstrip("/") + "/" + "-".join(segs) + "/")
        else:
            for page in range(1, max_pages + 1):
                segs = segs_master + [f"i3{page}"]
                urls.append(base.rstrip("/") + "/" + ("-".join(segs) if segs else "") + "/")

        all_l, seen, total = [], set(), 0
        for u in urls:
            html = get_html(s, u, mark="chuzu")
            if not html:
                continue
            m_total = re.search(r'共找到.*?(\d+).*?套', html) or re.search(r'"total":\s*(\d+)', html)
            if m_total:
                total = max(total, int(m_total.group(1)))
            items = _parse_listing_page(html, base)
            for it in items:
                if it.url not in seen:
                    seen.add(it.url)
                    all_l.append(it)

        return ScrapeResult(city=city_slug, platform=self.name, listings=all_l,
                            total_on_site=total, ok=len(all_l) > 0,
                            message="" if all_l else "房天下无返回，可能该城市/筛选无结果")
