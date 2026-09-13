# -*- coding: utf-8 -*-
"""抓取基座：统一请求头、重试、HTML 获取。"""
import random
import re
import time

import requests

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    "Connection": "keep-alive",
}


def _r(a=0.3, b=1.2):
    return random.uniform(a, b)


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({**BASE_HEADERS, "User-Agent": random.choice(USER_AGENTS)})
    return s


def get_html(session: requests.Session, url: str, retries: int = 3,
             timeout: int = 20, mark: str = None) -> str:
    """GET 一个页面，返回 HTML 文本。

    mark: 页面里应出现的特征串；出现验证页/被拦截时通常不含它，据此重试。
    失败（网络错误或拿不到 mark）返回 ""。
    """
    for i in range(retries):
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code == 200 and (mark is None or mark in r.text):
                return r.text
            # 412/302 验证页等：换 UA 随机 cookie 再试
            session.headers["User-Agent"] = random.choice(USER_AGENTS)
            session.cookies.update({"lianjia_token": "", "select_city": ""})
        except requests.RequestException:
            pass
        time.sleep(_r(1.0, 2.5) * (i + 1))
    return ""


def clean_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()
