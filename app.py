import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime
from github import Github
import time

# --- CONFIG ---
st.set_page_config(page_title="Goliath Gate.io Mobile", page_icon="🎯", layout="wide")

# CSS for a clean mobile dark-mode feel
st.markdown("""
    <style>
    .stMetric { background-color: #1e1e1e; padding: 10px; border-radius: 10px; border: 1px solid #333; }
    .up-signal { color: #00ff00; font-weight: bold; font-size: 1.2rem; }
    .down-signal { color: #ff4b4b; font-weight: bold; font-size: 1.2rem; }
    hr { margin: 10px 0px; border-top: 1px solid #444; }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_exchange():
    """Initialize Gate.io safely using Streamlit Secrets."""
    try:
        return ccxt.gateio({
            'apiKey': st.secrets["GATE_API_KEY"],
            'secret': st.secrets["GATE_SECRET"],
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
    except Exception as e:
        st.error(f"Failed to connect to Gate.io: {e}")
        return None

def fetch_ohlcv(exchange, symbol, timeframe):
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe, limit=205)
        df = pd.DataFrame(data, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
        return df
    except:
        return None

def calculate_indicators(df):
    df['SMA20'] = ta.sma(df['c'], length=20)
    df['SMA200'] = ta.sma(df['c'], length=200)
    return df

def detect_signals(df, symbol, timeframe):
    last, prev = df.iloc[-1], df.iloc[-2]
    signals = []
    
    # Golden / Death Cross
    if prev['SMA20'] < prev['SMA200'] and last['SMA20'] > last['SMA200']:
        signals.append({'type': 'Golden Cross', 'dir': 'UP'})
    elif prev['SMA20'] > prev['SMA200'] and last['SMA20'] < last['SMA200']:
        signals.append({'type': 'Death Cross', 'dir': 'DOWN'})
    
    # Squeeze Detection (Within 0.4%)
    gap = abs(last['SMA20'] - last['SMA200']) / last['SMA200']
    if gap < 0.004:
        signals.append({'type': 'SMA Squeeze', 'dir': 'NEUTRAL'})

    return [{**s, 'symbol': symbol, 'tf': timeframe, 'price': last['c']} for s in signals]

def main():
    st.title("🎯 Goliath Scanner")
    exchange = init_exchange()
    if not exchange: st.stop()

    # Load Pairs for selection
    try:
        markets = exchange.load_markets()
        all_pairs = sorted([s for s in markets.keys() if s.endswith('/USDT') and markets[s]['active']])
    except:
        all_pairs = ['BTC/USDT', 'ETH/USDT']

    # --- DEFENSIVE SELECTION LOGIC ---
    # Ensures BTC is found even if naming varies (e.g. BTC/USDT vs BTC_USDT)
    options_pool = all_pairs[:120]
    btc_match = next((s for s in options_pool if "BTC" in s and "USDT" in s), None)
    safe_defaults = [btc_match] if btc_match else ([options_pool[0]] if options_pool else [])

    with st.expander("⚙️ SCANNER SETTINGS", expanded=False):
        selected_pairs = st.multiselect("Pairs to Scan", options_pool, default=safe_defaults)
        selected_tfs = st.multiselect("Timeframes", ['15m', '1h', '4h'], default=['15m', '1h', '4h'])
        show_up = st.checkbox("Show UP Signals", value=True)
        show_down = st.checkbox("Show DOWN Signals", value=True)

    if st.button("🔍 START SCAN", type="primary", use_container_width=True):
        results = []
        prog = st.progress(0)
        
        for i, pair in enumerate(selected_pairs):
            for tf in selected_tfs:
                df = fetch_ohlcv(exchange, pair, tf)
                if df is not None:
                    df = calculate_indicators(df)
                    results.extend(detect_signals(df, pair, tf))
            prog.progress((i + 1) / len(selected_pairs))
            time.sleep(0.3) # Respect Gate.io rate limits

        if not results:
            st.info("No signals found in this batch.")
        else:
            for sig in results:
                # Filtering logic
                if sig['dir'] == 'UP' and not show_up: continue
                if sig['dir'] == 'DOWN' and not show_down: continue
                
                # Mobile-friendly signal card
                with st.container():
                    c1, c2 = st.columns([3, 2])
                    color_class = "up-signal" if sig['dir'] == 'UP' else "down-signal"
                    
                    c1.markdown(f"**{sig['symbol']}** ({sig['tf']})")
                    c1.markdown(f"<span class='{color_class}'>{sig['type']}</span>", unsafe_allow_html=True)
                    
                    # Deep link to Gate.io Trade Page
                    trade_url = f"https://www.gate.io/trade/{sig['symbol'].replace('/', '_')}"
                    c2.link_button("🚀 Trade", trade_url, use_container_width=True)
                    st.markdown("---")

if __name__ == "__main__":
    main()
