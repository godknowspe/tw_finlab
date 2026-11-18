"""Build one self-contained report.html from results.json.   python -m research.entry_timing.report"""
import json
from pathlib import Path

HERE = Path(__file__).parent

TEMPLATE = r"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><title>還沒投入的錢：什麼時候進場</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#0d1117;color:#c9d1d9;font:13px/1.6 -apple-system,"Noto Sans CJK TC","Microsoft JhengHei",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:14px 18px 40px}h1{font-size:17px;color:#fff;margin:4px 0 2px}h2{font-size:14px;color:#fff;margin:22px 0 6px}
.bar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:8px 12px;margin:10px 0}
.bar label{display:flex;gap:6px;align-items:center;color:#8b949e}select,input[type=range]{background:#0d1117;color:#c9d1d9;border:1px solid #30363d;border-radius:5px;padding:3px 6px}
.tabs button{background:#161b22;color:#c9d1d9;border:1px solid #30363d;border-radius:5px;padding:4px 10px;cursor:pointer}.tabs button.on{background:#1f6feb;border-color:#1f6feb;color:#fff}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}th,td{padding:4px 8px;text-align:right;border-bottom:1px solid #21262d;white-space:nowrap}th{color:#8b949e;font-weight:500}th:first-child,td:first-child{text-align:left}
.pos{color:#3fb950}.neg{color:#f85149}.dim{color:#6e7681}.warn{color:#d29922}tr.me td{background:#1f6feb1f}
.note{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:9px 12px;margin:8px 0;color:#9da7b3}.alert{border-color:#9e6a03;background:#2d2305;color:#e3c066}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px 12px}
.bar2{height:10px;border-radius:3px;background:#21262d;position:relative;overflow:hidden}.bar2 i{position:absolute;left:0;top:0;bottom:0;background:#3fb950}
canvas{width:100%;height:260px;background:#0d1117;border:1px solid #21262d;border-radius:6px}
</style></head><body><div class="wrap">
<h1>還沒投入的錢：一次買滿，還是分批／等回撤？</h1>
<div class="dim">用歷史價格的滾動視窗比較。每個策略從視窗第一天持有 1.0 的現金，在視窗最後一天估值，與「第一天一次買滿」相比。</div>
<div class="bar"><span class="tabs" id="sym"></span>
<label>持有期<select id="hz"></select></label><label>閒置現金利率<select id="rate"></select></label></div>
<div id="warn"></div>
<h2>你的情境怎麼比？</h2>
<div class="bar" id="build"></div>
<div class="grid" id="cards"></div>
<div id="dist"></div>
<h2>所有策略一覽 <span class="dim" style="font-weight:400">· 點欄位標題排序</span></h2>
<div id="tbl"></div>
<div class="note">怎麼讀：「贏」是期末財富勝過一次買滿的視窗比例；「中位差」是中位數的視窗期末財富相對一次買滿多（少）多少。<b>上漲視窗</b>＝期末價格高於起點的視窗，<b>下跌視窗</b>＝低於。
你事先並不知道自己會落在哪一種，所以單看「下跌視窗贏很多」是事後諸葛，要看兩者合起來的總體結果與最差情況。</div>
<div class="note alert" id="caveat"></div>
</div>
<script>
const R=__DATA__;let sym='0050',hz='3年',rate='現金0%',sortKey='median',sortDir=-1;
const $=id=>document.getElementById(id);
// Keys are JSON text written by Python; compare parsed fields, never the raw string.
const find=(rows,want)=>{for(const [k,c] of Object.entries(rows)){const p=JSON.parse(k);if(Object.entries(want).every(([f,v])=>p[f]===v))return c}return null};
const pc=(v,d=1,sign=true)=>v==null?'<span class="dim">—</span>':((sign&&v>0?'+':'')+(v*100).toFixed(d)+'%');
const cls=v=>v==null?'':v>=0?'pos':'neg';
const S=()=>R.symbols[sym].horizons[hz];
let up=0.5,step=0.10,tr=2,dl=0;
function strategies(){const rows=S().rows[rate],out=[];
 for(const [k,c] of Object.entries(rows)){const p=JSON.parse(k);
  if(p.deadline&&hz==='1年')continue; // a 12-month deadline equals the whole 1-year horizon: identical rows
  const name=p.kind==='spread'?`分${p.months}個月平均買`:`先買${p.upfront*100}%，每跌${p.step*100}%加碼×${p.tranches}${p.deadline?`，${p.deadline}個月期限`:'，不設期限'}${p.upfront===0?'（全部等回撤）':''}`;
  out.push({k,p,name,c})}return out}
function render(){
 if(hz==='1年')dl=0;
 const h=S(),lump=h.lump;
 $('warn').innerHTML=`<div class="note">${sym==='0050'?'0050 含息總報酬':'^TWII 價格指數（不含息）'}，${R.symbols[sym].first} → ${R.symbols[sym].last}（${R.symbols[sym].years} 年）。
  持有期 ${hz}：共 ${h.windows} 個滾動視窗，但互相重疊，<b class="warn">實際只相當於約 ${h.independent} 段獨立的歷史</b>。一次買滿的期末報酬中位數 ${pc(lump.median,0)}（5%～95%：${pc(lump.p5,0)} ~ ${pc(lump.p95,0)}），期末上漲的視窗占 ${(lump.up_share*100).toFixed(0)}%。</div>`;
 const pos=(S().rows[rate]);const want={deadline:dl,kind:'dip',step:step,tranches:tr,upfront:up};
 $('build').innerHTML=`<label>先買 <select id="up">${[0,0.5,0.7].map(v=>`<option value="${v}" ${v===up?'selected':''}>${v*100}%</option>`).join('')}</select></label>
  <label>每跌 <select id="st">${[0.05,0.1,0.15,0.2,0.3].map(v=>`<option value="${v}" ${v===step?'selected':''}>${v*100}%</option>`).join('')}</select> 加碼</label>
  <label>分 <select id="tr">${[2,3].map(v=>`<option ${v===tr?'selected':''}>${v}</option>`).join('')}</select> 檔</label>
  <label>期限 <select id="dl"><option value="0" ${dl===0?'selected':''}>不設</option>${hz==='1年'?'':`<option value="12" ${dl===12?'selected':''}>12 個月後強制投入</option>`}</select></label>`;
 ['up','st','tr','dl'].forEach(id=>$(id).onchange=e=>{const v=+e.target.value;if(id==='up')up=v;if(id==='st')step=v;if(id==='tr')tr=v;if(id==='dl')dl=v;render()});
 const mine=find(pos,want);const sp=find(pos,{kind:'spread',months:12});
 const card=(title,c,sub)=>c?`<div class="card"><div style="color:#fff;font-weight:600">${title}</div><div class="dim" style="margin-bottom:6px">${sub}</div>
  <div>勝過一次買滿：<b>${pc(c.win,0,false)}</b></div><div class="bar2"><i style="width:${c.win*100}%"></i></div>
  <table style="margin-top:6px"><tr><td>中位數期末財富差</td><td class="${cls(c.median)}">${pc(c.median)}</td></tr><tr><td>平均</td><td class="${cls(c.mean)}">${pc(c.mean)}</td></tr>
  <tr><td>最差視窗</td><td class="neg">${pc(c.worst)}</td></tr><tr><td>最好視窗</td><td class="pos">${pc(c.best)}</td></tr>
  <tr><td>上漲視窗贏（${c.n_up} 個）</td><td>${pc(c.win_when_up,0,false)}</td></tr><tr><td>下跌視窗贏（${c.n_down} 個）</td><td>${c.n_down?pc(c.win_when_down,0,false):'<span class="warn">沒有下跌視窗</span>'}</td></tr></table></div>`
  :`<div class="card dim">這個組合不在預先算好的網格內（檔數×間距超過 80%）。</div>`;
 $('cards').innerHTML=card('你選的組合',mine,`先買 ${up*100}%，每跌 ${step*100}% 加碼，${tr} 檔${dl?'，12 個月期限':''}${mine?`；平均有 ${(mine.invested_share*100).toFixed(0)}% 的加碼檔被觸發`:''}`)+card('對照：分 12 個月平均買',sp,'每個月買 1/12，其餘現金等待');
 drawDist();table();
 const nd=Object.values(R.symbols[sym].horizons).map(x=>x);
 $('caveat').innerHTML=`<b>這些結果的限制</b><br>· 視窗互相重疊，視窗數不是證據數；${sym==='0050'?'0050 只有 12.9 年，且<b>幾乎整段是多頭</b>：3、5 年持有期沒有任何下跌視窗，「等回撤」的好處根本沒機會被測到，它在這份資料裡的劣勢要打折看。':'^TWII 含 2000、2008 兩次大跌，但仍只有 27.9 年，約 2 次獨立的熊市。'}
 <br>· 我是在 5 個間距、2 個檔數、3 種先買比例中看過表現才標出重點，<b>表現最好的那一格有多重比較的偏差，不代表它真的比較好</b>。
 <br>· 回撤以「視窗起點以來的最高價」計算；沒有交易成本；閒置現金依上方利率計息；上漲視窗代表「期末比起點高」，不是「過程中沒有跌」。
 <br>· 這是歷史資料的比較，不保證未來，也不是投資建議。`;
}
function drawDist(){
 const P=S().paths;const names=Object.keys(P.vs_lump);const n=P.dates.length;
 $('dist').innerHTML='<h2>每個起點的結果 <span class="dim" style="font-weight:400">· 一個點 = 一個起點日；縱軸 = 該策略期末財富相對一次買滿多（少）多少；背景色 = 該視窗期末市場漲(綠)跌(紅)</span></h2>';
 const cv=document.createElement('canvas');$('dist').appendChild(cv);
 const r=cv.getBoundingClientRect(),W=cv.width=Math.max(600,r.width*2),H=cv.height=520,g=cv.getContext('2d');
 const all=names.flatMap(k=>P.vs_lump[k]),lo=Math.min(-0.05,...all),hi=Math.max(0.05,...all);
 const X=i=>40+(W-60)*i/(n-1),Y=v=>10+(H-30)*(1-(v-lo)/(hi-lo));
 for(let i=0;i<n;i++){g.fillStyle=P.lump[i]>=0?'rgba(63,185,80,.10)':'rgba(248,81,73,.18)';g.fillRect(X(i)-(W-60)/n/2,10,(W-60)/n+1,H-30)}
 g.strokeStyle='#30363d';g.fillStyle='#8b949e';g.font='20px sans-serif';
 for(let k=0;k<=5;k++){const v=lo+(hi-lo)*k/5,y=Y(v);g.beginPath();g.moveTo(40,y);g.lineTo(W-20,y);g.stroke();g.fillText((v*100).toFixed(0)+'%',0,y+6)}
 g.strokeStyle='#e6edf3';g.lineWidth=2;g.beginPath();g.moveTo(40,Y(0));g.lineTo(W-20,Y(0));g.stroke();g.lineWidth=1;
 const colors=['#f2c94c','#f85149','#58a6ff'];
 names.forEach((k,j)=>{g.fillStyle=colors[j%3];P.vs_lump[k].forEach((v,i)=>{g.fillRect(X(i)-1.5,Y(v)-1.5,3,3)});g.fillText('■ '+k,60+j*Math.min(440,W/3),H-4)});
 const y0=P.dates[0],y1=P.dates[n-1];g.fillStyle='#8b949e';g.fillText(y0,40,H-4-24);g.fillText('起點日 → '+y1,W-260,H-4-24);
}
function table(){
 const rows=strategies();
 const head=[['name','策略'],['win','贏'],['median','中位差'],['mean','平均差'],['worst','最差'],['best','最好'],['win_when_up','上漲視窗贏'],['win_when_down','下跌視窗贏']];
 const isMine=p=>p.kind==='dip'&&p.deadline===dl&&p.step===step&&p.tranches===tr&&p.upfront===up;
 $('tbl').innerHTML=`<table><tr>${head.map(([k,l])=>`<th style="cursor:pointer" data-k="${k}">${l}${sortKey===k?(sortDir>0?' ↑':' ↓'):''}</th>`).join('')}</tr>`+
  rows.sort((a,b)=>sortKey==='name'?a.name.localeCompare(b.name)*sortDir:((b.c[sortKey]??-9)-(a.c[sortKey]??-9))*(sortDir<0?1:-1)).map(r=>`<tr class="${isMine(r.p)?'me':''}"><td>${r.name}</td><td>${pc(r.c.win,0,false)}</td>
  <td class="${cls(r.c.median)}">${pc(r.c.median)}</td><td class="${cls(r.c.mean)}">${pc(r.c.mean)}</td><td class="neg">${pc(r.c.worst)}</td><td class="pos">${pc(r.c.best)}</td>
  <td>${pc(r.c.win_when_up,0,false)}</td><td>${r.c.n_down?pc(r.c.win_when_down,0,false):'<span class="dim">無</span>'}</td></tr>`).join('')+'</table>';
 document.querySelectorAll('#tbl th').forEach(th=>th.onclick=()=>{const k=th.dataset.k;if(sortKey===k)sortDir*=-1;else{sortKey=k;sortDir=-1}table()});
}
function boot(){
 $('sym').innerHTML=Object.keys(R.symbols).map(s=>`<button data-s="${s}">${s==='0050'?'0050（含息）':'^TWII（加權指數）'}</button>`).join('');
 $('sym').onclick=e=>{if(e.target.dataset.s){sym=e.target.dataset.s;fix();render()}};
 $('hz').onchange=e=>{hz=e.target.value;render()};$('rate').innerHTML=R.rates.map(r=>`<option>${r}</option>`).join('');$('rate').onchange=e=>{rate=e.target.value;render()};fix();render();
}
function fix(){const hs=Object.keys(R.symbols[sym].horizons);if(!hs.includes(hz))hz=hs[0];
 $('hz').innerHTML=hs.map(h=>`<option ${h===hz?'selected':''}>${h}</option>`).join('');
 document.querySelectorAll('#sym button').forEach(b=>b.classList.toggle('on',b.dataset.s===sym))}
boot();
</script></body></html>"""


def main():
    results = json.loads((HERE / "results.json").read_text())
    out = HERE / "report.html"
    out.write_text(TEMPLATE.replace("__DATA__", json.dumps(results, ensure_ascii=False)))
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
