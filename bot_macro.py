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
        padding: 20px 22px;
        border: 1px solid #1a2232;
        margin-bottom: 16px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
    }

    .card-title { 
        color: #7d8590; 
        font-size: 13px; 
        font-weight: 700; 
        letter-spacing: 1px; 
        text-transform: uppercase;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    
    .card-score { 
        font-size: 28px; 
        font-weight: 900; 
        margin-top: 4px;
    }
    
    .card-sub { 
        color: #8b949e; 
        font-size: 12.5px; 
        font-weight: 500; 
        margin-top: 4px; 
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
        height: 6px;
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
    precios = {"BTC-USD": 0.0, "ETH-USD": 0.0, "SOL-USD": 0.0, "XRP-USD": 0.0, "CVX-USD": 0.0}
    try:
        df = yf.download(tickers, period="1d", interval="1m", progress=False)
        if not df.empty:
            close_data = df['Close'] if 'Close' in df else df
            for t in tickers:
                if t in close_data.columns:
                    s = close_data[t].dropna()
                    if len(s) > 0:
                        precios[t] = float(s.iloc[-1])
    except:
        pass
    return precios

@st.cache_data(ttl=900, show_spinner=False)
def get_btc_history():
    try:
        btc_ticker = yf.Ticker("BTC-USD")
        return btc_ticker.history(period="1y", interval="1d")
    except:
        return pd.DataFrame()

@st.cache_data(ttl=1800, show_spinner=False)
def get_fear_and_greed():
    try:
        fg_data = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5).json()['data'][0]
        return int(fg_data['value']), str(fg_data['value_classification'])
    except:
        return 50, "Neutral"

@st.cache_data(ttl=21600, show_spinner=False)
def get_fred_data(api_key):
    try:
        fred = Fred(api_key=api_key)
        wresbal = fred.get_series('WRESBAL').dropna()
        walcl = fred.get_series('WALCL').dropna()
        ecb = fred.get_series('ECBASSETSW').dropna()
        return wresbal, walcl, ecb
    except:
        return pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float)

@st.cache_data(ttl=1800, show_spinner=False)
def get_dxy_data():
    try:
        dxy_df = yf.Ticker("DX-Y.NYB").history(period="1mo")
        return dxy_df
    except:
        return pd.DataFrame()

# ==========================================
# CÁLCULOS CUANTITATIVOS (TUS FÓRMULAS EXACTAS)
# ==========================================

live_prices = get_live_prices()
precio_btc = live_prices["BTC-USD"]
p_eth = live_prices["ETH-USD"]
p_sol = live_prices["SOL-USD"]
p_xrp = live_prices["XRP-USD"]
p_cvx = live_prices["CVX-USD"]

# 1. Técnico BTC (RSI y EMA 200)
hist = get_btc_history()
if not hist.empty:
    closes = hist['Close']
    highs = hist['High']
    if precio_btc == 0.0:
        precio_btc = float(closes.iloc[-1])
    
    ema_top = float(highs.ewm(span=200, adjust=False).mean().iloc[-1])
    ema_bot = float(closes.ewm(span=200, adjust=False).mean().iloc[-1])
    dist_ema = ((precio_btc - ema_bot) / ema_bot) * 100
    
    diff = closes.diff()
    gain = diff.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss = (-diff.clip(upper=0)).ewm(com=13, adjust=False).mean()
    rsi = float((100 - (100 / (1 + (gain / loss)))).iloc[-1])
    
    score_r = 10 if rsi <= 30 else (1 if rsi >= 75 else round((100 - rsi) / 10))
    score_e = 9 if precio_btc <= ema_top else (6 if precio_btc <= ema_top * 1.05 else 3)
else:
    rsi, ema_bot, ema_top, dist_ema, score_r, score_e = 50.0, 0.0, 0.0, 0.0, 5, 5

# 2. Sentimiento Fear & Greed
fg_val, fg_text = get_fear_and_greed()
score_f = round((100 - fg_val) / 10)

# 3. Macro FRED (WRESBAL y GLI)
wresbal_series, walcl, ecb = get_fred_data(API_KEY)

if not wresbal_series.empty:
    res_actual = float(wresbal_series.iloc[-1])
    res_sma = float(wresbal_series.rolling(14).mean().iloc[-1])
    modo_qe = res_actual > res_sma
    score_m = 8 if modo_qe else 3
else:
    res_actual, modo_qe, score_m = 0.0, False, 5

if not walcl.empty and not ecb.empty:
    total_gli = float(walcl.iloc[-1] + ecb.iloc[-1]) / 1e6
    gli_prev = float(walcl.iloc[-14] + ecb.iloc[-14]) / 1e6
    gli_sube = total_gli > gli_prev
    score_l = 8 if gli_sube else 4
else:
    total_gli, gli_sube, score_l = 30.5, False, 5

# 4. DXY
dxy_df = get_dxy_data()
if not dxy_df.empty:
    dxy_val = float(dxy_df['Close'].iloc[-1])
    dxy_sma = float(dxy_df['Close'].rolling(20).mean().iloc[-1])
    dxy_bear = dxy_val < dxy_sma
    score_d = 8 if dxy_bear else 3
else:
    dxy_val, dxy_bear, score_d = 100.0, False, 5

# Score Total Confluencia
total_score = int((score_f * 0.20) + (score_r * 0.20) + (score_e * 0.15) + (score_l * 0.15) + (score_m * 0.15) + (score_d * 0.15)) * 10

def color_by_score(val):
    if val >= 7: return "#00F7A5"  # Verde brillante
    if val >= 5: return "#FFB020"  # Ámbar/Amarillo
    return "#FF4A68"              # Rojo alerta

# ==========================================
# GENERADOR VISUAL: TACÓMETRO ESTILO DCAPITAL
# ==========================================
def render_semi_gauge(score, label_bottom, size="medium"):
    pct = max(0.0, min(100.0, float(score)))
    # Cálculo de ángulo en semicírculo (de 180° a 0°)
    angle_deg = 180 - (pct / 100.0 * 180)
    angle_rad = math.radians(angle_deg)
    
    cx, cy, r = 100, 95, 75
    pin_x = cx + r * math.cos(angle_rad)
    pin_y = cy - r * math.sin(angle_rad)
    
    color = color_by_score(round(pct / 10))

    return f"""
    <div style="text-align: center; margin: 0 auto; width: 100%;">
        <svg viewBox="0 0 200 125" style="width: 100%; max-width: 250px; display: block; margin: 0 auto; overflow: visible;">
            <defs>
                <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stop-color="#FF4A68" />
                    <stop offset="50%" stop-color="#FFB020" />
                    <stop offset="100%" stop-color="#00F7A5" />
                </linearGradient>
            </defs>
            <!-- Arco base oscuro -->
            <path d="M 25 95 A 75 75 0 0 1 175 95" fill="none" stroke="#181e2b" stroke-width="14" stroke-linecap="round" />
            <!-- Arco gradiente de color -->
            <path d="M 25 95 A 75 75 0 0 1 175 95" fill="none" stroke="url(#gaugeGrad)" stroke-width="12" stroke-linecap="round" opacity="0.9" />
            <!-- Punto indicador exterior -->
            <circle cx="{pin_x}" cy="{pin_y}" r="8" fill="#ffffff" stroke="{color}" stroke-width="3" filter="drop-shadow(0 0 6px rgba(0,0,0,0.8))"/>
            <circle cx="{pin_x}" cy="{pin_y}" r="3" fill="{color}" />
            <!-- Valor central grande -->
            <text x="100" y="88" text-anchor="middle" font-size="34" font-weight="900" fill="{color}">{int(pct)}</text>
            <text x="100" y="108" text-anchor="middle" font-size="11" font-weight="700" fill="#8b949e" letter-spacing="1">{label_bottom.upper()}</text>
        </svg>
    </div>
    """

# ==========================================
# RENDERIZADO DEL DASHBOARD
# ==========================================

# 1. Cabecera Ticker
c_title, c_assets = st.columns([1.1, 2.9])
with c_title:
    st.markdown("<h2 style='margin:0; padding:0; font-size:26px; font-weight:900; color:#f0f6fc; letter-spacing:0.5px;'>⚡ BOT DAC MACRO</h2>", unsafe_allow_html=True)

with c_assets:
    st.markdown(f"""
        <div class="ticker-bar">
            <div class="ticker-item"><span style="color:#8b949e;">BTC:</span> <span style="color:#f5d130;">${precio_btc:,.2f}</span></div>
            <div class="ticker-item"><span style="color:#8b949e;">ETH:</span> <span style="color:#58a6ff;">${p_eth:,.2f}</span></div>
            <div class="ticker-item"><span style="color:#8b949e;">SOL:</span> <span style="color:#c084fc;">${p_sol:,.2f}</span></div>
            <div class="ticker-item"><span style="color:#8b949e;">XRP:</span> <span style="color:#00F7A5;">${p_xrp:,.4f}</span></div>
            <div class="ticker-item"><span style="color:#8b949e;">CVX:</span> <span style="color:#fb923c;">${p_cvx:,.2f}</span></div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

# 2. Panel Central: Índice DAC Confluencia
col_main_gauge, col_top_gauges = st.columns([1.25, 2.75])

with col_main_gauge:
    status_label = "ZONA DE COMPRA / SUELO DETECTADO" if total_score >= 70 else ("PRECAUCIÓN / ZONA DE VENTA O TECHO" if total_score <= 40 else "NEUTRAL / ESPERANDO CONFLUENCIA")
    status_col = color_by_score(round(total_score / 10))
    
    st.markdown(f"""
        <div class="card-box" style="text-align: center; min-height: 295px;">
            <div class="card-title" style="justify-content: center; margin-bottom: 8px;">● ÍNDICE DAC CONFLUENCIA MACRO</div>
            {render_semi_gauge(total_score, status_label)}
            <div style="margin-top: 10px; font-size: 13.5px; font-weight: 800; color: {status_col};">
                ● {status_label}
            </div>
        </div>
    """, unsafe_allow_html=True)

with col_top_gauges:
    # Tacómetros superiores: F, R, E
    g1, g2, g3 = st.columns(3)
    
    with g1:
        st.markdown(f"""
            <div class="card-box" style="text-align: center;">
                <div class="card-title" style="justify-content: center;">● FEAR & GREED CRYPTO</div>
                {render_semi_gauge(fg_val, fg_text)}
                <div class="card-sub" style="margin-top: 8px;">Puntaje Contrario: <b style="color:{color_by_score(score_f)};">{score_f}/10</b></div>
            </div>
        """, unsafe_allow_html=True)
        
    with g2:
        rsi_label = "Sobreventa" if rsi < 30 else ("Sobrecompra" if rsi > 70 else "Neutral")
        st.markdown(f"""
            <div class="card-box" style="text-align: center;">
                <div class="card-title" style="justify-content: center;">● WILDER RSI BTC</div>
                {render_semi_gauge(rsi, rsi_label)}
                <div class="card-sub" style="margin-top: 8px;">Puntaje Técnico: <b style="color:{color_by_score(score_r)};">{score_r}/10</b></div>
            </div>
        """, unsafe_allow_html=True)
        
    with g3:
        # Puntuación EMA normalizada a base 100 para el arco
        ema_pct = min(max((score_e / 10.0) * 100, 10), 100)
        ema_status = "En Soporte" if score_e >= 9 else ("Rango +5%" if score_e >= 6 else "Extensión")
        st.markdown(f"""
            <div class="card-box" style="text-align: center;">
                <div class="card-title" style="justify-content: center;">● DAC EMA 200 CANAL</div>
                {render_semi_gauge(ema_pct, ema_status)}
                <div class="card-sub" style="margin-top: 8px;">${ema_bot:,.0f} - ${ema_top:,.0f} ({'+' if dist_ema>=0 else ''}{dist_ema:.1f}%)</div>
            </div>
        """, unsafe_allow_html=True)

# 3. Nivel Inferior: Fontanería de Liquidez y Macro (L, D, M)
st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
m1, m2, m3 = st.columns(3)

with m1:
    st.markdown(f"""
        <div class="card-box">
            <div class="card-title">● L - LIQUIDEZ GLOBAL (GLI - OFFSET 91D)</div>
            <div class="card-score" style="color:{color_by_score(score_l)};">{score_l}/10</div>
            <div class="comp-bar-bg"><div class="comp-bar-fill" style="width:{score_l*10}%; background-color:{color_by_score(score_l)};"></div></div>
            <div class="card-sub">Bancos Centrales: <b>{'Expansión de Liquidez' if gli_sube else 'Contracción'}</b> (${total_gli:.2f}T)</div>
        </div>
    """, unsafe_allow_html=True)

with m2:
    st.markdown(f"""
        <div class="card-box">
            <div class="card-title">● D - DOLLAR INDEX (DXY VS SMA 20)</div>
            <div class="card-score" style="color:{color_by_score(score_d)};">{score_d}/10</div>
            <div class="comp-bar-bg"><div class="comp-bar-fill" style="width:{score_d*10}%; background-color:{color_by_score(score_d)};"></div></div>
            <div class="card-sub">DXY: <b>{dxy_val:.2f}</b> | {'Bajista (Lubricante para Riesgo)' if dxy_bear else 'Alcista (Drenaje de Liquidez)'}</div>
        </div>
    """, unsafe_allow_html=True)

with m3:
    qe_label = "🟢 MODO QE (Inyección)" if modo_qe else "🔴 MODO QT (Absorción)"
    st.markdown(f"""
        <div class="card-box">
            <div class="card-title">● M - RESERVAS BANCARIAS FED (WRESBAL)</div>
            <div class="card-score" style="color:{color_by_score(score_m)};">{score_m}/10</div>
            <div class="comp-bar-bg"><div class="comp-bar-fill" style="width:{score_m*10}%; background-color:{color_by_score(score_m)};"></div></div>
            <div class="card-sub">Régimen Fed: <b>{qe_label}</b> (${res_actual/1e6:.2f}T)</div>
        </div>
    """, unsafe_allow_html=True)
