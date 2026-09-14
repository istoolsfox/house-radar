# -*- coding: utf-8 -*-
"""房天下租房抓取器（zu.fang.com）——匿名全功能主力源。

URL 规律（2026-09 实测，服务器对段顺序宽容、/ 与 - 分隔可混用）：
  城市页   https://zu.fang.com/{slug}/house/
  合租频道 https://zu.fang.com/{slug}/hezu/      （合租走独立频道）
  区域     -a{区代码}（从城市页"区域"导航解析，如 a016749=高新，多为 a0 开头多段数字）
  价格     c2{min}-d2{max}（min=0 写 c20）
  整租     n31    个人房源 a21    户型 g2{1..4} / g299
  分页     i3{页码}
注意：个人房源(a21)列表页不带 smrz"业主直租"徽章，owner_only 时需自行补标签。
"""
import re
from urllib.parse import urljoin

from .base import get_html, new_session, clean_ws, warm_up, polite, parse_cookie_string
from ..models import Listing, ScrapeResult


def fetch_districts(city_slug: str, cookie: str = "") -> dict:
    """解析城市页"区域"导航，返回 {区中文名: a代码}。

    导航形如 <a href="/cd/house-a016749/">高新</a>，区代码在 house- / hezu- 连字符后。
    触发过滑块验证的 IP 需带入验证 cookie 才能拿到完整城市页。
    """
    s = new_session()
    if cookie:
        s.cookies.update(parse_cookie_string(cookie))
    html = get_html(s, f"https://zu.fang.com/{city_slug}/house/", mark="house")
    out = {}
    if html:
        for code, name in re.findall(
                r'href="(?:https?://zu\.fang\.com)?/' + city_slug +
                r'/(?:house|hezu)-(a\d+)/"[^>]*>([^<]{1,12})</a>', html):
            name = clean_ws(name)
            if name and name not in ("不限", "全部房源") and code not in out:
                out[name] = code
    return out


def match_district(name: str, all_d: dict) -> str:
    """用户区名 → 代码。精确 > 导航名前缀（高新西→高新西区）> 双向包含。"""
    if name in all_d:
        return all_d[name]
    for n, c in all_d.items():
        if n.startswith(name):
            return c
    for n, c in all_d.items():
        if name.startswith(n):
            return c
    for n, c in all_d.items():
        if name in n or n in name:
            return c
    return ""


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

        # 区域行：区-商圈-小区。区名常为链接外裸文本（高新-<a>商圈</a>-<a>小区</a>），
        # 剥标签后按 - 切分比抓 span 更稳，三种段数格式统一处理
        m_loc = re.search(r'class="gray6[^"]*"[^>]*>(.*?)</p>', seg, re.S)
        district = bizarea = community = ""
        if m_loc:
            plain = re.sub(r"<[^>]+>", "", m_loc.group(1))
            parts = [p.strip() for p in plain.split("-") if p.strip()]
            if len(parts) >= 3:
                district, bizarea, community = parts[0], parts[1], parts[2]
            elif len(parts) == 2:
                district, bizarea = parts
            elif len(parts) == 1:
                district = parts[0]

        direct = 'class="smrz"' in seg           # 业主直租
        verified = "未经政府平台权属核验" not in seg and "icon_hy" in seg
        has_video = "video_icon" in seg

        listings.append(Listing(
            platform="房天下",
            house_id=(re.search(r'_(\d+)_1\.htm', url) or [None, url])[1],
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
    return listings


class FangScraper:
    name = "房天下"

    def __init__(self, cookie: str = ""):
        # 触发滑块验证后，浏览器人工通过验证拿到的 cookie 可复用解封
        # （global_cookie / unique_cookie 为关键设备凭证）
        self.cookie = cookie

    def search(self, city_slug: str, price_min: int = 0, price_max: int = 0,
               districts: list = None, rent_type: str = "", max_pages: int = 3,
               owner_only: bool = False) -> ScrapeResult:
        s = new_session()
        if self.cookie:
            s.cookies.update(parse_cookie_string(self.cookie))
        # 合租走独立频道 /{slug}/hezu/，整租用 n31 段
        channel = "hezu" if rent_type == "合租" else "house"
        base = f"https://zu.fang.com/{city_slug}/{channel}/"

        segs_master = []
        if price_min or price_max:
            segs_master.append(f"c2{price_min}-d2{price_max}" if price_min
                               else f"c20-d2{price_max}")
        if rent_type == "整租":
            segs_master.append("n31")
        if owner_only:
            segs_master.append("a21")

        # 区域：把用户给的区名匹配到房天下的 a 代码；匹配不到就留在列表里交由本地过滤
        dist_codes = []
        unmatched = []
        all_d = fetch_districts(city_slug, cookie=self.cookie) if districts else {}
        for d in (districts or []):
            code = match_district(d, all_d)
            if code:
                dist_codes.append(code)
            else:
                unmatched.append(d)

        urls = []
        if dist_codes:
            for c in dist_codes:
                for page in range(1, max_pages + 1):
                    segs = [c] + segs_master + [f"i3{page}"]
                    urls.append(base.rstrip("/") + "/" + "-".join(segs) + "/")
        else:
            for page in range(1, max_pages + 1):
                segs = segs_master + [f"i3{page}"]
                urls.append(base.rstrip("/") + "/" + ("-".join(segs) if segs else "") + "/")

        all_l, seen, total = [], set(), 0
        wall = False
        warm_up(s, f"https://zu.fang.com/{city_slug}/house/")   # 会话预热拿 cookie
        for u in urls:
            html = get_html(s, u, mark="chuzu", referer=f"https://zu.fang.com/{city_slug}/house/")
            polite()
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

        # 全部落空时区分"真无结果"和"滑块验证墙"，给用户可行动的提示
        msg = "" if all_l else "房天下无返回，可能该城市/筛选无结果"
        if not all_l and urls:
            try:
                probe = s.get(urls[0], timeout=20)
                if "请完成下列验证" in probe.text or len(probe.text) < 2000:
                    wall = True
                    msg = "房天下触发滑块验证（请求过于频繁被限流），请几分钟后重试"
            except Exception:
                pass

        # a21(个人房源)列表页不带"业主直租"徽章，主动补标签让评分吃到直租加分
        if owner_only:
            for it in all_l:
                if "业主直租" not in (it.tags or []):
                    it.tags.append("业主直租")

        if all_l and unmatched:
            msg = f"区 {'、'.join(unmatched)} 未匹配到房天下代码，已按全城抓取待本地过滤"
        return ScrapeResult(city=city_slug, platform=self.name, listings=all_l,
                            total_on_site=total, ok=len(all_l) > 0,
                            message=msg, blocked=wall)
