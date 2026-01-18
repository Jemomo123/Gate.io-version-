import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import time

# --- CONFIGURATION ---
BATCH_SIZE = 10 # Gate.io handles slightly larger batches than MEXC
REST_TIME = 1.0 

st.set_page_config(page_title="Gate.io Pro Scanner", page_icon="🎯", layout="wide")

# (Keep your existing CSS here)

@st.cache_resource
def init_exchange():
    # Switching to Gate.io
    return ccxt.gateio({
        'enableRateLimit': True, 
        'options': {'defaultType': 'spot'},
        'timeout': 30000
    })

@st.cache_data(ttl=600)
def get_gate_pairs(_exchange):
    try:
        markets = _exchange.load_markets()
        # Gate uses symbols like 'BTC/USDT'
        pairs = [s for s in markets.keys() if s.endswith('/USDT') and markets[s]['active']]
        
        # Sort and prioritize BTC
        pairs.sort()
        if 'BTC/USDT' in pairs:
            pairs.insert(0, pairs.pop(pairs.index('BTC/USDT')))
        return pairs
    except Exception as e:
        st.error(f"Error loading Gate.io markets: {e}")
        return ['BTC/USDT']

def main():
    st.markdown("# 🎯 Gate.io Pro Scanner")
    st.caption("📱 16-Opportunity System - Goliath Strategy")
    
    exchange = init_exchange()
    if not exchange:
        st.stop()

    usdt_pairs = get_gate_pairs(exchange)
    
    with st.expander("⚙️ SETTINGS", expanded=False):
        # Defensively load pairs to prevent the StreamlitAPIException
        options_pool = usdt_pairs[:100]
        desired_defaults = ['BTC/USDT'] + [p for p in usdt_pairs if p != 'BTC/USDT'][:9]
        safe_defaults = [p for p in desired_defaults if p in options_pool]

        st.markdown("### 📊 Trading Pairs")
        selected_pairs = st.multiselect("Select pairs", options=options_pool, default=safe_defaults)
        
        st.markdown("### ⏱️ Timeframes")
        # Aligned with your preferred timeframes
        selected_timeframes = st.multiselect("Select timeframes", ['3m', '5m', '15m', '1h', '4h'], default=['15m', '1h', '4h'])
        
        auto_refresh = st.toggle("Enable (60s)", value=True)
        st.session_state.auto_refresh_enabled = auto_refresh

    # --- SCANNING LOGIC ---
    scan_button = st.button("🔍 SCAN GATE.IO NOW", type="primary", use_container_width=True)

    if scan_button:
        if not selected_pairs:
            st.warning("⚠️ Please select at least one pair.")
        else:
            with st.spinner("📡 Probing Gate.io Markets..."):
                # Use your existing scan_markets function here
                # It will now use the Gate.io exchange object
                signals = scan_markets(exchange, selected_pairs, selected_timeframes)
                st.session_state.signals = signals
                st.session_state.last_update = datetime.now()
                st.rerun()

    # (Keep your existing Signal Display Logic here)

if __name__ == "__main__":
    main()
