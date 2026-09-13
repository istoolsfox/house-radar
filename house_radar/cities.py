# -*- coding: utf-8 -*-
"""城市映射：中文名/拼音 → 贝壳与安居客子域名。

贝壳租房子域格式：{slug}.zu.ke.com
安居客租房子域格式：{slug}.zu.anjuke.com
两者 slug 基本一致（城市全拼），个别不同在此维护。
"""

# 中文名 -> 拼音 slug
CITY_SLUG = {
    "北京": "bj", "上海": "sh", "广州": "gz", "深圳": "sz",
    "成都": "cd", "杭州": "hz", "重庆": "cq", "武汉": "wh",
    "西安": "xa", "苏州": "su", "南京": "nj", "天津": "tj",
    "郑州": "zz", "长沙": "cs", "东莞": "dg", "佛山": "fs",
    "合肥": "hf", "青岛": "qd", "厦门": "xm", "福州": "fz",
    "昆明": "km", "大连": "dl", "宁波": "nb", "济南": "jn",
    "沈阳": "sy", "哈尔滨": "hrb", "石家庄": "sjz", "太原": "ty",
    "南昌": "nc", "南宁": "nn", "贵阳": "gy", "兰州": "lz",
    "海口": "hk", "三亚": "sy2", "无锡": "wx", "常州": "cz",
    "珠海": "zh", "中山": "zs", "惠州": "huizhou", "绍兴": "sx",
    "嘉兴": "jx", "泉州": "qz", "温州": "wz", "金华": "jh",
    "烟台": "yt", "潍坊": "wf", "洛阳": "ly", "惠州大亚湾": "hzz",
}

# 拼音 slug -> 中文名（反向，用于输入识别）
SLUG_CITY = {v: k for k, v in CITY_SLUG.items()}

SUPPORTED_CITIES = sorted(CITY_SLUG.keys())


def resolve_city(text: str) -> str:
    """把用户输入（中文/拼音/英文）解析成拼音 slug，失败返回空串。"""
    t = text.strip().lower()
    if not t:
        return ""
    if t in CITY_SLUG:
        return CITY_SLUG[t]
    if t in SLUG_CITY:
        return t
    # 前缀匹配拼音，如 "cd" -> cd 已在上面命中；"chengdu" 不在表里则模糊匹配
    for slug, city in SLUG_CITY.items():
        if slug == t or city.lower() == t:
            return slug
    return ""
