import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import time

# --- MOBILE UI SETUP ---
st.set_page_config(page_title="Goliath Scanner", layout="wide")

st.markdown("""
    <style>
    .signal-card { border: 1px solid #333; padding: 10px; border-radius: 8px; margin-bottom: 10px; background: #161a21; }
    .up { color: #00ff00; font-weight: bold; }
    .down { color: #ff4b4b; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_exchange():
    return ccxt.gateio({
        'apiKey': st.secrets["GATE_API_KEY"],
        'secret': st.secrets["GATE_SECRET"],
        'enableRateLimit': True
    })

def detect_signals(df, symbol, tf):
    last, prev = df.iloc[-1], df.iloc[-2]
    c, o, s20, s200 = last['c'], last['o'], last['SMA20'], last['SMA200']
    rsi, vwap = last['RSI'], last['VWAP']
    
    sigs = []
    prio = 1 if tf in ['3m', '5m', '15m'] else 2

    # 1. Elephant Bars & V-Reversals
    avg_body = abs(df['c'] - df['o']).tail(20).mean()
    if abs(c - o) > (avg_body * 2.5):
        sigs.append({'type': 'Elephant Bar', 'dir': 'UP' if c > o else 'DOWN', 'prio': prio})
    
    # 2. The Kisses (SMA 200)
    if prev['l'] <= s200 and c > s200: sigs.append({'type': 'Kiss of Life', 'dir': 'UP', 'prio': prio})
    if prev['h'] >= s200 and c < s200: sigs.append({'type': 'Kiss of Death', 'dir': 'DOWN', 'prio': prio})

    # 3. Squeeze & Divergence
    gap = abs(s20 - s200) / s200
    if gap < 0.005: sigs.append({'type': 'Squeeze', 'dir': 'NEUTRAL', 'prio': prio})
    if (abs(c - s20) / s20) > 0.05: sigs.append({'type': 'Wide State', 'dir': 'WATCH', 'prio': prio})

    # 4. Value Snap (RSI/VWAP)
    if rsi < 30 and c > vwap: sigs.append({'type': 'Value Snap', 'dir': 'UP', 'prio': prio})
    if rsi > 70 and c < vwap: sigs.append({'type': 'Value Snap', 'dir': 'DOWN', 'prio': prio})

    return [{**s, 'symbol': symbol, 'tf': tf, 'price': c} for s in sigs]

def main():
    st.title("🎯 Goliath Scanner")
    ex = init_exchange()
    
    # Defensive Symbol Load
    m = ex.load_markets()
    pairs = sorted([s for s in m.keys() if s.endswith('/USDT') and m[s]['active']])
    btc = next((s for s in pairs if "BTC" in s), pairs[0])

    with st.sidebar:
        sel_pairs = st.multiselect("Pairs", pairs[:100], default=[btc])
        sel_tfs = st.multiselect("Timeframes", ['3m', '5m', '15m', '1h', '4h'], default=['3m', '15m', '1h'])

    if st.button("🚀 SCAN", use_container_width=True):
        found = []
        for p in sel_pairs:
            for t in sel_tfs:
                try:
                    bars = ex.fetch_ohlcv(p, t, limit=205)
                    df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
                    df['SMA20'] = ta.sma(df['c'], 20); df['SMA200'] = ta.sma(df['c'], 200)
                    df['RSI'] = ta.rsi(df['c'], 14); df['VWAP'] = ta.vwap(df['h'], df['l'], df['c'], df['v'])
                    found.extend(detect_signals(df, p, t))
                except: continue
            time.sleep(0.5)

        found.sort(key=lambda x: x['prio']) # Scalps First

        for s in found:
            c1, c2 = st.columns([3, 1])
            cls = "up" if s['dir'] == "UP" else ("down" if s['dir'] == "DOWN" else "")
            c1.markdown(f"<div class='signal-card'><b>{s['symbol']} ({s['tf']})</b><br><span class='{cls}'>{s['type']}</span> @ {s['price']}</div>", unsafe_allow_html=True)
            url = f"https://www.gate.io/trade/{s['symbol'].replace('/', '_')}"
            c2.link_button("Trade", url)

if __name__ == "__main__":
    main()
