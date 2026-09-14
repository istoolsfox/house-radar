# -*- coding: utf-8 -*-
"""评分引擎。

四个维度（内部 100 分制，加权合成为 0-100 综合分）：
  真实可信 trust  30%   平台核验、VR/视频、机构、维护时间、信息完整度
  性价比   value  25%   单价 vs 商圈/区/全城中位数
  风险安全 risk   25%   串串房/黑中介/隔断信号检测（高分=安全）
  便利匹配 conv   20%   地铁、区域命中、朝向、楼层、整租合租匹配

串串房高危组合（命中即 🔴 红灯，总分封顶 55）：
  新装修词（精装/全新装修/首次出租/拎包入住/豪装）且 价格 < 基准 75%
"""
import re
import statistics

# ---------- 信号词库 ----------
NEW_DECOR_WORDS = ["精装", "全新装修", "首次出租", "拎包入住", "豪装", "新装修", "崭新"]
URGE_WORDS = ["急租", "速租", "最后一套", "手慢无", "限时", "今日特惠", "房东直降", "捡漏"]
APARTMENT_WORDS = ["品牌公寓", "托管", "青年公寓", "服务式公寓", "集中式"]
PARTITION_WORDS = ["隔断", "隔间", "单间独立"]
SUBWAY_WORDS = ["近地铁", "地铁房", "地铁口", "近轨道交通", "近地铁房"]
MONTH_PAY_WORDS = ["押一付一", "可月付", "免押金", "月付无压力"]

DANGER = "疑似串串房：远低于市价的“新装修”房（低价+新装是串串房最典型特征，甲醛超标风险高）"


def _has(words, text):
    return [w for w in words if w and w in text]


def _median(nums):
    return statistics.median(nums) if nums else 0


def _area_medians(listings):
    """构建 商圈→中位数、区→中位数、全城中位数 三级基准。"""
    by_biz, by_dist, all_p = {}, {}, []
    for x in listings:
        if x.price <= 0 or not x.area_sqm:
            continue
        up = x.unit_price or x.price / x.area_sqm
        all_p.append(up)
        if x.bizarea:
            by_biz.setdefault(x.bizarea, []).append(up)
        if x.district:
            by_dist.setdefault(x.district, []).append(up)
    return ({k: _median(v) for k, v in by_biz.items() if len(v) >= 5},
            {k: _median(v) for k, v in by_dist.items() if len(v) >= 8},
            _median(all_p))


def _value_score(ratio):
    """性价比分：ratio = 单价 / 基准中位数。"""
    if ratio <= 0:
        return 55, []
    notes = []
    if ratio < 0.50:
        return 40, ["价格仅为市场均价一半，异常低价需警惕"]
    if ratio < 0.65:
        return 65, ["明显低于市场均价（65折以下）"]
    if ratio < 0.80:
        return 80, ["低于市场均价约2~3成"]
    if ratio <= 1.05:
        return 100, []
    if ratio <= 1.20:
        return 85, []
    if ratio <= 1.35:
        return 68, []
    if ratio <= 1.60:
        return 50, ["高于市场均价3~6成"]
    return 32, ["价格远高于市场均价"]


def score_all(listings, user_districts=None, rent_type=""):
    """给全部房源打分（会就地填充 listing.score）。返回 (listings, 基准信息)。"""
    user_districts = [d for d in (user_districts or []) if d]
    biz_med, dist_med, all_med = _area_medians(listings)

    for x in listings:
        blob = x.search_blob
        signals_add, signals_minus = [], []

        # ---- 真实可信 ----
        trust = 45.0
        verified = "权属核验" in x.tags or "已核验" in blob
        direct = "业主直租" in x.tags or "房东直租" in blob or "业主自荐" in x.tags
        if verified:
            trust += 25; signals_add.append("平台权属核验（真实性背书最强）")
        if direct:
            trust += 12; signals_add.append("业主/房东直租，无中介差价")
        if x.has_vr or "有视频" in x.tags:
            trust += 15; signals_add.append("VR/视频看房")
        if any(k in blob for k in ("自营", "贝壳优选", "德佑", "品牌")):
            trust += 8; signals_add.append(f"品牌机构维护（{x.brand or '自营'}）")
        mt = x.maintain
        if mt:
            if "今天" in mt or "刚刚" in mt:
                trust += 12
            elif "昨天" in mt:
                trust += 10
            elif re.search(r"[1-7]天", mt):
                trust += 6
        missing = [n for n, v in (("面积", x.area_sqm), ("朝向", x.orientation),
                                  ("户型", x.layout)) if not v]
        if not missing:
            trust += 15
        else:
            trust -= 5 * len(missing)
            signals_minus.append(f"信息不全：缺{'、'.join(missing)}")
        if x.image:
            trust += 8
        trust = max(0, min(100, trust))

        # ---- 性价比 ----
        up = x.unit_price or (x.price / x.area_sqm if x.area_sqm else 0)
        base, base_src = all_med, "全城"
        if x.bizarea in biz_med:
            base, base_src = biz_med[x.bizarea], f"{x.bizarea}商圈"
        elif x.district in dist_med:
            base, base_src = dist_med[x.district], f"{x.district}"
        ratio = (up / base) if base else 0
        value, vnotes = _value_score(ratio)
        signals_minus.extend(vnotes)
        if ratio and ratio < 0.85:
            signals_minus.append(f"单价约为{base_src}均价的{ratio:.0%}，看房时请核实真实原因")

        # ---- 风险安全（高分=安全）----
        risk = 85.0
        hard_flag = False
        decor_hits = _has(NEW_DECOR_WORDS, blob)
        if decor_hits and ratio and ratio < 0.75:
            hard_flag = True
            risk = 15
            signals_minus.insert(0, "⚠ " + DANGER)
        else:
            if decor_hits and ratio and ratio < 0.9:
                risk -= 10
                signals_minus.append(f"新装修词（{'、'.join(decor_hits)}）+ 低于市价：入住前建议做甲醛检测")
            urge = _has(URGE_WORDS, blob)
            if urge:
                risk -= min(15, 6 * len(urge))
                signals_minus.append(f"逼单话术（{'、'.join(urge)}）：制造紧迫感是常见套路，勿当场交定金")
            apart = _has(APARTMENT_WORDS, blob + (x.brand or ""))
            if apart:
                risk -= 10
                signals_minus.append("公寓运营商房源：注意服务水平与甲醛风险")
            pay = _has(MONTH_PAY_WORDS, blob)
            if pay:
                risk -= 6
            if _has(PARTITION_WORDS, blob):
                risk -= 18
                signals_minus.append("疑似隔断房：注意消防与邻居干扰")
            if x.area_sqm and x.area_sqm < 12:
                risk -= 12
                signals_minus.append(f"面积仅{x.area_sqm}㎡，疑似隔断单间")
            if verified:
                risk += 10
            if direct:
                risk += 8
            if x.has_vr or "有视频" in x.tags:
                risk += 5
        risk = max(0, min(100, risk))

        # ---- 便利匹配 ----
        conv = 30.0
        if _has(SUBWAY_WORDS, blob) or "近地铁" in x.tags:
            conv += 30; signals_add.append("近地铁")
        if user_districts and any(d and (d in x.district + x.bizarea + x.community or x.district in d)
                                  for d in user_districts):
            conv += 25; signals_add.append("命中目标区域")
        if x.orientation:
            if any(k in x.orientation for k in ("南北", "东南", "南")):
                conv += 15
            elif any(k in x.orientation for k in ("东西", "东", "西")):
                conv += 8
        if x.floor_desc:
            conv += 10 if any(k in x.floor_desc for k in ("中", "高")) else 5
        if rent_type and (rent_type == x.rent_type or rent_type in x.title):
            conv += 20
        conv = min(100, conv)

        total = trust * 0.30 + value * 0.25 + risk * 0.25 + conv * 0.20
        if hard_flag:
            total = min(total, 55)
        total = round(total)

        level, emoji = ("放心优先看", "🟢") if total >= 75 and not hard_flag else \
                       (("多留心", "🟡") if total >= 55 else ("高风险", "🔴"))

        x.score = {
            "total": total, "level": level, "emoji": emoji,
            "trust": round(trust), "value": round(value),
            "risk": round(risk), "conv": round(conv),
            "ratio": round(ratio, 2) if ratio else 0,
            "base": round(base), "base_src": base_src,
            "hard_flag": hard_flag,
            "add": signals_add[:6], "minus": signals_minus[:6],
        }
    return listings, {"all_median": round(all_med), "biz": {k: round(v) for k, v in biz_med.items()},
                      "dist": {k: round(v) for k, v in dist_med.items()}}
