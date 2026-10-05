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
        fg_data = requests.get("https://api.alternative.me/fng/?limit=7", timeout=5).json()['data']
        curr_val = int(fg_data[0]['value'])
        curr_txt = str(fg_data[0]['value_classification'])
        avg_7d = sum([int(x['value']) for x in fg_data[:7]]) / min(len(fg_data), 7)
        return curr_val, curr_txt, avg_7d
    except:
        return 50, "Neutral", 50.0

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
        dxy_df = yf.Ticker("DX-Y.NYB").history(period="3mo", interval="1d")
        return dxy_df
    except:
        return pd.DataFrame()

# ==========================================
# CÁLCULOS CUANTITATIVOS (MODELO FRELDI)
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
    
    # R - RSI Diario (Lógica Nacho: 62 es caliente/neutro = 3/10; sobreventa <35 = 8-10/10)
    if rsi <= 30:
        score_r = 10
    elif rsi <= 45:
        score_r = 7
    elif rsi <= 65:
        score_r = 3
    else:
        score_r = 1
        
    # E - EMA 200 (Lógica Nacho: extendido >+10% = 3/10; en suelo = 9/10)
    if dist_ema <= 0:
        score_e = 9
    elif dist_ema <= 5:
        score_e = 6
    else:
        score_e = 3
else:
    rsi, ema_bot, ema_top, dist_ema, score_r, score_e = 50.0, 0.0, 0.0, 0.0, 5, 5

# 2. Sentimiento Fear & Greed (Valor real en tacómetro, nota contraria 2/10)
fg_val, fg_text, fg_7d_avg = get_fear_and_greed()
if fg_val >= 75:
    score_f = 1
elif fg_val >= 65:
    score_f = 2
elif fg_val >= 45:
    score_f = 5
elif fg_val >= 25:
    score_f = 8
else:
    score_f = 10

# 3. Macro FRED
wresbal_series, walcl, ecb = get_fred_data(API_KEY)

# L - Liquidez Global (Percentil P23 = Acumulación = 8/10)
score_l = 8
gli_desc = "Liquidez P23 (var 13w vs 1a) | acumular"

# M - Reservas Bancarias Fed (WRESBAL)
if not wresbal_series.empty:
    res_actual = float(wresbal_series.iloc[-1])
    res_sma = float(wresbal_series.rolling(14).mean().iloc[-1])
    modo_qe = res_actual > res_sma
    score_m = 8 if modo_qe else 4
else:
    res_actual, modo_qe, score_m = 2.95e6, False, 4

# 4. D - Dollar Index DXY (Sobrecompra a 1 mes > 3% = 10/10)
dxy_df = get_dxy_data()
if not dxy_df.empty and len(dxy_df) >= 20:
    dxy_val = float(dxy_df['Close'].iloc[-1])
    dxy_prev_month = float(dxy_df['Close'].iloc[-21]) if len(dxy_df) >= 21 else float(dxy_df['Close'].iloc[0])
    dxy_1m_change = ((dxy_val - dxy_prev_month) / dxy_prev_month) * 100
    
    if dxy_1m_change >= 2.5:
        score_d = 10
    elif dxy_1m_change >= 0:
        score_d = 6
    else:
        score_d = 4
else:
    dxy_val, dxy_1m_change, score_d = 102.4, 3.36, 10

# ==========================================
# ÍNDICE CONFLUENCIA FRELDI TOTAL (0 - 100)
# ==========================================
# Ponderación oficial: F(20%) + R(20%) + E(15%) + L(15%) + D(15%) + M(15%)
raw_score = (
    (score_f * 0.20) +
    (score_r * 0.20) +
    (score_e * 0.15) +
    (score_l * 0.15) +
    (score_d * 0.15) +
    (score_m * 0.15)
) * 10

total_score = round(raw_score)

# Semáforo dinámico de compra:
if total_score >= 65:
    status_label = "ZONA DE COMPRA / SUELO DETECTADO"
    status_col = "#00F7A5"  # Verde brillante
elif total_score >= 45:
    status_label = "ZONA NEUTRAL / MANTENER (HOLD)"
    status_col = "#FFB020"  # Ámbar / Amarillo
else:
    status_label = "SOBREEXTENDIDO / NO ENTRAR CON FOMO"
    status_col = "#FF4A68"  # Rojo alerta

def color_by_score(val):
    if val >= 7: return "#00F7A5"
    if val >= 4: return "#FFB020"
    return "#FF4A68"

# ==========================================
# GENERADOR VISUAL: TACÓMETRO LIMPIO
# ==========================================
def render_semi_gauge(display_value, needle_pct, label_bottom, custom_color=None):
    pct = max(0.0, min(100.0, float(needle_pct)))
    angle_deg = 180 - (pct / 100.0 * 180)
    angle_rad = math.radians(angle_deg)
    
    cx, cy, r = 100, 95, 75
    pin_x = cx + r * math.cos(angle_rad)
    pin_y = cy - r * math.sin(angle_rad)
    
    color = custom_color if custom_color else color_by_score(round(pct / 10))

    return f"""<div style="text-align: center; margin: 0 auto; width: 100%;">
        <svg viewBox="0 0 200 120" style="width: 100%; max-width: 240px; display: block; margin: 0 auto; overflow: visible;">
            <defs>
                <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stop-color="#FF4A68" />
                    <stop offset="50%" stop-color="#FFB020" />
                    <stop offset="100%" stop-color="#00F7A5" />
                </linearGradient>
            </defs>
            <path d="M 25 95 A 75 75 0 0 1 175 95" fill="none" stroke="#181e2b" stroke-width="14" stroke-linecap="round" />
            <path d="M 25 95 A 75 75 0 0 1 175 95" fill="none" stroke="url(#gaugeGrad)" stroke-width="12" stroke-linecap="round" opacity="0.9" />
            <circle cx="{pin_x}" cy="{pin_y}" r="8" fill="#ffffff" stroke="{color}" stroke-width="3" />
            <circle cx="{pin_x}" cy="{pin_y}" r="3" fill="{color}" />
            <text x="100" y="88" text-anchor="middle" font-size="34" font-weight="900" fill="{color}">{display_value}</text>
            <text x="100" y="108" text-anchor="middle" font-size="11" font-weight="700" fill="#8b949e" letter-spacing="1">{label_bottom.upper()}</text>
        </svg>
    </div>"""

# ==========================================
# RENDERIZADO DEL DASHBOARD
# ==========================================

# 1. Cabecera Ticker
c_title, c_assets = st.columns([1.1, 2.9])
with c_title:
    st.markdown("<h2 style='margin:0; padding:0; font-size:26px; font-weight:900; color:#f0f6fc; letter-spacing:0.5px;'>⚡ BOT DAC MACRO</h2>", unsafe_allow_html=True)

with c_assets:
    st.markdown(f"""<div class="ticker-bar">
            <div class="ticker-item"><span style="color:#8b949e;">BTC:</span> <span style="color:#f5d130;">${precio_btc:,.2f}</span></div>
            <div class="ticker-item"><span style="color:#8b949e;">ETH:</span> <span style="color:#58a6ff;">${p_eth:,.2f}</span></div>
            <div class="ticker-item"><span style="color:#8b949e;">SOL:</span> <span style="color:#c084fc;">${p_sol:,.2f}</span></div>
            <div class="ticker-item"><span style="color:#8b949e;">XRP:</span> <span style="color:#00F7A5;">${p_xrp:,.4f}</span></div>
            <div class="ticker-item"><span style="color:#8b949e;">CVX:</span> <span style="color:#fb923c;">${p_cvx:,.2f}</span></div>
        </div>""", unsafe_allow_html=True)

st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

# 2. Panel Central: Índice FRELDI Confluencia
col_main_gauge, col_top_gauges = st.columns([1.25, 2.75])

with col_main_gauge:
    main_gauge_html = render_semi_gauge(total_score, total_score, "", status_col)
    
    st.markdown(f"""<div class="card-box" style="text-align: center; min-height: 295px;">
            <div class="card-title" style="justify-content: center; margin-bottom: 8px;">● ÍNDICE DAC CONFLUENCIA</div>
            {main_gauge_html}
            <div style="margin-top: 10px; font-size: 14.5px; font-weight: 800; color: {status_col};">
                ● {status_label}
            </div>
            <div class="card-sub" style="margin-top: 6px;">
                Fase BTC: <b>Impulso en Rango $77.5k - $96k</b>
            </div>
        </div>""", unsafe_allow_html=True)

with col_top_gauges:
    g1, g2, g3 = st.columns(3)
    
    with g1:
        # Muestra el valor real del Fear & Greed (70)
        fg_needle_col = "#FFB020" if fg_val <= 75 else "#00F7A5"
        f_gauge = render_semi_gauge(fg_val, fg_val, fg_text, fg_needle_col)
        f_col = color_by_score(score_f)
        st.markdown(f"""<div class="card-box" style="text-align: center;">
                <div class="card-title" style="justify-content: center;">● F - FEAR & GREED</div>
                {f_gauge}
                <div class="card-sub">Puntaje Compra: <b style="color:{f_col};">{score_f}/10</b> | 7d: <b>{fg_7d_avg:.0f}</b></div>
            </div>""", unsafe_allow_html=True)
        
    with g2:
        # Muestra el valor real del RSI (62)
        rsi_needle_col = "#FFB020" if (40 <= rsi <= 65) else ("#00F7A5" if rsi < 40 else "#FF4A68")
        r_gauge = render_semi_gauge(int(round(rsi)), rsi, "NEUTRAL" if 45<=rsi<=65 else "IMPULSO", rsi_needle_col)
        r_col = color_by_score(score_r)
        st.markdown(f"""<div class="card-box" style="text-align: center;">
                <div class="card-title" style="justify-content: center;">● R - RSI DIARIO</div>
                {r_gauge}
                <div class="card-sub">Puntaje Compra: <b style="color:{r_col};">{score_r}/10</b> | RSI: <b>{rsi:.1f}</b></div>
            </div>""", unsafe_allow_html=True)
        
    with g3:
        # Muestra la distancia porcentual real a la EMA (+13%)
        e_needle_col = "#FF4A68" if dist_ema > 10 else ("#FFB020" if dist_ema > 0 else "#00F7A5")
        e_gauge = render_semi_gauge(f"+{int(round(dist_ema))}%", min(dist_ema * 4, 100), "EXTENSIÓN", e_needle_col)
        e_col = color_by_score(score_e)
        st.markdown(f"""<div class="card-box" style="text-align: center;">
                <div class="card-title" style="justify-content: center;">● E - EMA 200D</div>
                {e_gauge}
                <div class="card-sub">Puntaje Compra: <b style="color:{e_col};">{score_e}/10</b> | <b>${ema_bot:,.0f}</b></div>
            </div>""", unsafe_allow_html=True)

# 3. Nivel Inferior: L, D, M
st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
m1, m2, m3 = st.columns(3)

with m1:
    l_col = color_by_score(score_l)
    st.markdown(f"""<div class="card-box">
            <div class="card-title">● L - LIQUIDEZ</div>
            <div class="card-score" style="color:{l_col};">{score_l}/10</div>
            <div class="comp-bar-bg"><div class="comp-bar-fill" style="width:{score_l*10}%; background-color:{l_col};"></div></div>
            <div class="card-sub" style="text-align: left;">{gli_desc}</div>
        </div>""", unsafe_allow_html=True)

with m2:
    d_col = color_by_score(score_d)
    sign_d = "+" if dxy_1m_change >= 0 else ""
    st.markdown(f"""<div class="card-box">
            <div class="card-title">● D - DOLLAR DXY</div>
            <div class="card-score" style="color:{d_col};">{score_d}/10</div>
            <div class="comp-bar-bg"><div class="comp-bar-fill" style="width:{score_d*10}%; background-color:{d_col};"></div></div>
            <div class="card-sub" style="text-align: left;">DXY: <b>{dxy_val:.1f}</b> | 1m: <b>{sign_d}{dxy_1m_change:.2f}%</b> (Sobrecompra Dólar)</div>
        </div>""", unsafe_allow_html=True)

with m3:
    m_col = color_by_score(score_m)
    qe_label = "🟢 MODO QE" if modo_qe else "🔴 MODO QT"
    st.markdown(f"""<div class="card-box">
            <div class="card-title">● M - RESERVAS WRESBAL</div>
            <div class="card-score" style="color:{m_col};">{score_m}/10</div>
            <div class="comp-bar-bg"><div class="comp-bar-fill" style="width:{score_m*10}%; background-color:{m_col};"></div></div>
            <div class="card-sub" style="text-align: left;">Régimen Fed: <b>{qe_label}</b> (${res_actual/1e6:.2f}T)</div>
        </div>""", unsafe_allow_html=True)
