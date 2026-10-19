import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="台股即時資金流向", page_icon="📊", layout="wide")

st.markdown("""
<style>
.stApp {background:#090b0e;color:#e9edf2}
.block-container {padding-top:1.1rem;max-width:1400px}
.metric-card {background:#11151b;border:1px solid #252b34;border-radius:14px;padding:14px 16px}
.small-muted {color:#929ba8;font-size:13px}
.flow-in {color:#ff667a;font-weight:700}
.flow-out {color:#42d6a0;font-weight:700}
div[data-testid="stMetric"] {background:#11151b;border:1px solid #252b34;padding:12px 15px;border-radius:12px}
</style>
""", unsafe_allow_html=True)

st.title("📊 台股資金流動盤")
st.caption("免費行情估算版｜使用 Yahoo Finance 行情推估資金方向，不等同交易所／券商的真實主動買賣超。")

# Starter universe. Users can edit/add tickers in the sidebar.
STOCKS = [
("2330","台積電","半導體"),("2454","聯發科","半導體"),("2303","聯電","半導體"),("3711","日月光投控","半導體"),("3034","聯詠","半導體"),("2379","瑞昱","半導體"),("3443","創意","半導體"),("3661","世芯-KY","半導體"),("5274","信驊","半導體"),("3529","力旺","半導體"),
("2317","鴻海","電腦及週邊"),("2382","廣達","電腦及週邊"),("2357","華碩","電腦及週邊"),("3231","緯創","電腦及週邊"),("6669","緯穎","電腦及週邊"),("2376","技嘉","電腦及週邊"),("2301","光寶科","電腦及週邊"),("2324","仁寶","電腦及週邊"),
("2345","智邦","通信網路"),("2412","中華電","通信網路"),("6285","啟碁","通信網路"),("3596","智易","通信網路"),
("2308","台達電","電子零組件"),("2383","台光電","電子零組件"),("3037","欣興","電子零組件"),("8046","南電","電子零組件"),("2368","金像電","電子零組件"),("3017","奇鋐","電子零組件"),("3324","雙鴻","電子零組件"),
("2455","全新","光電"),("3008","大立光","光電"),("3481","群創","光電"),("2409","友達","光電"),
("2603","長榮","航運"),("2609","陽明","航運"),("2615","萬海","航運"),("2618","長榮航","航運"),("2610","華航","航運"),
("2881","富邦金","金融保險"),("2882","國泰金","金融保險"),("2891","中信金","金融保險"),("2886","兆豐金","金融保險"),("2884","玉山金","金融保險"),("2885","元大金","金融保險"),
("1301","台塑","塑膠"),("1303","南亞","塑膠"),("1326","台化","塑膠"),("6505","台塑化","油電燃氣"),
("2002","中鋼","鋼鐵"),("2014","中鴻","鋼鐵"),("1101","台泥","水泥"),("1216","統一","食品"),("2912","統一超","貿易百貨"),
("2395","研華","電機機械"),("1504","東元","電機機械"),("1519","華城","電機機械"),("1503","士電","電機機械"),
("4904","遠傳","通信網路"),("3045","台灣大","通信網路"),("5269","祥碩","半導體"),("8299","群聯","半導體"),
]
DEFAULT_CODES = ",".join(x[0] for x in STOCKS)

@st.cache_data(ttl=180, show_spinner=False)
def fetch_data(codes_text):
    codes = [c.strip().replace(".TW","").replace(".TWO","") for c in codes_text.split(",") if c.strip()]
    # Keep unique codes, cap list to avoid excessive requests.
    codes = list(dict.fromkeys(codes))[:180]
    mapping = {code: (name, sector) for code, name, sector in STOCKS}
    tickers = [c + ".TW" for c in codes]
    rows = []
    def one(ticker):
        try:
            hist = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=False)
            if hist is None or len(hist) < 2:
                # Try OTC suffix for tickers not found on TWSE.
                hist = yf.Ticker(ticker[:-3] + ".TWO").history(period="5d", interval="1d", auto_adjust=False)
                ticker2 = ticker[:-3] + ".TWO"
            else:
                ticker2 = ticker
            if hist is None or len(hist) < 2:
                return None
            prev, cur = hist.iloc[-2], hist.iloc[-1]
            close = float(cur["Close"])
            prev_close = float(prev["Close"])
            volume = float(cur["Volume"]) if pd.notna(cur["Volume"]) else 0
            if close <= 0 or prev_close <= 0:
                return None
            change_pct = (close / prev_close - 1) * 100
            turnover = close * volume * 1000  # TWD estimate; Yahoo volume is shares
            # Signed turnover proxy: positive return = estimated inflow, negative = estimated outflow.
            signed = turnover * np.sign(change_pct) * min(abs(change_pct) / 2.0, 1.0)
            code = ticker.split(".")[0]
            name, sector = mapping.get(code, (code, "未分類"))
            return {"代號": code, "名稱": name, "產業": sector, "收盤價": close, "漲跌幅%": change_pct,
                    "成交量(股)": volume, "估算成交金額(億)": turnover/1e8, "估算資金方向(億)": signed/1e8}
        except Exception:
            return None
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(one, t) for t in tickers]
        for f in as_completed(futures):
            r = f.result()
            if r:
                rows.append(r)
    return pd.DataFrame(rows)

with st.sidebar:
    st.header("設定")
    st.write("更新間隔：手動按下方按鈕重新抓取。")
    codes_text = st.text_area("股票代號（逗號分隔）", value=DEFAULT_CODES, height=180,
        help="預設為常見台股樣本。可自行加入代號；產業分類可在程式中的 STOCKS 清單修改。")
    if st.button("🔄 重新抓取行情", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption("資料可能延遲、缺漏或受來源限制。非下單系統。")

with st.spinner("正在抓取行情並估算資金方向…"):
    df = fetch_data(codes_text)

if df.empty:
    st.error("目前無法取得行情。請稍後重試，或確認網路與 Yahoo Finance 是否可用。")
    st.stop()

# Label explicitly reflects estimate, not actual buy/sell data.
net = df["估算資金方向(億)"].sum()
up = int((df["漲跌幅%"] > 0).sum())
down = int((df["漲跌幅%"] < 0).sum())
total_turnover = df["估算成交金額(億)"].sum()

c1,c2,c3,c4 = st.columns(4)
c1.metric("樣本股票數", f"{len(df):,}")
c2.metric("估算資金方向淨額", f"{net:+.2f} 億")
c3.metric("上漲 / 下跌", f"{up} / {down}")
c4.metric("樣本估算成交金額", f"{total_turnover:.1f} 億")

st.caption(f"最後更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}｜數字是依價格漲跌與成交量估算，並非真正的主動買賣淨額。")

sector = df.groupby("產業", as_index=False).agg(
    **{"估算資金方向(億)":("估算資金方向(億)","sum"),
       "估算成交金額(億)":("估算成交金額(億)","sum"),
       "股票數":("代號","count"),
       "平均漲跌幅%":("漲跌幅%","mean")}
).sort_values("估算資金方向(億)", ascending=False)

left,right = st.columns([1.15, 1])
with left:
    st.subheader("產業資金流向排行（估算）")
    view = sector.sort_values("估算資金方向(億)", ascending=True)
    st.bar_chart(view.set_index("產業")[["估算資金方向(億)"]], horizontal=True)
    st.dataframe(sector.style.format({
        "估算資金方向(億)": "{:+.2f}", "估算成交金額(億)": "{:.2f}", "平均漲跌幅%": "{:+.2f}%"
    }), use_container_width=True, hide_index=True)
with right:
    st.subheader("個股資金方向排行（估算）")
    st.markdown("**估算流入較多**")
    st.dataframe(df.sort_values("估算資金方向(億)", ascending=False).head(12)[["代號","名稱","產業","漲跌幅%","估算資金方向(億)"]].style.format({"漲跌幅%":"{:+.2f}%","估算資金方向(億)":"{:+.2f}"}), use_container_width=True, hide_index=True)
    st.markdown("**估算流出較多**")
    st.dataframe(df.sort_values("估算資金方向(億)").head(12)[["代號","名稱","產業","漲跌幅%","估算資金方向(億)"]].style.format({"漲跌幅%":"{:+.2f}%","估算資金方向(億)":"{:+.2f}"}), use_container_width=True, hide_index=True)

st.subheader("全部個股")
st.dataframe(df.sort_values("估算資金方向(億)", ascending=False).style.format({
    "收盤價":"{:.2f}", "漲跌幅%":"{:+.2f}%", "成交量(股)":"{:,.0f}",
    "估算成交金額(億)":"{:.2f}", "估算資金方向(億)":"{:+.2f}"
}), use_container_width=True, hide_index=True)
csv = df.to_csv(index=False).encode("utf-8-sig")
st.download_button("⬇️ 下載個股資料 CSV", data=csv, file_name="台股資金流向估算.csv", mime="text/csv")
st.warning("重要限制：此版本是免費行情估算原型。股價上漲／下跌搭配成交量只能作為資金方向代理指標，不能代表真實主動買賣、法人買賣超或全市場完整資金流。若要複製圖片中的真實產業主動買賣淨額，需要有授權的即時行情／逐筆成交資料源。")
