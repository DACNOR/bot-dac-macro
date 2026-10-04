import streamlit as st
import yfinance as yf
import requests
import pandas as pd
import numpy as np
from fredapi import Fred
from streamlit_autorefresh import st_autorefresh

# ---------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA Y AUTO-REFRESCO (60s)
# ---------------------------------------------------------
st.set_page_config(
    page_title="BOT DAC MACRO",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Auto-refresco cada 60 segundos
st_autorefresh(interval=60 * 1000, key="dac_macro_refresh")

# ---------------------------------------------------------
# ESTILOS CSS - DARK MODE INSTITUCIONAL
# ---------------------------------------------------------
st.markdown("""
<style>
    header[data-testid="stHeader"] { display: none !important; }
    footer { display: none !important; }
    .main { background-color: #0b0e14; color: #e1e4ea; }
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 96% !important;
    }
    .metric-card {
        background-color: #131722;
        border: 1px solid #1e222d;
        border-radius: 8px;
        padding: 12px 16px;
        text-align: center;
    }
    .metric-title { font-size: 0.8rem; color: #787b86; text-transform: uppercase; font-weight: 600; }
    .metric-value { font-size: 1.25rem; font-weight: 700; color: #f0f3fa; margin-top: 4px; }
    .score-container {
        background-color: #131722;
        border: 1px solid #1e222d;
        border-radius: 12px;
        padding: 24px;
        text-align: center;
        margin: 20px 0;
    }
    .score-number { font-size: 3.5rem; font-weight: 800; }
    .score-badge {
        font-size: 1.1rem;
        font-weight: 700;
        padding: 6px 16px;
        border-radius: 20px;
        display: inline-block;
        margin-top: 8px;
    }
    .comp-box {
        background-color: #131722;
        border: 1px solid #1e222d;
        border-radius: 8px;
        padding: 14px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# FUNCIONES CON CACHÉ INTELIGENTE
# ---------------------------------------------------------
@st.cache_data(ttl=60, show_spinner=False)
def fetch_ticker_prices():
    tickers = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "CVX-USD"]
    data = {}
    try:
        df = yf.download(tickers, period="5d", interval="1d", progress=False)
        if not df.empty:
            close_df = df['Close'] if 'Close' in df else df
            for t in tickers:
                if t in close_df.columns:
                    s = close_df[t].dropna()
                    if len(s) >= 2:
                        prev = float(s.iloc[-2])
                        curr = float(s.iloc[-1])
                        pct = ((curr - prev) / prev) * 100
                        data[t] = {"price": curr, "change": pct}
                    elif len(s) == 1:
                        data[t] = {"price": float(s.iloc[-1]), "change": 0.0}
    except Exception:
        pass
    return data

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_technical_series():
    series_data = {}
    try:
        btc = yf.Ticker("BTC-USD").history(period="1y", interval="1d")
        dxy = yf.Ticker("DX-Y.NYB").history(period="6mo", interval="1d")
        if not btc.empty:
            series_data["btc"] = btc
        if not dxy.empty:
            series_data["dxy"] = dxy
    except Exception:
        pass
    return series_data

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_fear_and_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        if r.status_code == 200:
            payload = r.json()
            return int(payload['data'][0]['value'])
    except Exception:
        pass
    return 50  # Valor neutral por defecto si falla la API

@st.cache_data(ttl=21600, show_spinner=False)
def fetch_fred_macro_series(api_key: str):
    if not api_key:
        return None
    try:
        fred = Fred(api_key=api_key)
        walcl = fred.get_series('WALCL')
        ecb = fred.get_series('ECBASSETSW')
        wresbal = fred.get_series('WRESBAL')
        return {"walcl": walcl, "ecb": ecb, "wresbal": wresbal}
    except Exception:
        return None

# ---------------------------------------------------------
# CÁLCULOS CUANTITATIVOS DEL ÍNDICE DAC CONFLUENCIA
# ---------------------------------------------------------
def calculate_wilder_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])

# ---------------------------------------------------------
# OBTENCIÓN DE DATOS
# ---------------------------------------------------------
ticker_data = fetch_ticker_prices()
tech_data = fetch_technical_series()
fg_val = fetch_fear_and_greed()

# Clave FRED desde st.secrets si existe
fred_key = st.secrets.get("FRED_API_KEY", "")
macro_data = fetch_fred_macro_series(fred_key) if fred_key else None

# ---------------------------------------------------------
# 1. CABECERA: TICKERS EN TIEMPO REAL
# ---------------------------------------------------------
st.markdown("### ⚡ BOT DAC MACRO | Institutional Dashboard")

cols = st.columns(5)
names = {"BTC-USD": "BTC", "ETH-USD": "ETH", "SOL-USD": "SOL", "XRP-USD": "XRP", "CVX-USD": "CVX"}

for i, sym in enumerate(["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "CVX-USD"]):
    with cols[i]:
        if sym in ticker_data:
            p = ticker_data[sym]["price"]
            c = ticker_data[sym]["change"]
            color = "#00F7A5" if c >= 0 else "#FF4A68"
            sign = "+" if c >= 0 else ""
            fmt = f"${p:,.2f}" if p >= 1 else f"${p:,.4f}"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">{names[sym]}</div>
                <div class="metric-value">{fmt} <span style="font-size:0.85rem; color:{color};">({sign}{c:.2f}%)</span></div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">{names[sym]}</div>
                <div class="metric-value">--</div>
            </div>
            """, unsafe_allow_html=True)

st.write("")

# ---------------------------------------------------------
# 2. CÁLCULO DE PUNTUACIONES INDIVIDUALES (0 A 10)
# ---------------------------------------------------------

# F - Fear & Greed (Peso 20%)
if fg_val <= 20:
    f_score = 10.0
elif fg_val <= 40:
    f_score = 7.5
elif fg_val <= 60:
    f_score = 5.0
elif fg_val <= 80:
    f_score = 2.5
else:
    f_score = 1.0

# R - RSI Diario BTC (Peso 20%)
r_score = 5.0
current_rsi = 50.0
if "btc" in tech_data and not tech_data["btc"].empty:
    current_rsi = calculate_wilder_rsi(tech_data["btc"]['Close'])
    if current_rsi < 30:
        r_score = 10.0
    elif current_rsi <= 45:
        r_score = 7.5
    elif current_rsi <= 60:
        r_score = 5.0
    elif current_rsi <= 75:
        r_score = 3.0
    else:
        r_score = 1.0

# E - DAC EMA 200 (Peso 15%)
e_score = 5.0
ema_val = 0.0
btc_close = 0.0
if "btc" in tech_data and not tech_data["btc"].empty:
    df_btc = tech_data["btc"]
    btc_close = float(df_btc['Close'].iloc[-1])
    ema_200 = df_btc['Close'].ewm(span=200, adjust=False).mean()
    ema_val = float(ema_200.iloc[-1])
    if btc_close <= ema_val:
        e_score = 9.0
    elif btc_close <= ema_val * 1.05:
        e_score = 6.0
    else:
        e_score = 3.0

# L - Global Liquidity Index (GLI) (Peso 15%)
l_score = 5.0
if macro_data and macro_data["walcl"] is not None and macro_data["ecb"] is not None:
    try:
        combined = (macro_data["walcl"] + macro_data["ecb"]).dropna()
        if len(combined) >= 14:
            # Comparativa de tendencia con desfase aproximado
            l_score = 8.0 if combined.iloc[-1] >= combined.iloc[-14] else 4.0
    except Exception:
        pass

# M - Reservas WRESBAL (Peso 15%)
m_score = 5.0
if macro_data and macro_data["wresbal"] is not None:
    try:
        w = macro_data["wresbal"].dropna()
        if len(w) >= 14:
            sma14 = w.rolling(14).mean().iloc[-1]
            m_score = 8.0 if w.iloc[-1] >= sma14 else 3.0
    except Exception:
        pass

# D - DXY vs SMA 20 (Peso 15%)
d_score = 5.0
current_dxy = 100.0
if "dxy" in tech_data and not tech_data["dxy"].empty:
    dxy_s = tech_data["dxy"]['Close'].dropna()
    if len(dxy_s) >= 20:
        current_dxy = float(dxy_s.iloc[-1])
        dxy_sma20 = float(dxy_s.rolling(20).mean().iloc[-1])
        d_score = 8.0 if current_dxy < dxy_sma20 else 3.0

# ---------------------------------------------------------
# 3. SCORE TOTAL Y SEMÁFORO
# ---------------------------------------------------------
total_score = (
    (f_score * 0.20) +
    (r_score * 0.20) +
    (e_score * 0.15) +
    (l_score * 0.15) +
    (m_score * 0.15) +
    (d_score * 0.15)
) * 10

if total_score >= 70:
    signal_color = "#00F7A5"
    signal_label = "🟢 ZONA DE COMPRA / SUELO DETECTADO"
elif total_score >= 41:
    signal_color = "#FFB020"
    signal_label = "🟡 NEUTRAL / ESPERANDO CONFLUENCIA"
else:
    signal_color = "#FF4A68"
    signal_label = "🔴 PRECAUCIÓN / ZONA DE VENTA O TECHO"

# Panel central del Score
st.markdown(f"""
<div class="score-container">
    <div style="font-size: 1rem; color: #787b86; font-weight: 600; text-transform: uppercase;">Índice DAC Confluencia Macro</div>
    <div class="score-number" style="color: {signal_color};">{total_score:.1f} <span style="font-size: 1.5rem; color: #787b86;">/ 100</span></div>
    <div class="score-badge" style="background-color: {signal_color}22; color: {signal_color}; border: 1px solid {signal_color};">
        {signal_label}
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 4. DESGLOSE DE PILARES CONFLUENCIA
# ---------------------------------------------------------
st.markdown("#### Desglose de Componentes")
c1, c2, c3 = st.columns(3)
c4, c5, c6 = st.columns(3)

with c1:
    st.markdown(f"""
    <div class="comp-box">
        <div class="metric-title">F - Fear & Greed (20%)</div>
        <div class="metric-value">{fg_val} pts <span style="font-size:0.85rem; color:#787b86;">(Puntaje: {f_score}/10)</span></div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="comp-box">
        <div class="metric-title">R - Wilder RSI BTC (20%)</div>
        <div class="metric-value">{current_rsi:.1f} <span style="font-size:0.85rem; color:#787b86;">(Puntaje: {r_score}/10)</span></div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="comp-box">
        <div class="metric-title">E - DAC EMA 200 (15%)</div>
        <div class="metric-value">${ema_val:,.0f} <span style="font-size:0.85rem; color:#787b86;">(Puntaje: {e_score}/10)</span></div>
    </div>
    """, unsafe_allow_html=True)

with c4:
    st.markdown(f"""
    <div class="comp-box">
        <div class="metric-title">L - Global Liquidity / GLI (15%)</div>
        <div class="metric-value">{"Activo" if macro_data else "Sin API"} <span style="font-size:0.85rem; color:#787b86;">(Puntaje: {l_score}/10)</span></div>
    </div>
    """, unsafe_allow_html=True)

with c5:
    st.markdown(f"""
    <div class="comp-box">
        <div class="metric-title">M - Reservas Fed WRESBAL (15%)</div>
        <div class="metric-value">{"Activo" if macro_data else "Sin API"} <span style="font-size:0.85rem; color:#787b86;">(Puntaje: {m_score}/10)</span></div>
    </div>
    """, unsafe_allow_html=True)

with c6:
    st.markdown(f"""
    <div class="comp-box">
        <div class="metric-title">D - Índice Dólar DXY (15%)</div>
        <div class="metric-value">{current_dxy:.2f} <span style="font-size:0.85rem; color:#787b86;">(Puntaje: {d_score}/10)</span></div>
    </div>
    """, unsafe_allow_html=True)
