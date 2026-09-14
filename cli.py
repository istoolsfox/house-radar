# -*- coding: utf-8 -*-
"""租房雷达 CLI。

交互向导：  python cli.py
直通模式：  python cli.py -c 成都 -p 800 2500 -d 高新 天府新区 -r 整租
            python cli.py -c 深圳 -p 2000 4000 --owner-only --cookie "..." 
"""
import argparse
import io
import os
import sys
import webbrowser

if sys.stdout and hasattr(sys.stdout, "buffer") and \
        (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from house_radar import cities
from house_radar.scrapers import base
from house_radar.pipeline import run


def _wizard(args):
    print()
    print("=" * 46)
    print("  🏠 租房雷达 · 多平台真实房源筛选")
    print("  房天下 / 贝壳 / 安居客 / 58同城")
    print("=" * 46)

    if not args.city:
        print(f"\n支持城市：{'、'.join(cities.SUPPORTED_CITIES)}")
        while True:
            c = input("\n① 你在哪个城市？ ").strip()
            if cities.resolve_city(c):
                args.city = c
                break
            print("  没认出来，再输一次（中文或拼音，如：成都 / cd）")

    if not args.price:
        while True:
            raw = input("② 月租预算区间（如 800-2500，直接回车=不限）： ").strip()
            if not raw:
                break
            nums = [n for n in raw.replace("～", "-").replace("~", "-").replace("，", "-").split("-")
                    if n.strip().isdigit()]
            if len(nums) == 2:
                args.price = (int(nums[0]), int(nums[1]))
                break
            if len(nums) == 1:
                args.price = (0, int(nums[0]))
                break
            print("  格式：最低-最高，例如 800-2500")

    if args.districts is None and sys.stdin and sys.stdin.isatty():
        raw = input("③ 想住哪几个区？（空格分隔，回车=全城）： ").strip()
        args.districts = raw.split() if raw else []

    if not args.rent_type:
        r = input("④ 整租还是合租？（1 整租 / 2 合租 / 回车=都要）： ").strip()
        args.rent_type = {"1": "整租", "2": "合租"}.get(r, "")


def main():
    ap = argparse.ArgumentParser(description="租房雷达 · 多平台真实房源筛选")
    ap.add_argument("-c", "--city", help="城市（中文或拼音）")
    ap.add_argument("-p", "--price", nargs="+", type=int, help="价格区间 月租 如 800 2500")
    ap.add_argument("-d", "--districts", nargs="*", help="区域列表")
    ap.add_argument("-r", "--rent-type", choices=["整租", "合租"], default="")
    ap.add_argument("--owner-only", action="store_true", help="仅个人/业主直租（房天下支持）")
    ap.add_argument("--cookie", default="", help="贝壳登录 Cookie（可选，解锁筛选/翻页全量）")
    ap.add_argument("--fang-cookie", default="", dest="fang_cookie",
                    help="房天下 Cookie（触发滑块验证后，浏览器人工通过验证再复制的 Cookie）")
    ap.add_argument("--pages", type=int, default=2, help="房天下每个区域抓取页数（默认2）")
    ap.add_argument("--proxy", default=os.environ.get("RADAR_PROXY", ""),
                    help="HTTP/SOCKS5 代理（如 http://127.0.0.1:7890），IP 被平台限流时用")
    ap.add_argument("--open", action="store_true", help="生成后自动用浏览器打开报告")
    args = ap.parse_args()

    if args.proxy:
        base.set_proxy(args.proxy)

    interactive = not args.city
    if interactive:
        if not (sys.stdin and sys.stdin.isatty()):
            ap.error("非交互环境请使用参数模式，如：python cli.py -c 成都 -p 800 2500")
        _wizard(args)

    # 与交互向导一致：单值视为价格上限（-p 2500 = 2500 以内），两值为区间
    pmin = args.price[0] if args.price and len(args.price) > 1 else 0
    pmax = args.price[-1] if args.price else 0

    out_path, listings, stats = run(
        args.city, price_min=pmin, price_max=pmax,
        districts=args.districts or [], rent_type=args.rent_type or "",
        cookie=args.cookie, owner_only=args.owner_only, max_pages=args.pages,
        fang_cookie=args.fang_cookie)

    print()
    print("=" * 46)
    print(f"✔ 报告已生成：{out_path}")
    print(f"  房源 {len(listings)} 套 | 🟢放心看 {stats['green']} | 🔴高风险 {stats['red']}"
          + (f" | 疑似串串房 {stats['hard']}" if stats["hard"] else ""))
    if stats["failed"]:
        print(f"  （本次未返回数据的源：{'、'.join(stats['failed'])}，已自动跳过）")
    print("=" * 46)

    top = [x for x in listings if x.score["emoji"] == "🟢"][:5]
    if top:
        print("\n🟢 综合分最高：")
        for i, x in enumerate(top, 1):
            print(f"  {i}. [{x.score['total']}分] {x.price}元/月 {x.title[:34]}")
            print(f"     {x.url}")
    if args.open:
        import pathlib
        webbrowser.open(pathlib.Path(out_path).absolute().as_uri())


if __name__ == "__main__":
    main()
