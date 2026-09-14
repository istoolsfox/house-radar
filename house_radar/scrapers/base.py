# -*- coding: utf-8 -*-
"""抓取基座：浏览器仿真请求、会话预热、重试、代理支持。

反爬现实（2026-09 实测）：
  - 房天下/贝壳系(含链家/安居客/58)均部署 IP 信誉墙 + TLS 指纹识别(JA3)，
    python-requests 的默认指纹会被快速标记限流；
  - 用 curl_cffi 仿真 Chrome TLS 指纹可显著降低被标记概率，但对"已标记 IP"
    的信誉墙无效——换网络(手机热点)或配代理(RADAR_PROXY / --proxy)才能解；
  - 请求节奏：每请求间随机延时 + 会话预热（先访问首页再进列表页，带 Referer）。
"""
import os
import random
import re
import time

try:
    from curl_cffi import requests as curl_requests
    _HAS_CURL = True
except ImportError:                                    # curl_cffi 为可选依赖
    _HAS_CURL = False

import requests

IMPERSONATE = "chrome"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Upgrade-Insecure-Requests": "1",
}

_PROXY = os.environ.get("RADAR_PROXY", "").strip()


def set_proxy(proxy: str):
    """全局代理（http://host:port 或 socks5://...），供 --proxy / 环境变量注入。"""
    global _PROXY
    _PROXY = (proxy or "").strip()


def _proxy_conf():
    return {"http": _PROXY, "https": _PROXY} if _PROXY else None


def parse_cookie_string(s: str) -> dict:
    """'k1=v1; k2=v2' -> dict。浏览器 F12 复制的 Cookie 串通用。"""
    out = {}
    for part in (s or "").split(";"):
        if "=" in part:
            k, _, v = part.strip().partition("=")
            out[k.strip()] = v.strip()
    return out


def _r(a=0.3, b=1.2):
    return random.uniform(a, b)


def new_session():
    """创建仿真浏览器的会话；未装 curl_cffi 时退回 requests。"""
    if _HAS_CURL:
        s = curl_requests.Session(impersonate=IMPERSONATE, proxies=_proxy_conf())
        # curl_cffi 会自带与指纹匹配的 UA/Sec-CH-UA，只补业务头
        s.headers.update({k: v for k, v in BASE_HEADERS.items()
                          if not k.startswith("Sec-")})
    else:
        s = requests.Session()
        s.headers.update({**BASE_HEADERS, "User-Agent": random.choice(USER_AGENTS)})
        if _PROXY:
            s.proxies = _proxy_conf()
    return s


def warm_up(session, url: str):
    """会话预热：先 GET 首页拿 cookie，后续列表页带上 Referer 更像真人浏览。"""
    try:
        session.get(url, timeout=15)
        time.sleep(_r(0.4, 0.9))
    except Exception:
        pass


def get_html(session, url: str, retries: int = 3,
             timeout: int = 20, mark: str = None, referer: str = None) -> str:
    """GET 一个页面，返回 HTML 文本。

    mark: 页面里应出现的特征串；出现验证页/被拦截时通常不含它，据此重试。
    referer: 会话预热后的来源页。
    失败（网络错误或拿不到 mark）返回 ""。
    """
    if referer:
        session.headers["Referer"] = referer
    for i in range(retries):
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code == 200 and (mark is None or mark in r.text):
                return r.text
            wall = "请完成下列验证" in r.text or r.status_code in (412, 429)
            # 验证墙/限流：指数退避，重试期间顺手换 UA（仅 requests 引擎有效）
            if not _HAS_CURL:
                session.headers["User-Agent"] = random.choice(USER_AGENTS)
                session.cookies.update({"lianjia_token": "", "select_city": ""})
            if wall:
                time.sleep(_r(3.0, 5.0) * (i + 1))
            else:
                time.sleep(_r(1.0, 2.5) * (i + 1))
        except requests.RequestException:
            time.sleep(_r(1.0, 2.5) * (i + 1))
        except Exception:
            time.sleep(_r(1.0, 2.5) * (i + 1))
    return ""


def polite():
    """页面间随机礼貌延时，降低触发限流的概率。"""
    time.sleep(_r(0.6, 1.4))


def clean_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()
