import json
from datetime import datetime
import streamlit as st
import pandas as pd

import market_analyzer as core

st.set_page_config(page_title="Market Analyzer", page_icon="📊", layout="wide")

st.markdown("""
<style>
.block-container {max-width: 1250px; padding-top: 2rem;}
.metric-card {padding: 18px; border: 1px solid rgba(128,128,128,.25); border-radius: 14px;}
.small-muted {opacity: .7; font-size: .88rem;}
</style>
""", unsafe_allow_html=True)

st.title("📊 Market Analyzer")
st.caption("Dashboard analisis berita dan teknikal • BTC/USD • XAUUSD • WTI")

with st.sidebar:
    st.header("Pengaturan analisis")
    hours = st.slider("Rentang berita (jam)", 1, 168, 24)
    news_weight, tech_weight = 70, 30
    st.info("Bobot analisis dikunci: 70% berita + 30% teknikal.")
    refresh = st.button("🔄 Analisis / Perbarui sekarang", type="primary", use_container_width=True)
    st.divider()
    st.caption("Sumber harga: Yahoo Finance. Berita: Google News RSS, CoinDesk, Cointelegraph, OilPrice.")
    st.caption("Skor adalah ringkasan otomatis berbasis aturan kata kunci, bukan prediksi pasti.")

@st.cache_data(ttl=300, show_spinner=False)
def load_analysis(hours, news_weight, tech_weight, refresh_token):
    items = core.scrape_news(hours)
    news = core.news_scores(items)
    tech, symbols = {}, {}
    for key in core.KEYS:
        symbols[key], closes = core.fetch_prices(core.ASSETS[key]["symbols"])
        tech[key] = core.tech_score(closes)
    total_weight = news_weight + tech_weight
    if total_weight == 0:
        news_weight, tech_weight = 70, 30
        total_weight = 100
    wn, wt = news_weight / total_weight, tech_weight / total_weight
    combined = core.combine(news, tech, wn, wt)
    return items, news, tech, symbols, combined, wn, wt

if "refresh_token" not in st.session_state:
    st.session_state.refresh_token = 0
if refresh:
    st.session_state.refresh_token += 1
    st.cache_data.clear()

try:
    with st.spinner("Mengambil berita dan data harga pasar..."):
        items, news, tech, symbols, combined, wn, wt = load_analysis(
            hours, 70, 30, st.session_state.refresh_token
        )
except Exception as exc:
    st.error(f"Analisis gagal dijalankan: {exc}")
    st.info("Periksa koneksi internet, lalu tekan tombol Analisis / Perbarui sekarang.")
    st.stop()

st.caption(f"Terakhir dimuat: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')} • {len(items)} berita ditemukan • Bobot target berita {wn:.0%} / teknikal {wt:.0%}")
missing_technical = [labels[k] for k in core.KEYS if tech[k] is None]
if missing_technical:
    st.warning("Data teknikal tidak tersedia untuk: " + ", ".join(missing_technical) + ". Untuk aset tersebut, skor sementara hanya memakai berita; hasil belum merupakan gabungan penuh 70/30.")

labels = {"btc": "BTC/USD", "eth": "ETH/USD", "xrp": "XRP/USD", "sol": "SOL/USD", "gold": "XAUUSD", "oil": "WTI"}
st.subheader("Crypto")
crypto_cols = st.columns(4)
for col, key in zip(crypto_cols, ("btc", "eth", "xrp", "sol")):
    result = combined[key]
    verdict = result["verdict"]
    color = "🟢" if verdict == "Bullish" else "🔴" if verdict == "Bearish" else "🟡"
    with col:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.subheader(labels[key])
        st.markdown(f"### {color} {verdict}")
        st.metric("Skor gabungan", f'{result["total"]:+d}', help="Rentang skor indikatif -100 sampai +100")
        st.progress(min(1.0, max(0.0, (result["total"] + 100) / 200)))
        st.caption(f'Berita: {result["news"]:+d}  |  Teknikal: {result["tech"] if result["tech"] is not None else "N/A"}')
        if tech[key]:
            st.metric("Harga terakhir", f'{tech[key]["price"]:,.2f}')
            st.caption(f'RSI {tech[key]["rsi"]:.1f} • EMA20 {tech[key]["ema20"]:,.2f} • EMA50 {tech[key]["ema50"]:,.2f}')
        else:
            st.warning("Data teknikal belum tersedia.")
        for note in result["notes"]:
            st.warning(note)
        st.markdown('</div>', unsafe_allow_html=True)

st.subheader("Komoditas")
commodity_cols = st.columns(2)
for col, key in zip(commodity_cols, ("gold", "oil")):
    result = combined[key]
    verdict = result["verdict"]
    color = "🟢" if verdict == "Bullish" else "🔴" if verdict == "Bearish" else "🟡"
    with col:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.subheader(labels[key])
        st.markdown(f"### {color} {verdict}")
        st.metric("Skor gabungan", f'{result["total"]:+d}')
        st.progress(min(1.0, max(0.0, (result["total"] + 100) / 200)))
        st.caption(f'Berita: {result["news"]:+d}  |  Teknikal: {result["tech"] if result["tech"] is not None else "N/A"}')
        if tech[key]:
            st.metric("Harga terakhir", f'{tech[key]["price"]:,.2f}')
            st.caption(f'RSI {tech[key]["rsi"]:.1f} • EMA20 {tech[key]["ema20"]:,.2f} • EMA50 {tech[key]["ema50"]:,.2f}')
        else:
            st.warning("Data teknikal belum tersedia.")
        for note in result["notes"]:
            st.warning(note)
        st.markdown('</div>', unsafe_allow_html=True)

st.divider()
tab_overview, tab_news, tab_technical, tab_export = st.tabs(
    ["Ringkasan", "Berita", "Teknikal", "Ekspor data"]
)

with tab_overview:
    st.subheader("Perbandingan skor")
    chart_data = pd.DataFrame({
        "Aset": [labels[k] for k in core.KEYS],
        "Berita": [news[k]["score"] for k in core.KEYS],
        "Teknikal": [tech[k]["score"] if tech[k] else 0 for k in core.KEYS],
        "Gabungan": [combined[k]["total"] for k in core.KEYS],
    }).set_index("Aset")
    st.bar_chart(chart_data, height=300)
    st.subheader("Pendorong utama")
    for key in core.KEYS:
        with st.expander(f'{labels[key]} — {news[key]["n"]} berita relevan'):
            drivers = news[key]["drivers"]
            if drivers:
                st.dataframe(pd.DataFrame(drivers, columns=["Faktor", "Dampak"]), hide_index=True, use_container_width=True)
            else:
                st.write("Belum ada pendorong berita yang terdeteksi.")

with tab_news:
    st.subheader("Berita yang dianalisis")
    asset_filter = st.selectbox("Filter aset", ["Semua", "BTC/USD", "ETH/USD", "XRP/USD", "SOL/USD", "XAUUSD", "WTI"])
    rows = []
    for item in items:
        scores, _ = core.score_headline(item["title"])
        relevant = [labels[k] for k in core.KEYS if scores[k] != 0]
        if asset_filter == "Semua" or asset_filter in relevant:
            rows.append({
                "Judul": item["title"], "Sumber": item["source"],
                "Aset terkait": ", ".join(relevant) or "Belum terklasifikasi",
                "Tautan": item["link"]
            })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                     column_config={"Tautan": st.column_config.LinkColumn("Buka berita")})
    else:
        st.info("Tidak ada berita yang cocok dengan filter ini.")

with tab_technical:
    st.subheader("Indikator teknikal")
    for key in core.KEYS:
        t = tech[key]
        with st.expander(labels[key], expanded=True):
            if not t:
                st.warning("Data harga historis belum tersedia.")
                continue
            st.write(f'**Harga:** {t["price"]:,.4f}  |  **RSI:** {t["rsi"]:.2f}  |  **Momentum 5 hari:** {t["mom5"]:+.2f}%')
            st.write(f'**EMA20:** {t["ema20"]:,.4f}  |  **EMA50:** {t["ema50"]:,.4f}  |  **MACD histogram:** {t["macd_hist"]:.5f}')
            st.dataframe(pd.DataFrame(t["parts"], columns=["Komponen", "Skor"]), hide_index=True, use_container_width=True)

with tab_export:
    st.subheader("Unduh hasil analisis")
    report = {
        "generated_at": datetime.now().isoformat(),
        "weights": {"news": wn, "technical": wt},
        "result": combined,
        "technical": tech,
        "news": {k: {"score": news[k]["score"], "count": news[k]["n"], "drivers": news[k]["drivers"]} for k in core.KEYS}
    }
    st.download_button("⬇️ Unduh laporan JSON", json.dumps(report, ensure_ascii=False, indent=2, default=str),
                       file_name="market_report.json", mime="application/json")
    headlines = "\n".join(i["title"] for i in items)
    st.download_button("⬇️ Unduh daftar berita TXT", headlines,
                       file_name="market_headlines.txt", mime="text/plain")

st.divider()
st.caption("⚠️ Bukan saran investasi. Skor otomatis dapat salah mengklasifikasikan konteks berita dan tidak menjamin arah harga. Gunakan manajemen risiko dan verifikasi data sebelum mengambil keputusan.")
