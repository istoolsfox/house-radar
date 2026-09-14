# -*- coding: utf-8 -*-
"""贝壳租房抓取器（{city}.zu.ke.com）。

URL 规律（2026-09 实测）：
  城市首页   https://{slug}.zu.ke.com/zufang/          （匿名仅此页，约30条全城推荐）
  区域页     https://{slug}.zu.ke.com/zufang/{区slug}/  （需登录；区slug 无规律，
              如 xiaoshanqu / xihuqu4，必须从首页"按区域"导航解析，不能拼接）
  筛选段     整租 rt200600000001 / 合租 rt200600000002
              价格 rp1≤1000 rp2=1000-1500 rp3=1500-2000 rp4=2000-2500
                   rp5=2500-3500 rp6=3500-5000 rp7=5000-10000 rp8≥10000
              组合：/zufang/{区slug}/rt200600000001rp2/  段顺序宽容
  分页       追加 /pg{n}/
注意：
  - ?brp=&erp= 查询参数服务端不认（静默忽略），必须用 rp 路径段；
  - 匿名访问区域页会 302 到 clogin.ke.com，据此快速判定登录态失效；
  - 个人公寓房源 data-house_code 可能是纯数字且无详情链接，解析时容忍。
"""
import re
from urllib.parse import urljoin

from .base import get_html, new_session, clean_ws, warm_up, polite, parse_cookie_string
from ..models import Listing, ScrapeResult

PRICE_BANDS = [
    (0, 1000, "rp1"), (1000, 1500, "rp2"), (1500, 2000, "rp3"),
    (2000, 2500, "rp4"), (2500, 3500, "rp5"), (3500, 5000, "rp6"),
    (5000, 10000, "rp7"), (10000, 10 ** 9, "rp8"),
]
RENT_SEG = {"整租": "rt200600000001", "合租": "rt200600000002"}


def _parse_cookie_string(s: str) -> dict:
    return parse_cookie_string(s)


def _parse_district_nav(html: str) -> dict:
    """解析首页"按区域"导航 HTML → {区中文名: 区slug}（纯函数，可离线测试）。"""
    out = {}
    for slug, name in re.findall(
            r'href="/zufang/([a-z0-9]+)/"[^>]*>([^<]{2,10})<', html):
        name = clean_ws(name)
        # 真区域是"XX区/市/县"(2-4字)；品牌公寓(X X社区)和小区名同样以区结尾，靠长度排除
        if not re.search(r"(区|市|县)$", name) or not (2 <= len(name) - 1 <= 4) \
                or name in ("不限",):
            continue
        if name not in out:
            out[name] = slug
    return out


def fetch_districts(city_slug: str) -> dict:
    """解析城市首页"按区域"导航，返回 {区中文名: 区slug}。

    区slug 无统一规律（xihuqu4 / xiaoshanqu），只能解析获得。
    """
    s = new_session()
    html = get_html(s, f"https://{city_slug}.zu.ke.com/zufang/", mark="content__list")
    return _parse_district_nav(html) if html else {}


def match_district(name: str, all_d: dict) -> str:
    """用户区名 → 区slug。精确 > 前缀 > 包含。"""
    if name in all_d:
        return all_d[name]
    for n, slug in all_d.items():
        if n.startswith(name):
            return slug
    for n, slug in all_d.items():
        if name.startswith(n):
            return slug
    for n, slug in all_d.items():
        if name in n or n in name:
            return slug
    return ""


def _price_segments(pmin: int, pmax: int) -> list:
    """用户区间覆盖到的 rp 价格段代码。"""
    if not pmin and not pmax:
        return []
    segs = [code for lo, hi, code in PRICE_BANDS if hi > pmin and lo < pmax]
    return segs or [PRICE_BANDS[-1][2]]


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

        匿名：仅城市首页（约30条全城推荐，区域/筛选强制登录）。
        带 cookie：区域页 + rt/rp 筛选段 + /pg{n}/ 翻页全量；登录失效立即报错不空耗。
        """
        s = new_session()
        if self.cookie:
            s.cookies.update(_parse_cookie_string(self.cookie))
        base = f"https://{city_slug}.zu.ke.com"
        rent_seg = RENT_SEG.get(rent_type, "")
        rp_segs = _price_segments(price_min, price_max)

        if not self.cookie:
            urls = [f"{base}/zufang/"]
        else:
            all_d = fetch_districts(city_slug)
            slugs, unmatched = [], []
            for d in (districts or []):
                slug = match_district(d, all_d)
                if slug:
                    slugs.append(slug)
                else:
                    unmatched.append(d)
            if not slugs:
                slugs = [""]                       # 无有效区名 → 城市级筛选
            urls = []
            for slug in slugs:
                for rp in (rp_segs or [""]):
                    seg = rent_seg + rp
                    path = f"/zufang/{slug}/" if slug else "/zufang/"
                    urls.append(base + path + seg + "/" if seg else base + path)

        # 登录态快速判定：失效 cookie 访问纯首页仍会拿到匿名内容（不跳登录），
        # 必须用带筛选段的金丝雀 URL 才能触发 clogin 302
        if self.cookie and urls:
            canary = urls[0]
            if canary.rstrip("/").endswith("/zufang"):
                canary = f"{base}/zufang/rt200600000001rp1/"
            try:
                probe = s.get(canary, timeout=20, allow_redirects=True)
                if "clogin" in str(probe.url):
                    return ScrapeResult(city=city_slug, platform=self.name, listings=[],
                                        ok=False, blocked=True,
                                        message="贝壳登录 Cookie 已失效，请重新复制（F12 → Network → Cookie）")
                first_html = probe.text if canary == urls[0] and "content__list" in probe.text else ""
            except Exception:
                first_html = ""
        else:
            first_html = ""

        all_l, seen = [], set()
        total = 0
        if not self.cookie:
            warm_up(s, f"{base}/zufang/")      # 匿名先逛首页再抓，更像真人
        for ui, u in enumerate(urls):
            for page in range(1, max_pages + 1):
                if ui == 0 and page == 1 and first_html:
                    html = first_html              # 复用探测请求，省一次抓取
                else:
                    pu = u if page == 1 else u.rstrip("/") + f"/pg{page}/"
                    html = get_html(s, pu, mark="content__list",
                                    referer=f"{base}/zufang/")
                    polite()
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
                    if it.url and it.url not in seen:
                        seen.add(it.url)
                        all_l.append(it)
                        new += 1
                if new == 0:
                    break

        # 精确价格兜底：rp 段只到 500 档，边界内再本地精滤
        if price_min:
            all_l = [x for x in all_l if x.price >= price_min]
        if price_max:
            all_l = [x for x in all_l if x.price <= price_max]

        if all_l:
            msg = ""
            if self.cookie and (districts or []) and len(all_l) < 5:
                msg = "结果偏少，可放宽价格段或去掉区域试试"
        elif self.cookie:
            msg = "贝壳带 Cookie 未取到数据：Cookie 可能过期，或该区域/价格段无房源"
        else:
            msg = "贝壳匿名状态仅能获取首页推荐，建议提供登录 Cookie 以解锁区域+筛选全量"
        return ScrapeResult(city=city_slug, platform=self.name, listings=all_l,
                            total_on_site=total, ok=len(all_l) > 0, message=msg)
