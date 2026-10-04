"""results/results.json -> results/report.html (single-file dashboard).

Columns: ID, policy (expected), input, latency (ms), input tokens, cost (USD), Jev classification,
         classification correct, fired filters, filter set exact match
Charts:  accuracy per policy, latency per case, cost per policy, filter probability heatmap
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).parent / "results"
data = json.loads((OUT / "results.json").read_text())
for r in data["rows"]:                       # backfill primary_match for results from older runs
    if "error" in r or "primary_match" in r:
        continue
    if r["kind"] == "grounding":
        r["primary_match"] = r["exact_match"]
    else:
        r["primary_match"] = (r["primary_category"] == "none") if not r["expected"] else (r["primary_category"] in r["expected"])
ok = [r for r in data["rows"] if "error" not in r]
data["summary"].setdefault("primary_accuracy", round(sum(r["primary_match"] for r in ok) / max(len(ok), 1), 4))

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Jev Guardrail Benchmark</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{
  color-scheme:light;
  --surface:#fcfcfb; --surface-2:#f3f2ef; --border:#e2e0da;
  --text:#0b0b0b; --text-2:#52514e; --text-3:#8a887f;
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100; --s5:#e87ba4; --s6:#008300; --s7:#4a3aa7; --s8:#e34948;
  --good:#0ca30c; --critical:#d03b3b; --warning:#fab219;
  --seq100:#cde2fb; --seq250:#86b6ef; --seq400:#3987e5; --seq550:#1c5cab; --seq700:#0d366b;
  --grid:#e8e6e0;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    color-scheme:dark;
    --surface:#1a1a19; --surface-2:#242423; --border:#34332f;
    --text:#ffffff; --text-2:#c3c2b7; --text-3:#8d8c84;
    --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; --s5:#d55181; --s6:#008300; --s7:#9085e9; --s8:#e66767;
    --grid:#2c2c2a;
  }
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --surface:#1a1a19; --surface-2:#242423; --border:#34332f;
  --text:#ffffff; --text-2:#c3c2b7; --text-3:#8d8c84;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; --s5:#d55181; --s6:#008300; --s7:#9085e9; --s8:#e66767;
  --grid:#2c2c2a;
}
*{box-sizing:border-box}
body{margin:0;background:var(--surface);color:var(--text);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;padding:24px 16px 64px}
main{max-width:1200px;margin:0 auto}
h1{font-size:22px;margin:0 0 4px}
h2{font-size:15px;font-weight:600;margin:32px 0 10px;color:var(--text)}
.sub{color:var(--text-2);margin:0 0 20px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.tile{background:var(--surface-2);border:1px solid var(--border);border-radius:8px;padding:12px 14px}
.tile .k{font-size:12px;color:var(--text-2)}
.tile .v{font-size:24px;font-weight:600;letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.tile .u{font-size:12px;color:var(--text-3);margin-left:4px}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}
.card{background:var(--surface-2);border:1px solid var(--border);border-radius:8px;padding:14px}
.card h3{margin:0 0 8px;font-size:13px;font-weight:600;color:var(--text-2)}
.card canvas{width:100%!important;height:260px!important}
.card.tall canvas{height:420px!important}
.toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0 12px}
.toolbar label{color:var(--text-2);font-size:13px}
select,input[type=search]{background:var(--surface-2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:6px 8px;font:inherit}
.tablewrap{overflow-x:auto;border:1px solid var(--border);border-radius:8px}
table{border-collapse:collapse;width:100%;min-width:900px;font-variant-numeric:tabular-nums}
th,td{padding:8px 10px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top}
th{background:var(--surface-2);font-weight:600;color:var(--text-2);cursor:pointer;white-space:nowrap;position:sticky;top:0}
th .arrow{color:var(--text-3);font-size:11px;margin-left:3px}
td.num{text-align:right;white-space:nowrap}
td.text{max-width:380px;color:var(--text-2)}
.chip{display:inline-block;padding:1px 7px;border-radius:999px;font-size:12px;border:1px solid var(--border);background:var(--surface);margin:1px 2px 1px 0;white-space:nowrap}
.chip.fired{border-color:var(--s1);color:var(--text)}
.ok{color:var(--good);font-weight:600}.miss{color:var(--critical);font-weight:600}
.heat{display:grid;gap:2px;font-size:11px}
.heat .hd{color:var(--text-2);text-align:center;padding-bottom:4px;writing-mode:vertical-rl;transform:rotate(180deg);height:120px}
.heat .rl{color:var(--text-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:6px;line-height:20px}
.heat .c{height:20px;border-radius:3px;position:relative}
.heat .c[data-exp="1"]{outline:2px solid var(--s2);outline-offset:-2px}
.heat .c:hover::after{content:attr(data-tip);position:absolute;left:50%;bottom:110%;transform:translateX(-50%);background:var(--text);color:var(--surface);padding:3px 7px;border-radius:4px;white-space:nowrap;z-index:5;font-size:11px}
.legend{display:flex;gap:14px;flex-wrap:wrap;color:var(--text-2);font-size:12px;margin-top:8px;align-items:center}
.sw{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-2px;margin-right:4px}
.note{color:var(--text-2);font-size:13px}
</style>
</head>
<body>
<main>
<h1>Jev Guardrail Benchmark</h1>
<p class="sub" id="sub"></p>

<div class="tiles" id="tiles"></div>

<h2>Accuracy by Bedrock Guardrails policy type</h2>
<div class="grid2">
  <div class="card"><h3>Accuracy (%)</h3><canvas id="accChart"></canvas>
  <div class="legend"><span><i class="sw" style="background:var(--s1)"></i>Classification correct (primary_category)</span><span><i class="sw" style="background:var(--s3)"></i>Fired filter set equals expected set</span></div></div>
  <div class="card"><h3>Total cost per policy (USD); mean latency in tooltip</h3><canvas id="costChart"></canvas></div>
</div>

<h2>Latency per case</h2>
<div class="card tall"><h3>Round-trip time of the single request (ms); color shows whether the classification was correct</h3><canvas id="latChart"></canvas>
<div class="legend"><span><i class="sw" style="background:var(--s1)"></i>Correct</span><span><i class="sw" style="background:var(--s8)"></i>Incorrect</span></div></div>

<h2>Filter probability heatmap (Noul p(yes))</h2>
<div class="card"><div class="heat" id="heat"></div>
<div class="legend"><span>Darker = higher probability</span><span><i class="sw" style="outline:2px solid var(--s2);outline-offset:-2px"></i>Orange outline = expected label</span><span>Fires at or above threshold <b id="thr"></b></span></div></div>

<h2>All results</h2>
<div class="toolbar">
  <label>Policy <select id="fCat"><option value="">All</option></select></label>
  <label>Classification <select id="fRes"><option value="">All</option><option value="1">Correct</option><option value="0">Incorrect</option></select></label>
  <label>Filter set <select id="fExact"><option value="">All</option><option value="1">Match</option><option value="0">Mismatch</option></select></label>
  <input type="search" id="fText" placeholder="Search text…">
  <span class="note" id="count"></span>
</div>
<div class="tablewrap"><table id="tbl"><thead><tr>
  <th data-k="id">ID<span class="arrow"></span></th>
  <th data-k="category">Policy (expected)<span class="arrow"></span></th>
  <th data-k="text">Input<span class="arrow"></span></th>
  <th data-k="elapsed_ms">Latency ms<span class="arrow"></span></th>
  <th data-k="input_tokens">Input tokens<span class="arrow"></span></th>
  <th data-k="cost_usd">Cost USD<span class="arrow"></span></th>
  <th data-k="primary_category">Jev classification<span class="arrow"></span></th>
  <th data-k="primary_match">Correct<span class="arrow"></span></th>
  <th>Fired filters (p ≥ threshold)</th>
  <th data-k="exact_match">Filter set match<span class="arrow"></span></th>
</tr></thead><tbody></tbody></table></div>
<p class="note" style="margin-top:10px"><b>Correct</b> = Jev's primary_category is one of the expected labels (or none for a safe case). <b>Filter set match</b> = the set of Noul filters that fired at or above the threshold equals the expected label set exactly. Example: hate_1 is classified correctly as hate, but the insults filter also fired, so the set does not match.</p>
<p class="note">Cost = input tokens × $0.042 / 1M (output tokens are free, docs.typesafe.ai/models). Latency is the client-side round-trip time and includes network delay.</p>
</main>
<script>
const DATA = __DATA__;
const rows = DATA.rows.filter(r => !r.error);
const S = DATA.summary;
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const fmt = (n, d=1) => n==null ? '—' : Number(n).toLocaleString('en-US',{maximumFractionDigits:d, minimumFractionDigits:d});

document.getElementById('sub').textContent =
  `model ${S.model} · ${S.n_ok}/${S.n_cases} cases · run ${S.run_at} · threshold ${S.threshold}`;
document.getElementById('thr').textContent = S.threshold;

// ── tiles
const tiles = [
  ['Classification accuracy', (S.primary_accuracy*100).toFixed(1), '%'],
  ['Filter set exact match', (S.accuracy*100).toFixed(1), '%'],
  ['Total cost', '$'+S.total_cost_usd.toFixed(4), ''],
  ['Total input tokens', S.total_input_tokens.toLocaleString(), ''],
  ['Mean latency', fmt(S.latency_ms.mean,0), 'ms'],
  ['p50 / p95', `${fmt(S.latency_ms.p50,0)} / ${fmt(S.latency_ms.p95,0)}`, 'ms'],
  ['Avg cost per case', '$'+(S.total_cost_usd/S.n_ok).toFixed(6), ''],
];
document.getElementById('tiles').innerHTML = tiles.map(([k,v,u]) =>
  `<div class="tile"><div class="k">${k}</div><div class="v">${v}<span class="u">${u}</span></div></div>`).join('');

// ── per-category aggregates
const cats = [...new Set(rows.map(r=>r.category))];
const agg = cats.map(c => { const rs = rows.filter(r=>r.category===c);
  return { c, n: rs.length, acc: rs.filter(r=>r.exact_match).length/rs.length*100,
           pacc: rs.filter(r=>r.primary_match).length/rs.length*100,
           cost: rs.reduce((a,r)=>a+r.cost_usd,0), lat: rs.reduce((a,r)=>a+r.elapsed_ms,0)/rs.length }; });

Chart.defaults.color = css('--text-2'); Chart.defaults.borderColor = css('--grid');
Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
const barOpts = (yTitle, extraTip) => ({ responsive:true, maintainAspectRatio:false,
  plugins:{ legend:{display:false}, tooltip:{callbacks:{ afterLabel: extraTip }} },
  scales:{ x:{grid:{display:false}}, y:{title:{display:true,text:yTitle}, grid:{color:css('--grid')}, border:{display:false}} } });

new Chart(document.getElementById('accChart'), { type:'bar',
  data:{ labels: agg.map(a=>a.c), datasets:[
    { label:'Classification correct', data: agg.map(a=>a.pacc), backgroundColor: css('--s1'), borderRadius:{topLeft:4,topRight:4}, borderSkipped:'bottom' },
    { label:'Filter set exact match', data: agg.map(a=>a.acc), backgroundColor: css('--s3'), borderRadius:{topLeft:4,topRight:4}, borderSkipped:'bottom' }]},
  options: { ...barOpts('%', ctx => `n = ${agg[ctx.dataIndex].n}`), scales:{ x:{grid:{display:false}}, y:{min:0, max:100, title:{display:true,text:'%'}, grid:{color:css('--grid')}, border:{display:false}} } } });
new Chart(document.getElementById('costChart'), { type:'bar',
  data:{ labels: agg.map(a=>a.c), datasets:[{ data: agg.map(a=>a.cost), backgroundColor: css('--s3'),
    borderRadius:{topLeft:4,topRight:4}, borderSkipped:'bottom', barPercentage:0.6, categoryPercentage:0.8 }]},
  options: barOpts('USD', ctx => `avg latency ${fmt(agg[ctx.dataIndex].lat,0)} ms · n = ${agg[ctx.dataIndex].n}`) });
new Chart(document.getElementById('latChart'), { type:'bar',
  data:{ labels: rows.map(r=>r.id), datasets:[{ data: rows.map(r=>r.elapsed_ms),
    backgroundColor: rows.map(r=> r.primary_match ? css('--s1') : css('--s8')),
    borderRadius:{topLeft:4,topRight:4}, borderSkipped:'bottom', barPercentage:0.7, categoryPercentage:0.9 }]},
  options: { ...barOpts('ms', ctx => { const r = rows[ctx.dataIndex]; return `${r.input_tokens} tok · $${r.cost_usd.toFixed(6)} · ${r.primary_category}`; }),
    scales:{ x:{ grid:{display:false}, ticks:{autoSkip:false, maxRotation:90, minRotation:60, font:{size:10}} },
             y:{ title:{display:true,text:'ms'}, grid:{color:css('--grid')}, border:{display:false} } } } });

// ── heatmap (moderation rows: 9 noul labels; grounding rows: 2)
const mod = rows.filter(r=>r.kind==='moderation'); const labels = Object.keys(mod[0]?.probs||{});
const grd = rows.filter(r=>r.kind==='grounding'); const glabels = Object.keys(grd[0]?.probs||{});
const allLabels = [...labels, ...glabels];
const heat = document.getElementById('heat');
heat.style.gridTemplateColumns = `180px repeat(${allLabels.length}, minmax(26px,1fr))`;
const seq = ['#f0efec','#cde2fb','#9ec5f4','#6da7ec','#3987e5','#256abf','#1c5cab','#0d366b'];
const seqDark = ['#2a2a28','#184f95','#1c5cab','#256abf','#2a78d6','#3987e5','#5598e7','#86b6ef'];
const isDark = matchMedia('(prefers-color-scheme: dark)').matches && document.documentElement.dataset.theme!=='light' || document.documentElement.dataset.theme==='dark';
const ramp = isDark ? seqDark : seq;
const shade = p => ramp[Math.min(ramp.length-1, Math.floor(p*ramp.length))];
let h = '<div></div>' + allLabels.map(l=>`<div class="hd">${l}</div>`).join('');
for (const r of rows) {
  h += `<div class="rl" title="${r.text.replace(/"/g,'&quot;')}">${r.id}</div>`;
  for (const l of allLabels) {
    const p = r.probs[l];
    if (p==null) { h += `<div class="c" style="background:transparent"></div>`; continue; }
    const exp = r.expected.includes(l) ? 1 : 0;
    h += `<div class="c" data-exp="${exp}" data-tip="${l}: ${p.toFixed(2)}${exp?' (expected)':''}" style="background:${shade(p)}"></div>`;
  }
}
heat.innerHTML = h;

// ── table
const tbody = document.querySelector('#tbl tbody');
const fCat = document.getElementById('fCat'); cats.forEach(c => fCat.insertAdjacentHTML('beforeend', `<option>${c}</option>`));
let sortKey = null, sortDir = 1;
function render() {
  const cat = fCat.value, res = document.getElementById('fRes').value, ex = document.getElementById('fExact').value, q = document.getElementById('fText').value.toLowerCase();
  let rs = rows.filter(r => (!cat || r.category===cat) && (res==='' || String(+r.primary_match)===res) && (ex==='' || String(+r.exact_match)===ex) && (!q || r.text.toLowerCase().includes(q) || r.id.includes(q)));
  if (sortKey) rs = [...rs].sort((a,b) => (a[sortKey] > b[sortKey] ? 1 : a[sortKey] < b[sortKey] ? -1 : 0) * sortDir);
  document.getElementById('count').textContent = `${rs.length} rows`;
  tbody.innerHTML = rs.map(r => `<tr>
    <td><code>${r.id}</code></td><td><span class="chip">${r.category}</span></td>
    <td class="text">${r.text.replace(/</g,'&lt;')}</td>
    <td class="num">${fmt(r.elapsed_ms,0)}</td><td class="num">${r.input_tokens}</td><td class="num">${r.cost_usd.toFixed(6)}</td>
    <td>${r.primary_category}${r.primary_confidence!=null ? ` <span class="note">(${r.primary_confidence.toFixed(2)})</span>`:''}${r.pii_type && r.pii_type!=='none' ? `<br><span class="note">pii: ${r.pii_type}</span>`:''}</td>
    <td class="${r.primary_match?'ok':'miss'}">${r.primary_match?'✓':'✗'}</td>
    <td>${r.fired.length ? r.fired.map(f=>`<span class="chip fired">${f} ${r.probs[f]!=null? r.probs[f].toFixed(2):''}</span>`).join('') : '<span class="note">—</span>'}
        ${!r.exact_match ? `<br><span class="note">expected: ${r.expected.length ? r.expected.join(', ') : '(none)'}</span>`:''}</td>
    <td class="${r.exact_match?'ok':'miss'}">${r.exact_match?'✓':'✗'}</td></tr>`).join('');
}
document.querySelectorAll('th[data-k]').forEach(th => th.addEventListener('click', () => {
  const k = th.dataset.k; sortDir = sortKey===k ? -sortDir : 1; sortKey = k;
  document.querySelectorAll('th .arrow').forEach(a=>a.textContent=''); th.querySelector('.arrow').textContent = sortDir>0?'▲':'▼'; render(); }));
['fCat','fRes','fExact'].forEach(id => document.getElementById(id).addEventListener('change', render));
document.getElementById('fText').addEventListener('input', render);
render();
</script>
</body></html>
"""

html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
(OUT / "report.html").write_text(html)
print(f"wrote {OUT/'report.html'} ({len(html)//1024} KB)")
