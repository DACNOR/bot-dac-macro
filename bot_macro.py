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

# --- FUNCIONES DE DESCARGA CON CACHÉ Y TIMEOUTS SEGUROS ---
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
                avg_7d = sum([int(x['value']) for x in fg_data[:7]]) / min(len(fg_data), 7)
                return curr_val, curr_txt, avg_7d
    except Exception:
        pass
    return 30, "Fear", 48.0

@st.cache_data(ttl=7200, show_spinner=False)
def get_fred_data(api_key):
    try:
        fred = Fred(api_key=api_key)
        wresbal = fred.get_series('WRESBAL')
        walcl = fred.get_series('WALCL')
        ecb = fred.get_series('ECBASSETSW')
        return (wresbal.dropna() if wresbal is not None else pd.Series(dtype=float),
                walcl.dropna() if walcl is not None else pd.Series(dtype=float),
                ecb.dropna() if ecb is not None else pd.Series(dtype=float))
    except Exception:
        return pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float)

@st.cache_data(ttl=1800, show_spinner=False)
def get_dxy_data():
    try:
        dxy_df = yf.Ticker("DX-Y.NYB").history(period="6mo", interval="1d")
        if not dxy_df.empty:
            return dxy_df
    except Exception:
        pass
    return pd.DataFrame()

# ==========================================
# CÁLCULOS CUANTITATIVOS (CONTROL TOTAL DE ERRORES)
# ==========================================

live_prices = get_live_prices()
precio_btc = live_prices["BTC-USD"]
p_eth = live_prices["ETH-USD"]
p_sol = live_prices["SOL-USD"]
p_xrp = live_prices["XRP-USD"]
p_cvx = live_prices["CVX-USD"]

# 1. Técnico BTC (RSI y EMA 200)
rsi, ema_bot, ema_top, dist_ema, score_r, score_e = 35.1, 76417.0, 77500.0, 1.0, 8, 6
try:
    hist = get_btc_history()
    if not hist.empty and len(hist) >= 200:
        closes = hist['Close']
        highs = hist['High']
        if precio_btc <= 0:
            precio_btc = float(closes.iloc[-1])
        
        ema_top = float(highs.ewm(span=200, adjust=False).mean().iloc[-1])
        ema_bot = float(closes.ewm(span=200, adjust=False).mean().iloc[-1])
        dist_ema = ((precio_btc - ema_bot) / ema_bot) * 100
        
        diff = closes.diff()
        gain = diff.clip(lower=0).ewm(com=13, adjust=False).mean()
        loss = (-diff.clip(upper=0)).ewm(com=13, adjust=False).mean()
        rsi = float((100 - (100 / (1 + (gain / loss)))).iloc[-1])
        
        # R - RSI Diario
        if rsi <= 30:
            score_r = 10
        elif rsi <= 38:
            score_r = 8
        elif rsi <= 45:
            score_r = 7
        elif rsi <= 55:
            score_r = 5
        elif rsi <= 65:
            score_r = 3
        else:
            score_r = 1
            
        # E - EMA 200
        if dist_ema <= 0:
            score_e = 9
        elif dist_ema <= 3:
            score_e = 6
        elif dist_ema <= 10:
            score_e = 4
        else:
            score_e = 3
except Exception:
    pass

# 2. Sentimiento Fear & Greed
fg_val, fg_text, fg_7d_avg = get_fear_and_greed()
if fg_val <= 25:
    score_f = 10
elif fg_val <= 35:
    score_f = 7
elif fg
