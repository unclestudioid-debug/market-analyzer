#!/usr/bin/env python3
"""
Market Analyzer: scrap berita + analisa gabungan untuk Kripto (BTC), XAUUSD (emas), Minyak (WTI).

Skor akhir = 70% skor berita + 30% skor teknikal (bisa diubah lewat --w-news / --w-tech).
Tanpa library tambahan, cukup Python 3.8+.

  python market_analyzer.py                 # hasil: report.html, report.json, headlines.txt
  python market_analyzer.py --hours 12
  python market_analyzer.py --w-news 0.6 --w-tech 0.4
  python market_analyzer.py --loop 30       # perbarui tiap 30 menit

Bukan saran investasi. Skor hanyalah ringkasan otomatis dari kata kunci berita dan indikator harian.
"""
import argparse, html, json, math, re, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as ET

UA = "Mozilla/5.0 (compatible; MarketAnalyzer/1.0)"

def gnews(q, lang="en", cc="US"):
    return f"https://news.google.com/rss/search?q={quote(q)}&hl={lang}&gl={cc}&ceid={cc}:{lang}"

ASSETS = {
    "btc": {"name": "Bitcoin", "label": "BTC/USD", "symbols": ["BTC-USD"], "feeds": [
        gnews("bitcoin when:1d"), gnews("bitcoin harga when:1d", "id", "ID"),
        "https://www.coindesk.com/arc/outputfeeds/rss/", "https://cointelegraph.com/rss"]},
    "eth": {"name": "Ethereum", "label": "ETH/USD", "symbols": ["ETH-USD"], "feeds": [
        gnews("ethereum when:1d"), gnews("ethereum harga when:1d", "id", "ID"),
        "https://www.coindesk.com/arc/outputfeeds/rss/", "https://cointelegraph.com/rss"]},
    "xrp": {"name": "XRP", "label": "XRP/USD", "symbols": ["XRP-USD"], "feeds": [
        gnews("XRP Ripple when:1d"), gnews("harga XRP Ripple when:1d", "id", "ID"),
        "https://www.coindesk.com/arc/outputfeeds/rss/", "https://cointelegraph.com/rss"]},
    "sol": {"name": "Solana", "label": "SOL/USD", "symbols": ["SOL-USD"], "feeds": [
        gnews("Solana SOL when:1d"), gnews("harga Solana when:1d", "id", "ID"),
        "https://www.coindesk.com/arc/outputfeeds/rss/", "https://cointelegraph.com/rss"]},
    "gold": {"name": "Emas", "label": "XAUUSD", "symbols": ["XAUUSD=X", "GC=F"], "feeds": [
        gnews("gold price OR XAUUSD OR gold Fed when:1d"), gnews("harga emas when:1d", "id", "ID")]},
    "oil": {"name": "Minyak", "label": "WTI", "symbols": ["CL=F", "BZ=F"], "feeds": [
        gnews("oil price OR crude OR OPEC when:1d"), gnews("harga minyak OR OPEC when:1d", "id", "ID"),
        "https://oilprice.com/rss/main"]},
}
KEYS = ["btc", "eth", "xrp", "sol", "gold", "oil"]

# (regex, efek kripto, efek emas, efek minyak, alasan)
RULES = [
 (r"rate hike|hawkish|suku bunga naik|menaikkan suku bunga|hot cpi|inflasi.*(lebih tinggi|melonjak)|inflation.*(hotter|higher|accelerat)", -2, -2, -.5, "Kebijakan moneter ketat"),
 (r"rate cut|dovish|suku bunga turun|memangkas suku bunga|pelonggaran|stimulus|quantitative easing", 2, 2, .5, "Pelonggaran moneter"),
 (r"dollar (strengthen|rall|surge|jump|rise)|dolar.*(menguat|naik)|yields? (rise|jump|surge)|yield.*naik", -1, -2, -1, "Dolar AS/yield menguat"),
 (r"dollar (weaken|slump|fall|drop)|dolar.*(melemah|turun)|yields? (fall|drop)|yield.*turun", 1, 2, 1, "Dolar AS/yield melemah"),
 (r"\bwar\b|perang|konflik|geopolit|serangan|attack|missile|rudal|tensions?|ketegangan|iran|israel|sanction|sanksi|houthi|red sea|laut merah", -1, 2, 2, "Premi risiko geopolitik naik"),
 (r"ceasefire|gencatan senjata|peace deal|perdamaian|de-escalat|meredakan ketegangan", 1, -1, -2, "Ketegangan geopolitik mereda"),
 (r"opec.*(cut|pangkas|kurangi|reduce)|production cut|pemangkasan produksi|supply cut|output cut", 0, 0, 3, "Pasokan minyak diperketat"),
 (r"opec.*(increase|raise|tambah|naikkan|boost)|production increase|tambah produksi|oversupply|kelebihan pasokan", 0, 0, -3, "Pasokan minyak bertambah"),
 (r"(stok|persediaan|inventor|stockpile).*(naik|bertambah|rise|build|jump|surge|larger)", 0, 0, -2, "Stok minyak naik"),
 (r"(stok|persediaan|inventor|stockpile).*(turun|menyusut|fall|draw|drop|decline|smaller)", 0, 0, 2, "Stok minyak turun"),
 (r"weak demand|permintaan (melemah|lemah|turun)|china.*(slowdown|melambat|weak)|recession|resesi|demand fears", -1, 1, -2, "Kekhawatiran permintaan/resesi"),
 (r"strong demand|permintaan (kuat|naik|meningkat)|demand (surge|rebound|growth)", 0, 0, 2, "Permintaan energi menguat"),
 (r"etf.*(inflow|masuk|approv|disetujui)|(inflow|arus masuk).*etf|institution|institusi|adopsi|adoption|halving|bitcoin reserve|cadangan.*bitcoin", 3, 0, 0, "Arus institusi/adopsi kripto"),
 (r"etf.*(outflow|keluar)|(outflow|arus keluar).*etf|liquidation|likuidasi|whale.*(sell|jual)", -2, 0, 0, "Arus keluar/likuidasi kripto"),
 (r"hack|exploit|peretas|bangkrut|bankrupt|collapse|runtuh|crackdown|banned|larang|sec (sue|gugat)|lawsuit|gugatan|scam|rug ?pull", -3, 0, 0, "Risiko peretasan/hukum kripto"),
 (r"regulatory clarity|regulasi.*jelas|legal tender|pro-crypto|crypto bill|ruu kripto|clarity act", 2, 0, 0, "Regulasi kripto positif"),
 (r"central bank.*(buy|purchas|accumulat)|bank sentral.*(beli|borong|tambah)|pembelian emas", 0, 3, 0, "Bank sentral beli emas"),
 (r"safe.?haven|aset aman|lindung nilai|hedge against", 0, 2, 0, "Permintaan aset aman"),
 (r"risk.?on|stocks? (rally|surge|record)|saham (naik|menguat|reli)|record high|rekor tertinggi", 1, -.5, .5, "Selera risiko membaik"),
 (r"risk.?off|sell.?off|stocks? (plunge|tumble|crash)|saham (anjlok|jatuh|merosot)|crash|panic|panik", -2, 1, -1, "Selera risiko memburuk"),
 (r"(strong|solid|beat|kuat).{0,20}(jobs|payroll|nfp|tenaga kerja)|(jobs|payroll|nfp).{0,20}(strong|beat|kuat)", -1, -1, .5, "Data tenaga kerja kuat"),
 (r"(weak|miss|lemah).{0,20}(jobs|payroll|nfp|tenaga kerja)|(jobs|payroll|nfp).{0,20}(weak|miss|lemah)|jobless claims (rise|naik)", .5, 1, -.5, "Data tenaga kerja lemah"),
]
RULES = [(re.compile(p, re.I), c, g, o, t) for p, c, g, o, t in RULES]
MENTION = {
    "btc": re.compile(r"bitcoin|\\bbtc\\b", re.I),
    "eth": re.compile(r"ethereum|\\beth\\b", re.I),
    "xrp": re.compile(r"\\bxrp\\b|ripple", re.I),
    "sol": re.compile(r"solana|\\bsol\\b", re.I),
    "gold": re.compile(r"\\bgold\\b|\\bemas\\b|xau|bullion", re.I),
    "oil": re.compile(r"\\boil\\b|minyak|crude|\\bwti\\b|brent|opec", re.I)
}
UP = re.compile(r"naik|menguat|melonjak|rally|surge|jump|rise|gain|breakout|rekor|tertinggi|climb|soar", re.I)
DOWN = re.compile(r"turun|melemah|anjlok|jatuh|drop|fall|slump|plunge|tumble|merosot|decline|slide", re.I)

# ---------- pengambilan data ----------
def fetch(url, timeout=20):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout) as r:
        return r.read()

def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()

def parse_feed(xml, host=""):
    root, out = ET.fromstring(xml), []
    for it in root.iter("item"):
        src = it.find("source")
        try:
            dt = parsedate_to_datetime(it.findtext("pubDate"))
            dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            dt = None
        t, s = strip_tags(it.findtext("title")), (src.text if src is not None and src.text else host)
        t = t[:-len(s) - 3].strip() if s and t.endswith(" - " + s) else t
        out.append({"title": t, "source": s, "time": dt, "link": (it.findtext("link") or "").strip()})
    return out

def scrape_news(hours):
    cutoff, seen, items = datetime.now(timezone.utc) - timedelta(hours=hours), set(), []
    for k in KEYS:
        for url in ASSETS[k]["feeds"]:
            host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
            try:
                feed = parse_feed(fetch(url), host)
            except Exception as e:
                print(f"  [gagal] {host}: {e}", file=sys.stderr); continue
            n = 0
            for it in feed:
                key = re.sub(r"[^a-z0-9]+", " ", it["title"].lower()).strip()
                if not key or key in seen or (it["time"] and it["time"] < cutoff):
                    continue
                seen.add(key); items.append(it); n += 1
            print(f"  [berita] {k:6} {host}: {n}")
    return items

def fetch_prices(symbols):
    for sym in symbols:
        try:
            d = json.loads(fetch(f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(sym)}?range=6mo&interval=1d"))
            closes = [c for c in d["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c is not None]
            if len(closes) >= 35:
                print(f"  [harga] {sym}: {len(closes)} candle"); return sym, closes
        except Exception as e:
            print(f"  [gagal] harga {sym}: {e}", file=sys.stderr)
    return None, []

# ---------- analisa berita ----------
def score_headline(title):
    e, why = dict.fromkeys(KEYS, 0.0), []
    # Aturan crypto yang sama diterapkan hanya pada koin yang disebut dalam judul.
    for rx, c, g, o, reason in RULES:
        if rx.search(title):
            if c:
                for k in ("btc", "eth", "xrp", "sol"):
                    if MENTION[k].search(title):
                        e[k] += c
                        why.append((reason, {k: c}))
            if g and MENTION["gold"].search(title):
                e["gold"] += g
                why.append((reason, {"gold": g}))
            if o and MENTION["oil"].search(title):
                e["oil"] += o
                why.append((reason, {"oil": o}))
    up, down = bool(UP.search(title)), bool(DOWN.search(title))
    if up != down:
        for k in KEYS:
            if MENTION[k].search(title) and e[k] == 0:
                e[k] = 1.0 if up else -1.0
                why.append(("Harga disebut " + ("naik" if up else "turun"), {k: e[k]}))
    return e, why


def news_scores(items):
    res = {k: {"sum": 0.0, "n": 0, "drivers": {}, "top": []} for k in KEYS}
    for it in items:
        effects, why = score_headline(it["title"])
        for k in KEYS:
            if effects[k]:
                r = res[k]
                r["sum"] += effects[k]
                r["n"] += 1
                r["top"].append((effects[k], it))
                for reason, effect_map in why:
                    if effect_map.get(k):
                        r["drivers"][reason] = r["drivers"].get(reason, 0) + effect_map[k]
    for k in KEYS:
        r = res[k]
        r["score"] = round(math.tanh(r["sum"] / 5) * 100)
        r["top"] = sorted(r["top"], key=lambda x: -abs(x[0]))[:5]
        r["drivers"] = sorted(r["drivers"].items(), key=lambda x: -abs(x[1]))[:3]
    return res

# ---------- analisa teknikal ----------
def ema(v, n):
    k, out = 2 / (n + 1), [v[0]]
    for x in v[1:]: out.append(x * k + out[-1] * (1 - k))
    return out

def rsi(v, n=14):
    g = [max(v[i] - v[i - 1], 0) for i in range(1, len(v))]; l = [max(v[i - 1] - v[i], 0) for i in range(1, len(v))]
    ag, al = sum(g[:n]) / n, sum(l[:n]) / n
    for i in range(n, len(g)):
        ag, al = (ag * (n - 1) + g[i]) / n, (al * (n - 1) + l[i]) / n
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)

def tech_score(closes):
    if len(closes) < 35: return None
    p, e20, e50 = closes[-1], ema(closes, 20)[-1], ema(closes, 50)[-1] if len(closes) >= 50 else ema(closes, 34)[-1]
    macd = [a - b for a, b in zip(ema(closes, 12), ema(closes, 26))]
    hist = macd[-1] - ema(macd, 9)[-1]
    r, mom = rsi(closes), (p / closes[-6] - 1) * 100
    parts = [("Harga vs EMA20", 1 if p > e20 else -1), ("EMA20 vs EMA50", 1 if e20 > e50 else -1),
             ("MACD histogram", 1 if hist > 0 else -1), ("Momentum 5 hari", 1 if mom > 0 else -1),
             ("RSI", -1 if r > 70 else 1 if r < 30 else round((r - 50) / 20, 2))]
    return {"score": round(sum(s for _, s in parts) / 5 * 100), "parts": parts, "price": p,
            "rsi": r, "ema20": e20, "ema50": e50, "macd_hist": hist, "mom5": mom}

# ---------- gabungan & laporan ----------
def verdict(s): return ("Bullish", "up") if s >= 20 else ("Bearish", "down") if s <= -20 else ("Netral", "flat")

def combine(news, tech, wn, wt):
    out = {}
    for k in KEYS:
        n, t = news[k]["score"], tech[k]["score"] if tech[k] else None
        tot = wn * n + wt * t if t is not None else n
        notes = []
        if t is None: notes.append("Data teknikal tidak tersedia, skor memakai berita saja.")
        if news[k]["n"] == 0: notes.append("Tidak ada berita relevan, skor berita 0 dan keyakinan rendah.")
        if t is not None and n * t < 0 and abs(n) >= 20 and abs(t) >= 20: notes.append("Berita dan teknikal berlawanan arah, hati-hati.")
        out[k] = {"total": round(tot), "verdict": verdict(tot)[0], "news": n, "tech": t, "notes": notes}
    return out

def render_html(news, tech, comb, items, wn, wt, sym):
    e = html.escape
    cards = []
    for k in KEYS:
        c, nw, tc = comb[k], news[k], tech[k]; v, cls = verdict(c["total"])
        w = abs(c["total"]) / 2; bar = f"left:50%;width:{w}%;background:var(--up)" if c["total"] >= 0 else f"right:50%;width:{w}%;background:var(--down)"
        tparts = "".join(f"<li>{e(a)}: {'+' if b > 0 else ''}{b}</li>" for a, b in tc["parts"]) if tc else "<li>Data harga tidak tersedia</li>"
        tinfo = f"Harga {tc['price']:,.2f} ({e(sym[k] or '-')}), RSI {tc['rsi']:.0f}, EMA20 {tc['ema20']:,.2f}, EMA50 {tc['ema50']:,.2f}" if tc else ""
        drv = "".join(f"<li>{e(t)} ({s:+.1f})</li>" for t, s in nw["drivers"]) or "<li>Tidak ada pendorong terdeteksi</li>"
        heads = "".join(f"<li>{e(i['title'])} <span class='m'>({s:+.1f}, {e(i['source'])})</span></li>" for s, i in nw["top"]) or "<li>Tidak ada</li>"
        notes = "".join(f"<p class='warn'>{e(x)}</p>" for x in c["notes"])
        tv = "n/a" if c["tech"] is None else f"{c['tech']:+d}"
        cards.append(f"""<article class="card"><h2>{ASSETS[k]['name']} <small>{ASSETS[k]['label']}</small></h2>
<div class="verdict {cls}">{v} {c['total']:+d}</div><div class="gauge"><i style="{bar}"></i><b></b></div>
<p class="m">Berita {c['news']:+d} x {wn:.0%} &nbsp; Teknikal {tv} x {wt:.0%}</p>{notes}
<h3>Pendorong berita ({nw['n']} berita relevan)</h3><ul>{drv}</ul><ul>{heads}</ul>
<h3>Teknikal</h3><p class="m">{tinfo}</p><ul>{tparts}</ul></article>""")
    now = datetime.now().strftime("%d %b %Y %H:%M")
    return f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Laporan Pasar</title><style>
:root{{--bg:#eef1ef;--s:#fbfcfb;--ink:#16201b;--m:#5d6b64;--line:#d5dcd8;--up:#157a47;--down:#bf3029;--flat:#7a857f}}
@media(prefers-color-scheme:dark){{:root{{--bg:#101613;--s:#18201c;--ink:#e7eeea;--m:#98a69e;--line:#2c3732;--up:#4cc58a;--down:#ff7b72;--flat:#8a968f}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,sans-serif}}main{{max-width:1000px;margin:0 auto;padding:24px 16px}}
h1{{font-size:2rem;margin:0}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:14px;margin-top:18px}}
.card{{background:var(--s);border:1px solid var(--line);border-radius:12px;padding:16px}}h2{{margin:0}}h2 small,.m{{color:var(--m);font-size:.85rem;font-weight:400}}
h3{{font-size:.95rem;margin:14px 0 4px}}ul{{margin:4px 0;padding-left:18px;font-size:.9rem}}.verdict{{font-size:1.8rem;font-weight:800;margin:6px 0}}
.up{{color:var(--up)}}.down{{color:var(--down)}}.flat{{color:var(--flat)}}.warn{{color:var(--down);font-size:.88rem;margin:6px 0}}
.gauge{{position:relative;height:12px;border:1px solid var(--line);border-radius:6px;overflow:hidden;background:var(--bg)}}.gauge i{{position:absolute;top:0;bottom:0}}.gauge b{{position:absolute;left:50%;top:0;bottom:0;width:2px;background:var(--m)}}
</style></head><body><main><h1>Laporan Pasar</h1><p class="m">{now}. {len(items)} berita dianalisa. Bobot: berita {wn:.0%}, teknikal {wt:.0%}. Bukan saran investasi.</p>
<div class="grid">{''.join(cards)}</div></main></body></html>"""

def run(a):
    tot = a.w_news + a.w_tech; wn, wt = a.w_news / tot, a.w_tech / tot
    print(f"Mengambil data {datetime.now():%Y-%m-%d %H:%M} ...")
    items = scrape_news(a.hours); news = news_scores(items)
    tech, sym = {}, {}
    for k in KEYS:
        sym[k], closes = fetch_prices(ASSETS[k]["symbols"]); tech[k] = tech_score(closes)
    comb = combine(news, tech, wn, wt)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / "headlines.txt").write_text("\n".join(i["title"] for i in items), encoding="utf-8")
    (out / "report.html").write_text(render_html(news, tech, comb, items, wn, wt, sym), encoding="utf-8")
    (out / "report.json").write_text(json.dumps({"weights": {"news": wn, "tech": wt}, "result": comb,
        "tech": {k: tech[k] for k in KEYS}}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nGabungan ({wn:.0%} berita, {wt:.0%} teknikal):")
    for k in KEYS:
        c = comb[k]; print(f"  {ASSETS[k]['label']:8} {c['verdict']:8} {c['total']:+4d}   (berita {c['news']:+d}, teknikal {c['tech']})")
    print(f"Laporan: {out / 'report.html'}")

def main():
    ap = argparse.ArgumentParser(description="Scrap berita + analisa 70% berita / 30% teknikal")
    ap.add_argument("--hours", type=float, default=24); ap.add_argument("--out", default="market_output")
    ap.add_argument("--w-news", type=float, default=0.7); ap.add_argument("--w-tech", type=float, default=0.3)
    ap.add_argument("--loop", type=float, default=0, help="ulangi tiap N menit")
    a = ap.parse_args()
    while True:
        run(a)
        if not a.loop: break
        time.sleep(a.loop * 60)

if __name__ == "__main__":
    main()