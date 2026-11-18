"""Build one self-contained report.html from results.json.   python -m research.twii_regime.report

The page embeds lightweight-charts 3.8 and the data, so it opens from disk with no server and
touches nothing of the dashboard.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
LWC = HERE.parents[1] / "frontend/node_modules/lightweight-charts/dist/lightweight-charts.standalone.production.js"

TEMPLATE = r"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><title>台股大盤多空規則研究</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#0d1117;color:#c9d1d9;font:13px/1.5 -apple-system,"Noto Sans CJK TC","Microsoft JhengHei",sans-serif}
header{padding:10px 16px;border-bottom:1px solid #30363d;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
h1{font-size:15px;margin:0;color:#fff}.tabs button,select{background:#161b22;color:#c9d1d9;border:1px solid #30363d;border-radius:5px;padding:4px 10px;cursor:pointer}
.tabs button.on{background:#1f6feb;color:#fff;border-color:#1f6feb}
main{display:grid;grid-template-columns:minmax(0,1fr) 430px;gap:0}
#left{min-width:0}#right{border-left:1px solid #30363d;padding:10px 12px;overflow:auto;font-size:12px;height:calc(100vh - 47px)}
.chart{position:relative;border-bottom:1px solid #21262d}.chart .lab{position:absolute;left:8px;top:4px;z-index:5;font-size:11px;color:#8b949e;pointer-events:none}
canvas.shade{position:absolute;left:0;top:0;pointer-events:none;z-index:2}
table{border-collapse:collapse;width:max-content;min-width:100%;font-variant-numeric:tabular-nums}th,td{padding:3px 5px;text-align:right;border-bottom:1px solid #21262d;white-space:nowrap}
th{color:#8b949e;font-weight:500}th:first-child,td:first-child{text-align:left}tr.sel td{background:#1f6feb22}tr.click{cursor:pointer}tr.click:hover td{background:#ffffff0a}
.pos{color:#3fb950}.neg{color:#f85149}.dim{color:#6e7681}.warn{color:#d29922}
.note{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:8px 10px;margin:8px 0;color:#8b949e;line-height:1.55}
h2{font-size:12px;margin:14px 0 4px;color:#fff}.legend{display:flex;gap:10px;flex-wrap:wrap;font-size:11px;margin:4px 0}.legend i{display:inline-block;width:10px;height:3px;margin-right:4px;vertical-align:middle}
</style></head><body>
<header><h1>台股大盤多空規則研究</h1><span class="tabs" id="exps"></span>
<label>成本<select id="scen"></select></label><label>K 線顯示策略<select id="strat"></select></label>
<span class="dim" id="meta"></span></header>
<main><div id="left"><div class="chart" id="cPrice" style="height:46vh"><div class="lab" id="labPrice"></div></div>
<div class="chart" id="cEq" style="height:26vh"><div class="lab">權益曲線（起點 = 1，對數刻度）</div></div>
<div class="chart" id="cDd" style="height:18vh"><div class="lab">回撤 / 持股比例</div></div></div>
<div id="right" style="overflow-x:auto"><div class="legend" id="legend"></div><div id="tables"></div></div></main>
<script>__LWC__</script>
<script>
const R=__DATA__;
const COL={"A":"#8b949e","B":"#3fb950","C":"#f2c94c","D":"#56ccf2","E":"#bc8cff","F":"#ff7eb9","G":"#484f58","H":"#f2994a"};
const colorOf=k=>COL[k[0]]||"#fff";
const pct=(v,d=1)=>v==null?'<span class="dim">N/A</span>':(v*100).toFixed(d)+'%';
const num=(v,d=2)=>v==null?'<span class="dim">N/A</span>':v.toFixed(d);
let syncing=false,exp='investment',scen='含成本',strat='B 站上200日線',charts={},series={};
const el=id=>document.getElementById(id);
const E=()=>R.experiments[exp];

function mk(id,h){const c=LightweightCharts.createChart(el(id),{width:el(id).clientWidth,height:el(id).clientHeight,
 layout:{background:{type:'solid',color:'#0d1117'},textColor:'#c9d1d9',fontSize:11},grid:{vertLines:{color:'#161b22'},horzLines:{color:'#161b22'}},
 rightPriceScale:{borderColor:'#30363d',minimumWidth:64,mode:id==='cDd'?0:1},timeScale:{borderColor:'#30363d',visible:id==='cDd',minBarSpacing:0.05,rightOffset:2},crosshair:{mode:0}});return c}
function init(){
 charts.price=mk('cPrice');charts.eq=mk('cEq');charts.dd=mk('cDd');
 const all=Object.values(charts);
 all.forEach(c=>c.timeScale().subscribeVisibleLogicalRangeChange(r=>{if(syncing||!r)return;syncing=true;all.forEach(o=>o!==c&&o.timeScale().setVisibleLogicalRange(r));syncing=false;shade()}));
 window.addEventListener('resize',()=>{all.forEach((c,i)=>{const e=el(['cPrice','cEq','cDd'][i]);c.resize(e.clientWidth,e.clientHeight)});shade()});
}
function build(){
 const e=E(),tradeSym=e.label.includes('0050')?'0050.TW':'^TWII';
 ['price','eq','dd'].forEach(k=>{(series[k]||[]).forEach(s=>charts[k].removeSeries(s));series[k]=[]});
 const bars=R.bars[tradeSym].filter(b=>b[0]>=e.start).map(b=>({time:b[0],open:b[1],high:b[2],low:b[3],close:b[4]}));
 const cs=charts.price.addCandlestickSeries({upColor:'#f85149',downColor:'#3fb950',borderVisible:false,wickUpColor:'#f85149',wickDownColor:'#3fb950'});
 cs.setData(bars.map(b=>({...b})));series.price.push(cs);
 const fills=(e.fills[strat]||[]);
 cs.setMarkers(fills.map(f=>({time:f.date,position:f.side==='BUY'?'belowBar':'aboveBar',color:f.side==='BUY'?'#58a6ff':'#f2c94c',shape:f.side==='BUY'?'arrowUp':'arrowDown',
   text:''})));
 for(const k of Object.keys(e.curves)){
  const s=charts.eq.addLineSeries({color:colorOf(k),lineWidth:k===strat?3:1,priceLineVisible:false,lastValueVisible:k===strat||k[0]==='A',title:k[0]});
  s.setData(e.curves[k].equity.map(([t,v])=>({time:t,value:v})));series.eq.push(s)}
 const dd=charts.dd.addLineSeries({color:'#f85149',lineWidth:1,priceLineVisible:false,title:'策略回撤'});dd.setData(e.curves[strat].drawdown.map(([t,v])=>({time:t,value:v*100})));series.dd.push(dd);
 const bh=charts.dd.addLineSeries({color:'#484f58',lineWidth:1,priceLineVisible:false,title:'買進持有回撤'});bh.setData(e.curves['A 買進持有'].drawdown.map(([t,v])=>({time:t,value:v*100})));series.dd.push(bh);
 const ex=charts.dd.addAreaSeries({lineColor:'#1f6feb',topColor:'#1f6feb33',bottomColor:'#1f6feb05',lineWidth:1,priceScaleId:'expo',priceLineVisible:false,lastValueVisible:false});
 ex.priceScale().applyOptions({scaleMargins:{top:0.7,bottom:0}});ex.setData(e.curves[strat].weight.map(([t,v])=>({time:t,value:v})));series.dd.push(ex);
 el('labPrice').textContent=(tradeSym==='0050.TW'?'0050（已還原分割）':'^TWII 加權指數')+' · '+strat+' · 箭頭 = 實際成交日（隔日開盤，藍=買 黃=賣）· 底色 = 持有期間（綠=該回合賺 紅=賠）· 價格為對數刻度';
 setRange(bars.length);window.cur={bars,episodes:e.episodes[strat]||[]};shade();
}
function setRange(n){syncing=true;const r={from:0,to:n+2};Object.values(charts).forEach(c=>c.timeScale().setVisibleLogicalRange(r));syncing=false;shade()}
function shade(){
 const host=el('cPrice');let cv=host.querySelector('canvas.shade');if(!cv){cv=document.createElement('canvas');cv.className='shade';host.appendChild(cv)}
 const w=host.clientWidth,h=host.clientHeight;cv.width=w;cv.height=h;cv.style.width=w+'px';cv.style.height=h+'px';
 const g=cv.getContext('2d');g.clearRect(0,0,w,h);const ts=charts.price.timeScale();
 for(const ep of (window.cur?window.cur.episodes:[])){
  const x1=ts.timeToCoordinate(ep.entry),x2=ts.timeToCoordinate(ep.exit);if(x1==null&&x2==null)continue;
  const a=x1==null?0:x1,b=x2==null?w:x2;g.fillStyle=ep.ret>=0?'rgba(63,185,80,.10)':'rgba(248,81,73,.10)';g.fillRect(a,0,Math.max(1,b-a),h)}
}
function jump(i){const ep=window.cur.episodes[i];const idx=window.cur.bars.findIndex(b=>b.time>=ep.entry);const j=window.cur.bars.findIndex(b=>b.time>=ep.exit);
 const pad=15;charts.price.timeScale().setVisibleLogicalRange({from:Math.max(0,idx-pad),to:(j<0?window.cur.bars.length:j)+pad});
 document.querySelectorAll('#ep tr').forEach(r=>r.classList.toggle('sel',r.dataset.i==i))}
function tables(){
 const e=E(),S=e.scenarios[scen];
 const rows=Object.entries(S).map(([k,s])=>`<tr class="click ${k===strat?'sel':''}" data-k="${k}"><td><i style="display:inline-block;width:8px;height:8px;background:${colorOf(k)};margin-right:5px"></i>${k}</td>
  <td>${pct(s.cagr)}</td><td>${pct(s.vol)}</td><td class="neg">${pct(s.max_drawdown)}</td><td>${num(s.sharpe)}</td><td>${pct(s.win_rate,0)}</td><td>${s.episodes_closed}</td><td>${num(s.payoff,1)}</td><td>${pct(s.exposure_avg,0)}</td><td>${s.fills}</td></tr>`).join('');
 const b=e.bootstrap.result;const bt=Object.entries(b).filter(([k])=>k[0]!=='G').map(([k,v])=>`<tr><td>${k}</td><td>${v.d_cagr.map(x=>(x*100).toFixed(1)).join(' / ')}</td><td>${v.d_mdd.map(x=>(x*100).toFixed(1)).join(' / ')}</td><td>${(v.p_better_cagr*100).toFixed(0)}%</td></tr>`).join('');
 const sens=Object.entries(e.sensitivity['B 站上200日線']).map(([n,v])=>`<tr><td>${n} 日</td><td>${pct(v.cagr)}</td><td class="neg">${pct(v.max_drawdown)}</td><td>${num(v.sharpe)}</td><td>${v.fills}</td></tr>`).join('');
 const hv=['前半','後半'].map(h=>{const d=e.halves[h];return `<tr><td>${h}（${d._from} 起）</td>`+['A 買進持有',strat,'H 50%持有+50%現金'].map(k=>`<td>${pct(d[k].cagr)} / <span class="neg">${pct(d[k].max_drawdown,0)}</span></td>`).join('')+'</tr>'}).join('');
 const eps=(e.episodes[strat]||[]);
 const epRows=eps.map((p,i)=>`<tr class="click" data-i="${i}"><td>${p.entry}</td><td>${p.closed?p.exit:'<span class="warn">持有中</span>'}</td><td>${p.sessions}</td><td class="${p.ret>=0?'pos':'neg'}">${(p.ret*100).toFixed(1)}%</td></tr>`).join('');
 el('tables').innerHTML=`
 <div class="note">${e.label}<br>樣本 ${e.start} → ${e.end}。收盤出訊號、<b>隔日開盤成交</b>；買進前的隔夜跳空不算賺，賣出前的跳空照賠。所有參數用慣例值固定，沒有搜尋最佳化。</div>
 <h2>績效（${scen}）<span class="dim"> · 點列可切換 K 線上的進出</span></h2>
 <table id="perf"><tr><th>策略</th><th>年化</th><th>波動</th><th>最大回撤</th><th>夏普</th><th>勝率</th><th>回合</th><th>盈虧比</th><th>曝險</th><th>成交</th></tr>${rows}</table>
 <div class="note">勝率只算「空手→持有→空手」的完整回合；買進持有與不歸零的波動目標沒有完整回合，顯示 N/A。趨勢策略勝率低但賺大賠小（盈虧比高），要與年化和回撤一起看。</div>
 <h2>與買進持有的差距（同一批交易日抽區塊 bootstrap，120 日區塊 2000 次）</h2>
 <table><tr><th>策略</th><th>Δ年化 5/50/95%</th><th>Δ最大回撤 5/50/95%（點）</th><th>年化勝過A</th></tr>${bt}</table>
 <div class="note">這只量化「這段歷史樣本留給我們多大不確定性」，不是新行情，也不是未來回撤的上限。約 27 年（機制）/ 12 年（投資）只含少數幾次大跌，回撤的區間很寬。</div>
 <h2>參數敏感度（B 站上 N 日線）</h2><table><tr><th>N</th><th>年化</th><th>最大回撤</th><th>夏普</th><th>成交</th></tr>${sens}</table>
 <h2>前後半段（年化 / 最大回撤）<span class="dim"> · 整段樣本已看過，只作探索</span></h2>
 <table><tr><th></th><th>買進持有</th><th>${strat.slice(0,1)} 選定</th><th>H 一半</th></tr>${hv}</table>
 <h2>${strat} 的進出回合 <span class="dim">· 點一列跳到該段</span></h2>
 <div style="max-height:260px;overflow:auto"><table id="ep"><tr><th>進場</th><th>出場</th><th>天數</th><th>報酬</th></tr>${epRows||'<tr><td colspan=4 class="dim">此策略沒有完整回合</td></tr>'}</table></div>
 <div class="note warn">資料說明：0050 已把 2014-01-02 的 1:4 分割還原，股息另計入帳；Yahoo 的 0050 在 2014-07-23、2016-07-08 及 2025-06-11 至 06-17（共 8 個交易日，^TWII 當天有正常 K 線）沒有資料，這幾天沒有成交價，訊號延到下一個有價日成交。^TWII 為價格指數，不含股息，機制實驗不可直接交易。資料抓取時間 ${R.data.fetched_at}。</div>`;
 document.querySelectorAll('#perf tr.click').forEach(r=>r.onclick=()=>{strat=r.dataset.k;el('strat').value=strat;refresh()});
 document.querySelectorAll('#ep tr.click').forEach(r=>r.onclick=()=>jump(+r.dataset.i));
}
function refresh(){build();tables();}
function boot(){
 el('exps').innerHTML=Object.entries(R.experiments).map(([k,v])=>`<button data-k="${k}">${k==='investment'?'投資實驗（0050）':'機制實驗（^TWII）'}</button>`).join('');
 el('exps').onclick=ev=>{if(ev.target.dataset.k){exp=ev.target.dataset.k;sync();refresh()}};
 el('scen').innerHTML=Object.keys(E().scenarios).map(s=>`<option ${s===scen?'selected':''}>${s}</option>`).join('');el('scen').onchange=ev=>{scen=ev.target.value;tables()};
 el('strat').onchange=ev=>{strat=ev.target.value;refresh()};
 el('legend').innerHTML=Object.keys(E().curves).map(k=>`<span><i style="background:${colorOf(k)}"></i>${k}</span>`).join('');
 init();sync();refresh();
}
function sync(){
 document.querySelectorAll('#exps button').forEach(b=>b.classList.toggle('on',b.dataset.k===exp));
 el('strat').innerHTML=Object.keys(E().curves).filter(k=>k[0]!=='G').map(k=>`<option ${k===strat?'selected':''}>${k}</option>`).join('');
 if(!E().curves[strat])strat='B 站上200日線';el('strat').value=strat;
 el('meta').textContent=`資料 ${Object.entries(R.data.symbols).map(([s,m])=>s+' '+m.first+'→'+m.last).join(' · ')}`;
}
boot();
</script></body></html>"""


def main():
    results = json.loads((HERE / "results.json").read_text())
    html = TEMPLATE.replace("__LWC__", LWC.read_text()).replace("__DATA__", json.dumps(results, ensure_ascii=False))
    out = HERE / "report.html"
    out.write_text(html)
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
