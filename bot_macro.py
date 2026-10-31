import streamlit as st
import requests
import pandas as pd
import yfinance as yf
from fredapi import Fred
from streamlit_autorefresh import st_autorefresh
import math

st.set_page_config(page_title="BOT DAC MACRO", layout="wide", initial_sidebar_state="collapsed")

# Auto-refresco cada 60 segundos
st_autorefresh(interval=60 * 1000, key="data_refresh")

# --- ESTILOS CSS INSTITUCIONALES (DARK MODE ESTILO TERMINAL DCAPITAL) ---
st.markdown("""
    <style>
    header[data-testid="stHeader"] { display: none !important; }
    .stApp { background-color: #07090e; color: #e1e7ec; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        max-width: 96% !important;
    }

    /* Tarjetas y Contenedores */
    .card-box {
        background-color: #0e121a;
        border-radius: 14px;
        padding: 22px 24px;
        border: 1px solid #1a2232;
        margin-bottom: 16px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
    }

    .card-title { 
        color: #9aa4b2; 
        font-size: 14.5px; 
        font-weight: 800; 
        letter-spacing: 0.8px; 
        text-transform: uppercase;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    
    .card-score { 
        font-size: 32px; 
        font-weight: 900; 
        margin-top: 6px;
    }
    
    .card-sub { 
        color: #8b949e; 
        font-size: 13px; 
        font-weight: 500; 
        margin-top: 8px; 
        text-align: center;
    }

    /* Cinta de precios superior */
    .ticker-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        justify-content: flex-end;
        align-items: center;
    }
    .ticker-item {
        background-color: #0e121a;
        border: 1px solid #1a2232;
        padding: 7px 14px;
        border-radius: 8px;
        font-size: 13.5px;
        font-weight: 700;
    }

    /* Mini barras de progreso */
    .comp-bar-bg {
        width: 100%;
        height: 7px;
        background-color: #1a2232;
        border-radius: 4px;
        margin-top: 10px;
        overflow: hidden;
    }
    .comp-bar-fill {
        height: 100%;
        border-radius: 4px;
    }
    </style>
""", unsafe_allow_html=True)

API_KEY = "90d75f0fd9f03982f65ae802c71aad75"

# --- FUNCIONES DE DESCARGA CON CACHÉ ---
@st.cache_data(ttl=60, show_spinner=False)
def get_live_prices():
    tickers = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "CVX-USD"]
    precios = {"BTC-USD": 77500.0, "ETH-USD": 2225.0, "SOL-USD": 94.5, "XRP-USD": 1.24, "CVX-USD": 1.96}
    try:
        df = yf.download(tickers, period="1d", interval="1m", progress=False)
        if not df.empty:
            close_data = df['Close'] if 'Close' in df else df
            for t in tickers:
                if t in close_data.columns:
                    s = close_data[t].dropna()
                    if len(s) > 0 and float(s.iloc[-1]) > 0:
                        precios[t] = float(s.iloc[-1])
    except Exception:
        pass
    return precios

@st.cache_data(ttl=900, show_spinner=False)
def get_btc_history():
    try:
        btc_ticker = yf.Ticker("BTC-USD")
        df = btc_ticker.history(period="1y", interval="1d")
        if not df.empty and len(df) > 50:
            return df
    except Exception:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=1800, show_spinner=False)
def get_fear_and_greed():
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=7", timeout=4)
        if res.status_code == 200:
            fg_data = res.json().get('data', [])
            if fg_data:
                curr_val = int(fg_data[0]['value'])
                curr_txt = str(fg_data[0]['value_classification'])
                avg_7d = sum([int(x['value']) for x in fg_data[:7]]) / min(
