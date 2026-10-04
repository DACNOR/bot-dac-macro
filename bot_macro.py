import streamlit as st
import yfinance as yf
import requests
import pandas as pd
from fredapi import Fred

# ---------------------------------------------------------
# 1. COTIZACIONES CABECERA (Tickers en tiempo real - 60s)
# ---------------------------------------------------------
@st.cache_data(ttl=60, show_spinner=False)
def fetch_ticker_prices():
    tickers = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "CVX-USD"]
    data = {}
    try:
        # Descarga en bloque en una sola petición HTTP
        df = yf.download(tickers, period="2d", interval="1d", progress=False)['Close']
        for t in tickers:
            if t in df.columns and len(df[t].dropna()) >= 2:
                prev = df[t].iloc[-2]
                curr = df[t].iloc[-1]
                pct = ((curr - prev) / prev) * 100
                data[t] = {"price": curr, "change": pct}
            elif t in df.columns and len(df[t].dropna()) == 1:
                data[t] = {"price": df[t].iloc[-1], "change": 0.0}
    except Exception as e:
        st.warning(f"Error actualizando tickers: {e}")
    return data

# ---------------------------------------------------------
# 2. INDICADORES TÉCNICOS DIARIOS (RSI, EMA 200, DXY - 30 min)
# ---------------------------------------------------------
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_technical_series():
    series_data = {}
    try:
        # BTC Diario para Wilder RSI y DAC EMA 200
        btc = yf.Ticker("BTC-USD").history(period="1y", interval="1d")
        # DXY Diario
        dxy = yf.Ticker("DX-Y.NYB").history(period="6mo", interval="1d")
        
        series_data["btc"] = btc
        series_data["dxy"] = dxy
    except Exception as e:
        st.error(f"Error descargando datos técnicos diarios: {e}")
    return series_data

# ---------------------------------------------------------
# 3. SENTIMIENTO: FEAR & GREED (30 min)
# ---------------------------------------------------------
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_fear_and_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        if r.status_code == 200:
            payload = r.json()
            return int(payload['data'][0]['value'])
    except Exception:
        pass
    return None

# ---------------------------------------------------------
# 4. MACROECONOMÍA FRED (WALCL, ECBASSETSW, WRESBAL - 6 horas)
# ---------------------------------------------------------
@st.cache_data(ttl=21600, show_spinner=False)
def fetch_fred_macro_series(api_key: str):
    if not api_key:
        return None
    try:
        fred = Fred(api_key=api_key)
        # Descarga de series macro semanales
        walcl = fred.get_series('WALCL')
        ecb = fred.get_series('ECBASSETSW')
        wresbal = fred.get_series('WRESBAL')
        
        return {
            "walcl": walcl,
            "ecb": ecb,
            "wresbal": wresbal
        }
    except Exception as e:
        st.error(f"Error conectando con API FRED: {e}")
        return None
