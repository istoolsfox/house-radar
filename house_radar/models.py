# -*- coding: utf-8 -*-
"""数据模型：房源条目与评分结果。"""
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Listing:
    """一条房源信息（跨平台统一结构）。"""
    platform: str                 # beike / anjuke
    house_id: str                 # 平台房源编码
    title: str = ""
    url: str = ""                 # 房源详情页绝对链接
    image: str = ""               # 首图
    price: int = 0                # 月租（元）
    unit_price: float = 0.0       # 单价 元/㎡/月
    rent_type: str = ""           # 整租 / 合租
    district: str = ""            # 区（如 高新）
    bizarea: str = ""             # 商圈（如 金融城）
    community: str = ""           # 小区名
    area_sqm: float = 0.0         # 面积㎡
    orientation: str = ""         # 朝向
    layout: str = ""              # 户型 1室0厅1卫
    floor_desc: str = ""          # 楼层描述
    tags: list = field(default_factory=list)   # 平台标签（权属核验/VR/近地铁…）
    brand: str = ""               # 品牌方 / 经纪机构
    maintain: str = ""            # 维护时间（今天维护 / 3天前…）
    has_vr: bool = False          # 是否 VR 看房
    score: dict = None            # 评分结果（scoring 后填充）

    @property
    def search_blob(self) -> str:
        """用于信号词扫描的拼接文本。"""
        return " ".join([
            self.title, self.layout, self.orientation, self.floor_desc,
            " ".join(self.tags), self.brand,
        ])

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class ScrapeResult:
    """一次抓取的整体结果。"""
    city: str
    platform: str
    listings: list = field(default_factory=list)
    total_on_site: int = 0        # 平台显示的命中总数
    ok: bool = True
    message: str = ""
    blocked: bool = False         # 是否被反爬验证墙拦截（限流，稍后可重试）
