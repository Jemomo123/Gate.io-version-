import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime
from github import Github
import time

# --- INITIAL CONFIG ---
st.set_page_config(page_title="Goliath Gate.io Scanner", page_icon="🎯", layout="wide")

# CSS for Mobile Readability
st.markdown("""
    <style>
    .stMetric { background-color: #1e1e1e; padding: 10px; border-radius: 10px; border: 1px solid #333; }
    .up-signal { color: #00ff00; font-weight: bold; }
    .down-signal { color: #ff4b4b; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- EXCHANGE & DATA FUNCTIONS ---
@st.cache_resource
def init_exchange():
    """Initialize Gate.io via CCXT using secrets."""
    return ccxt.gateio({
        'apiKey': st.secrets["GATE_API_KEY"],
        'secret': st.secrets["GATE_SECRET"],
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })

def fetch_ohlcv(exchange, symbol, timeframe):
    """Fetch candles with safety handling."""
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe, limit=201)
        df = pd.DataFrame(data, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
        return df
    except Exception:
        return None

def calculate_indicators(df):
    """Calculate the 20/200 SMA and VWAP for the Goliath strategy."""
    df['SMA20'] = ta.sma(df['c'], length=20)
    df['SMA200'] = ta.sma(df['c'], length=200)
    df['VWAP'] = ta.vwap(df['h'], df['l'], df['c'], df['v'])
    return df

# --- SIGNAL DETECTION ---
def detect_signals(df, symbol, timeframe):
    """Detects Crossovers, Squeezes, and Rejections."""
    last = df.iloc[-1]
    prev = df.iloc[-2]
    signals = []
    
    # 1. Golden/Death Cross
    if prev['SMA20'] < prev['SMA200'] and last['SMA20'] > last['SMA200']:
        signals.append({'type': 'Golden Cross', 'dir': 'UP'})
    elif prev['SMA20'] > prev['SMA200'] and last['SMA20'] < last['SMA200']:
        signals.append({'type': 'Death Cross', 'dir': 'DOWN'})
    
    # 2. SMA Squeeze (Gap less than 0.5%)
    gap = abs(last['SMA20'] - last['SMA200']) / last['SMA200']
    if gap < 0.005:
        signals.append({'type': 'SMA Squeeze', 'dir': 'NEUTRAL'})

    return [{**s, 'symbol': symbol, 'tf': timeframe, 'price': last['c']} for s in signals]

# --- GITHUB LOGGING ---
def log_to_github(signal):
    """Logs signal to your GitHub repository."""
    try:
        g = Github(st.secrets["GITHUB_TOKEN"])
        repo = g.get_repo(st.secrets["GITHUB_REPO"])
        file_path = "goliath_signals.csv"
        line = f"{datetime.now()},{signal['symbol']},{signal['type']},{signal['dir']},{signal['price']}\n"
        
        try:
            content = repo.get_contents(file_path)
            new_content = content.decoded_content.decode() + line
            repo.update_file(file_path, f"Update {signal['symbol']}", new_content, content.sha)
        except:
            repo.create_file(file_path, "Initial log", "Time,Symbol,Type,Dir,Price\n" + line)
        return True
    except:
        return False

# --- MAIN APP ---
def main():
    st.title("🎯 Goliath Scanner (Gate.io)")
    exchange = init_exchange()
    
    # Sidebar Settings
    with st.sidebar:
        st.header("Settings")
        markets = exchange.load_markets()
        pairs = sorted([s for s in markets.keys() if s.endswith('/USDT')])
        
        selected_pairs = st.multiselect("Pairs", pairs[:100], default=['BTC/USDT'])
        selected_tfs = st.multiselect("Timeframes", ['15m', '1h', '4h'], default=['15m', '1h', '4h'])
        
        show_up = st.checkbox("Show UP Signals", value=True)
        show_down = st.checkbox("Show DOWN Signals", value=True)

    if st.button("🚀 START GLOBAL SCAN", use_container_width=True):
        found_signals = []
        progress = st.progress(0)
        
        for i, symbol in enumerate(selected_pairs):
            for tf in selected_tfs:
                df = fetch_ohlcv(exchange, symbol, tf)
                if df is not None:
                    df = calculate_indicators(df)
                    found_signals.extend(detect_signals(df, symbol, tf))
            
            progress.progress((i + 1) / len(selected_pairs))
            time.sleep(0.5) # Gate.io batch rest
            
        # Display Results
        for sig in found_signals:
            if sig['dir'] == 'UP' and not show_up: continue
            if sig['dir'] == 'DOWN' and not show_down: continue
            
            with st.container():
                col1, col2, col3 = st.columns([2, 2, 1])
                color = "up-signal" if sig['dir'] == 'UP' else "down-signal"
                col1.markdown(f"### {sig['symbol']} ({sig['tf']})")
                col2.markdown(f"**Type:** {sig['type']} | **Dir:** <span class='{color}'>{sig['dir']}</span>", unsafe_allow_html=True)
                
                if col3.button("💾 Log", key=f"{sig['symbol']}_{sig['tf']}"):
                    if log_to_github(sig):
                        st.toast(f"Logged {sig['symbol']}!")

if __name__ == "__main__":
    main()
