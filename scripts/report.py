#!/usr/bin/env python3
"""Shared HTML report template for coach analyses (Appendix B §10).

Every ride / sleep / metric analysis renders through this so reports look and read the
same way. Self-contained: charts are base64-embedded, no external assets, no CDN.

    from report import Report
    r = Report("Title", subtitle="...", sources=["Garmin get_activity_details", ...])
    r.kpis([("Label","BIG","sub"), ...])
    r.section("1. Headline")
    r.prose("**bold** and plain text")
    r.callout("good", "What improved", "...")
    r.table(["h1","h2"], [["a","b"]], accent={1:"good"})
    r.chart("charts/x.png", "caption")
    r.save("reports/2026-08-26_thing.html")
"""
import base64, datetime, html, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CSS = """
:root{--bg:#0d1220;--card:#161f31;--card2:#1b2740;--tx:#e8edf7;--mut:#94a2be;--grid:#26324a;
--acc:#4f8cff;--good:#4ade80;--warn:#e6a23c;--bad:#ff5d5d;--info:#2fd4c6}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);
 font:15px/1.62 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:28px 18px 64px}
header{border-bottom:1px solid var(--grid);padding-bottom:20px;margin-bottom:26px}
h1{font-size:26px;line-height:1.25;margin:0 0 8px}
.sub{color:var(--mut);font-size:15px;margin:0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:22px 0 28px}
.kpi{background:var(--card);border:1px solid var(--grid);border-radius:12px;padding:15px 17px}
.kpi .l{color:var(--mut);font-size:12.5px;margin-bottom:7px}
.kpi .v{font-size:26px;font-weight:700;line-height:1.15}
.kpi .s{color:var(--mut);font-size:12.5px;margin-top:6px}
section{background:var(--card);border:1px solid var(--grid);border-radius:14px;
 padding:20px 22px;margin-bottom:18px}
section h2{font-size:17px;margin:0 0 14px;padding-bottom:11px;border-bottom:1px solid var(--grid)}
p{margin:0 0 12px}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:6px 0 14px}
table{border-collapse:collapse;width:100%;min-width:440px;font-size:14px}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--grid);white-space:nowrap}
th{color:var(--mut);font-weight:600;font-size:12.5px;text-transform:uppercase;letter-spacing:.4px}
tbody tr:hover{background:var(--card2)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.good{color:var(--good)}.bad{color:var(--bad)}.warn{color:var(--warn)}.info{color:var(--info)}
.co{border-left:3px solid var(--acc);background:var(--card2);border-radius:0 10px 10px 0;
 padding:13px 16px;margin:0 0 14px}
.co .t{font-weight:700;margin-bottom:5px;font-size:14.5px}
.co.good{border-color:var(--good)}.co.bad{border-color:var(--bad)}
.co.warn{border-color:var(--warn)}.co.info{border-color:var(--info)}
figure{margin:6px 0 10px}
img{max-width:100%;height:auto;border-radius:10px;display:block;border:1px solid var(--grid)}
figcaption{color:var(--mut);font-size:12.5px;margin-top:8px}
ul{margin:0 0 12px;padding-left:20px}li{margin-bottom:6px}
code{background:var(--card2);padding:1.5px 6px;border-radius:5px;font-size:13px}
footer{color:var(--mut);font-size:12.5px;border-top:1px solid var(--grid);
 padding-top:16px;margin-top:26px}
@media(max-width:640px){.wrap{padding:18px 12px 48px}h1{font-size:21px}.kpi .v{font-size:22px}}
"""

def _md(s):
    s = html.escape(s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'`(.+?)`', r'<code>\1</code>', s)
    return s

class Report:
    def __init__(self, title, subtitle="", sources=None, date=None):
        self.title, self.subtitle = title, subtitle
        self.sources = sources or []
        self.date = date or datetime.date.today().isoformat()
        self._kpis, self._body = [], []

    def kpis(self, items):
        self._kpis = items; return self

    def section(self, heading):
        self._body.append(f'<section><h2>{_md(heading)}</h2>')
        self._open = True; return self

    def _end(self):
        if self._body and not self._body[-1].endswith('</section>'):
            self._body.append('</section>')

    def prose(self, text):
        for para in text.strip().split('\n\n'):
            self._body.append(f'<p>{_md(para)}</p>')
        return self

    def bullets(self, items):
        li = ''.join(f'<li>{_md(i)}</li>' for i in items)
        self._body.append(f'<ul>{li}</ul>'); return self

    def callout(self, kind, title, text):
        self._body.append(f'<div class="co {kind}"><div class="t">{_md(title)}</div>'
                          f'<div>{_md(text)}</div></div>'); return self

    def table(self, headers, rows, num_cols=(), accent=None):
        """accent: {row_index: 'good'|'bad'|'warn'} colours the last cell of that row."""
        accent = accent or {}
        th = ''.join(f'<th class="{"num" if i in num_cols else ""}">{_md(str(h))}</th>'
                     for i, h in enumerate(headers))
        tr = []
        for ri, row in enumerate(rows):
            cls = accent.get(ri, '')
            td = ''.join(
                f'<td class="{"num " if ci in num_cols else ""}'
                f'{cls if ci == len(row)-1 else ""}">{_md(str(c))}</td>'
                for ci, c in enumerate(row))
            tr.append(f'<tr>{td}</tr>')
        self._body.append(f'<div class="tw"><table><thead><tr>{th}</tr></thead>'
                          f'<tbody>{"".join(tr)}</tbody></table></div>')
        return self

    def chart(self, path, caption=""):
        p = path if os.path.isabs(path) else os.path.join(ROOT, path)
        if not os.path.exists(p):
            self._body.append(f'<p class="bad">[missing chart: {html.escape(path)}]</p>')
            return self
        b64 = base64.b64encode(open(p, 'rb').read()).decode()
        cap = f'<figcaption>{_md(caption)}</figcaption>' if caption else ''
        self._body.append(f'<figure><img src="data:image/png;base64,{b64}" alt="">{cap}</figure>')
        return self

    def save(self, path):
        self._end()
        out = path if os.path.isabs(path) else os.path.join(ROOT, path)
        kp = ''.join(f'<div class="kpi"><div class="l">{_md(l)}</div>'
                     f'<div class="v">{_md(v)}</div><div class="s">{_md(s)}</div></div>'
                     for l, v, s in self._kpis)
        src = (' · '.join(html.escape(s) for s in self.sources)) or '—'
        doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(self.title)}</title><style>{CSS}</style></head><body><div class="wrap">
<header><h1>{_md(self.title)}</h1><p class="sub">{_md(self.subtitle)}</p></header>
{f'<div class="kpis">{kp}</div>' if kp else ''}
{''.join(self._body)}
<footer>Generated {self.date} by the AI coach · Sources: {src}</footer>
</div></body></html>"""
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, 'w').write(doc)
        print(f"✅ {out}  ({len(doc)/1024:.0f} KB)")
        return out
