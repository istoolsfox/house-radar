# -*- coding: utf-8 -*-
"""HTML 报告生成：单文件自包含，图片外链（no-referrer 防防盗链）。"""
import html as H
import time

LEVEL_COLOR = {"🟢": "#16a34a", "🟡": "#d97706", "🔴": "#dc2626"}

_CSS = """
:root{--bg:#f4f6f9;--card:#fff;--ink:#1f2937;--dim:#8a94a6}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"PingFang SC","Microsoft YaHei",system-ui,sans-serif;background:var(--bg);color:var(--ink)}
.wrap{max-width:1060px;margin:0 auto;padding:20px 16px 60px}
.hero{background:linear-gradient(135deg,#0f2b46,#1d4ed8 90%);border-radius:16px;color:#fff;padding:26px 26px 22px}
.hero h1{font-size:24px;letter-spacing:1px}.hero p{margin-top:8px;font-size:14px;opacity:.85}
.statline{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px;font-size:13px}
.statline span{background:rgba(255,255,255,.14);padding:5px 12px;border-radius:99px}
.statline b{font-size:15px}
.toolbar{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 12px;align-items:center;font-size:13px;color:#64748b}
.toolbar button{border:1px solid #d7dde6;background:#fff;border-radius:99px;padding:6px 14px;font-size:13px;cursor:pointer;color:#374151}
.toolbar button.on{background:#1d4ed8;border-color:#1d4ed8;color:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(480px,1fr));gap:14px}
@media(max-width:560px){.grid{grid-template-columns:1fr}.card{flex-direction:column}.imgbox{width:100%;height:180px;min-width:0}}
.card{background:var(--card);border-radius:14px;overflow:hidden;display:flex;box-shadow:0 1px 4px rgba(16,24,40,.08);position:relative}
.fav{position:absolute;right:8px;top:8px;z-index:3;width:30px;height:30px;border-radius:50%;border:none;background:rgba(255,255,255,.92);font-size:17px;color:#94a3b8;cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,.18);line-height:1}
.fav.on{color:#f59e0b;background:#fffbeb}
.favbar{position:fixed;left:50%;transform:translateX(-50%);bottom:18px;z-index:9;background:#0f172a;color:#fff;border-radius:99px;padding:10px 18px;display:none;align-items:center;gap:12px;font-size:13px;box-shadow:0 6px 24px rgba(2,6,23,.35)}
.favbar.show{display:flex}
.favbar button{border:none;border-radius:99px;padding:6px 14px;font-size:13px;cursor:pointer;font-weight:600}
.favbar .copy{background:#22c55e;color:#04250f}
.favbar .clear{background:rgba(255,255,255,.15);color:#fff}
.card.lvred{outline:2px solid #fecaca}
.imgbox{width:168px;min-width:168px;position:relative;background:#eef1f5}
.imgbox img{width:100%;height:100%;object-fit:cover;display:block}
.noimg{height:100%;display:flex;align-items:center;justify-content:center;color:#b6bfcc;font-size:13px}
.pf{position:absolute;left:6px;top:6px;font-size:11px;color:#fff;padding:2px 8px;border-radius:6px;background:#6b7280}
.pf.bk{background:#0e6f3c}.pf.ft{background:#c2812a}.pf.aj{background:#0ea5e9}.pf.w5{background:#f59e0b}
.body{flex:1;padding:12px 14px;min-width:0}
.row1{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}
.title{font-size:15px;font-weight:600;line-height:1.45;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.ring{width:52px;height:52px;flex-shrink:0}
.price{margin-top:4px;font-size:13px;color:#c2410c}
.price b{font-size:20px}
.unit{margin-left:8px;color:var(--dim);font-size:12px}
.ratio{margin-left:8px;font-size:12px;color:#0e7490;background:#ecfeff;border-radius:6px;padding:1px 6px}
.loc{margin-top:4px;font-size:13px;color:#475569;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.meta{margin-left:8px;color:var(--dim);font-size:12px}
.ratio-bar{position:relative;height:5px;background:#e8ecf1;border-radius:99px;margin-top:8px;overflow:hidden}
.ratio-bar i{display:block;height:100%;background:linear-gradient(90deg,#34d399,#fbbf24 75%,#f87171);border-radius:99px}
.tags{margin-top:8px;display:flex;flex-wrap:wrap;gap:5px}
.tag{font-size:11px;background:#f1f5f9;color:#475569;border-radius:6px;padding:2px 7px}
.tag.vr{background:#ecfdf5;color:#059669}.tag.direct{background:#fff7ed;color:#c2410c}
.sg{font-size:12px;margin-top:5px;line-height:1.5}
.sg.add{color:#15803d}.sg.minus{color:#b91c1c}
.hardwarn{margin-top:6px;background:#fef2f2;color:#b91c1c;font-size:12px;font-weight:600;padding:6px 9px;border-radius:8px;border:1px dashed #fca5a5}
.foot{margin-top:8px;display:flex;justify-content:space-between;align-items:center;font-size:12px}
.dim{color:var(--dim)}.go{color:#1d4ed8;text-decoration:none;font-weight:600}
.note{margin-top:22px;background:#fff;border-radius:14px;padding:18px 20px;font-size:13px;line-height:1.9;color:#374151}
.note h3{font-size:15px;margin-bottom:8px}.note li{margin-left:18px}
.src{background:#eef2ff;color:#3730a3;border-radius:8px;padding:3px 10px;font-size:12px}
.hint{margin-top:10px;font-size:12px;color:var(--dim);line-height:1.7}
"""

_JS = """
document.querySelectorAll('.toolbar button[data-k]').forEach(function(b){
  b.onclick=function(){
    document.querySelectorAll('.toolbar button[data-k]').forEach(function(x){x.classList.remove('on')});
    b.classList.add('on');
    var k=b.dataset.k, cards=[].slice.call(grid.children);
    cards.sort(function(a,c){return (+c.dataset[k]||0)-(+a.dataset[k]||0);});
    cards.forEach(function(c){grid.appendChild(c);});
  };
});
document.querySelectorAll('.toolbar button[data-f]').forEach(function(b){
  b.onclick=function(){
    document.querySelectorAll('.toolbar button[data-f]').forEach(function(x){x.classList.remove('on')});
    b.classList.add('on');
    var f=b.dataset.f;
    [].slice.call(grid.children).forEach(function(c){
      var lv=c.getAttribute('data-lv');
      var show = f==='all' || (f==='green' && lv==='🟢') || (f==='red' && lv==='🔴');
      c.style.display = show ? '' : 'none';
    });
  };
});
"""
_JS_FAV = """
const favs = new Set();
function refreshFav(){
  document.getElementById('favcount').textContent = '已选 ' + favs.size + ' 套';
  document.getElementById('favbar').classList.toggle('show', favs.size > 0);
}
document.querySelectorAll('.card .fav').forEach(function(b){
  b.onclick = function(e){
    e.stopPropagation();
    var card = b.closest('.card');
    var key = card.dataset.url;
    if (favs.has(key)) { favs.delete(key); b.classList.remove('on'); b.textContent='☆'; }
    else { favs.add(key); b.classList.add('on'); b.textContent='★'; }
    refreshFav();
  };
});
document.getElementById('favclear').onclick = function(){
  favs.clear();
  document.querySelectorAll('.card .fav.on').forEach(function(b){b.classList.remove('on');b.textContent='☆';});
  refreshFav();
};
document.getElementById('favcopy').onclick = function(){
  var lines = [];
  [].slice.call(grid.children).forEach(function(c){
    if (favs.has(c.dataset.url)) {
      lines.push('【' + c.dataset.platform + '】' + c.dataset.title + ' ' + c.dataset.price + '元/月 评分' + c.dataset.score + '\\n' + c.dataset.url);
    }
  });
  var text = '🏠 租房雷达收藏清单\\n' + lines.join('\\n----------\\n');
  function done(){ document.getElementById('favcopy').textContent='✓ 已复制'; setTimeout(function(){document.getElementById('favcopy').textContent='📋 复制收藏清单';}, 2000); }
  if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(text).then(done); }
  else {
    var ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta);
    ta.select(); document.execCommand('copy'); document.body.removeChild(ta); done();
  }
};
"""
_JS = _JS + _JS_FAV


def _ring(score, color):
    r, c = 26, 2 * 3.14159 * 26
    filled = c * score / 100
    return f'''<svg viewBox="0 0 64 64" class="ring"><circle cx="32" cy="32" r="{r}" fill="none" stroke="#e8ecf1" stroke-width="6"/><circle cx="32" cy="32" r="{r}" fill="none" stroke="{color}" stroke-width="6" stroke-linecap="round" stroke-dasharray="{filled:.0f} {c:.0f}" transform="rotate(-90 32 32)"/><text x="32" y="38" text-anchor="middle" font-size="20" font-weight="700" fill="#1f2937">{score}</text></svg>'''


def _card(x):
    s = x.score or {}
    emoji = s.get("emoji", "⚪")
    color = LEVEL_COLOR.get(emoji, "#6b7280")
    img = H.escape(x.image) if x.image else ""
    ratio = s.get("ratio", 0)
    bar_w = max(4, min(100, int(ratio * 70))) if ratio else 4
    tags = "".join(f'<span class="tag">{H.escape(t)}</span>' for t in (x.tags or [])[:6])
    add = "".join(f'<div class="sg add">＋ {H.escape(t)}</div>' for t in s.get("add", []))
    minus = "".join(f'<div class="sg minus">－ {H.escape(t)}</div>' for t in s.get("minus", []))
    loc = "·".join(p for p in (x.district, x.bizarea, x.community) if p)
    meta = " | ".join(p for p in (x.layout, f"{x.area_sqm:g}㎡" if x.area_sqm else "",
                                  (x.orientation + "向") if x.orientation else "",
                                  x.floor_desc) if p)
    unit = f'{x.unit_price:g} 元/㎡/月' if x.unit_price else ""
    pf = {"贝壳": "pf bk", "房天下": "pf ft", "安居客": "pf aj", "58同城": "pf w5"}.get(x.platform, "pf")
    vr = ' <span class="tag vr">▶ 视频/VR</span>' if (x.has_vr or "有视频" in x.tags) else ""
    direct = ' <span class="tag direct">业主直租</span>' if "业主直租" in x.tags else ""
    hard = '<div class="hardwarn">疑似串串房 · 建议跳过，或要求甲醛检测报告后再看</div>' if s.get("hard_flag") else ""
    img_html = f'<img loading="lazy" src="{img}" alt="">' if img else '<div class="noimg">暂无图</div>'
    ratio_html = f'<span class="ratio">约为{H.escape(s.get("base_src",""))}均价 {ratio:.0%}</span>' if ratio else ""
    unit_html = f'<span class="unit">{unit}</span>' if unit else ""

    return f'''<div class="card{' lvred' if emoji == '🔴' else ''}" data-score="{s.get('total', 0)}" data-price="{x.price}" data-unit="{x.unit_price}" data-lv="{emoji}" data-title="{H.escape(x.title or loc)}" data-url="{H.escape(x.url)}" data-platform="{H.escape(x.platform)}">
  <button class="fav" title="加入收藏清单">☆</button>
  <div class="imgbox">{img_html}<span class="{pf}">{H.escape(x.platform)}</span></div>
  <div class="body">
    <div class="row1"><div class="title">{emoji} {H.escape(x.title or loc)}</div>{_ring(s.get('total', 0), color)}</div>
    <div class="price"><b>{x.price}</b> 元/月{unit_html}{ratio_html}</div>
    <div class="loc">{H.escape(loc)}<span class="meta">{H.escape(meta)}</span></div>
    <div class="ratio-bar"><i style="width:{bar_w}%"></i></div>
    <div class="tags">{tags}{vr}{direct}</div>
    {add}{minus}{hard}
    <div class="foot"><span class="dim">{H.escape(x.maintain or "")} {H.escape(x.brand or "")}</span>
      <a class="go" href="{H.escape(x.url)}" target="_blank" rel="noopener noreferrer">查看原房源 ↗</a></div>
  </div>
</div>'''


def build_html(city_cn, districts, pmin, pmax, rent_type, listings, baseline,
               source_stats, out_path):
    n_all = len(listings)
    n_green = sum(1 for x in listings if x.score and x.score["emoji"] == "🟢")
    n_red = sum(1 for x in listings if x.score and x.score["emoji"] == "🔴")
    n_hard = sum(1 for x in listings if x.score and x.score.get("hard_flag"))
    lst = sorted(listings, key=lambda x: -(x.score["total"] if x.score else 0))
    cards = "\n".join(_card(x) for x in lst)

    cond = f"{city_cn} · " + (f"{pmin}~{pmax} 元/月" if pmin or pmax else "价格不限") + \
           (" · " + "/".join(districts) if districts else "") + \
           (f" · {rent_type}" if rent_type else "")
    src = " ".join(f'<span class="src">{H.escape(k)} {v}条</span>' for k, v in source_stats.items())
    med = baseline.get("all_median", 0)
    now = time.strftime("%Y-%m-%d %H:%M")
    biz_lines = " · ".join(f"{k} {v}" for k, v in
                           sorted(baseline.get("dist", {}).items(), key=lambda kv: -kv[1])[:12])

    head = f'''<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="referrer" content="no-referrer">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>租房雷达 · {H.escape(cond)}</title>
<style>{_CSS}</style></head><body><div class="wrap">
<div class="hero">
  <h1>🏠 租房雷达 · 筛房报告</h1>
  <p>{H.escape(cond)}　·　生成于 {now}</p>
  <div class="statline">
    <span>房源 <b>{n_all}</b> 套</span>
    <span>🟢 放心优先看 <b>{n_green}</b></span>
    <span>🔴 高风险 <b>{n_red}</b>{f'（含疑似串串房 <b>{n_hard}</b> 套）' if n_hard else ''}</span>
    <span>全城单价中位 <b>{med}</b> 元/㎡/月</span>
    {src}
  </div>
</div>
<div class="toolbar">
  排序：<button class="on" data-k="score">综合分</button><button data-k="price">月租</button><button data-k="unit">单价</button>
　筛选：<button class="on" data-f="all">全部</button><button data-f="green">🟢 放心看</button><button data-f="red">🔴 高风险</button>
</div>
<div class="grid" id="grid">
'''

    foot = f'''
</div>
<div class="note">
<h3>📊 评分怎么来的（0~100）</h3>
真实可信 30%（平台权属核验、VR/视频、品牌机构、信息完整度、维护新鲜度）＋
性价比 25%（单价 vs {H.escape(biz_lines.split(' · ')[0] if biz_lines else '全城')}等基准中位数）＋
风险安全 25%（串串房信号、逼单话术、隔断嫌疑、直租/核验加分）＋
便利匹配 20%（地铁、区域命中、朝向楼层、整租合租匹配）。<br>
各区单价中位数基准（元/㎡/月）：{H.escape(biz_lines)}
<h3 style="margin-top:14px">🛡️ 看房防坑清单（串串房高发特征）</h3>
<li>警惕<b>「新装修 + 明显低于市价」</b>组合——串串房最典型特征；看房时闻气味、看家具是否全新杂牌。</li>
<li>要求出示<b>房产证/权属证明 + 房东身份证</b>；二房东要原始租赁合同及转租授权。</li>
<li>明显低于市价还催着交定金的，直接走。定金务必写明退还条件。</li>
<li>签约逐条核对：押付方式、维修责任、涨租条款、提前退租违约金、水电燃气单价。</li>
<li>新装修房建议做<b>甲醛检测（CMA 资质机构报告才有维权效力）</b>，或合同加「甲醛超标无责退租」条款。</li>
<li>本报告由公开挂牌信息自动生成，价格与描述以平台为准；评分仅供筛房参考，不构成任何担保。</li>
</div>
<p class="hint">数据来源：{H.escape("、".join(source_stats.keys()))}（安居客/58 反爬受限时自动跳过；闲鱼、小红书需登录态，可在 ZCode 会话里让 AI 用浏览器代查）。图片版权归原平台所有。</p>
</div>
<div class="favbar" id="favbar"><span id="favcount">已选 0 套</span><button class="copy" id="favcopy">📋 复制收藏清单</button><button class="clear" id="favclear">清空</button></div>
<script>const grid=document.getElementById('grid');{_JS}</script>
</body></html>'''

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(head + cards + foot)
    return out_path
