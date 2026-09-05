import streamlit as st
import requests
import pandas as pd
import yfinance as yf
from fredapi import Fred
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="BOT DAC MACRO", layout="wide", initial_sidebar_state="collapsed")

# Auto-refresco cada 60 segundos
st_autorefresh(interval=60 * 1000, key="data_refresh")

# Inyección de estilos idénticos al panel de referencia
st.markdown("""
    <style>
    .stApp { background-color: #0c0e14; color: #e1e7ec; }
    .card-box {
        background-color: #121620;
        border-radius: 8px;
        padding: 14px 18px;
        border: 1px solid #1f2633;
        margin-bottom: 12px;
    }
    .card-title { color: #8b949e; font-size: 13px; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 4px; }
    .card-score { font-size: 22px; font-weight: 800; color: #ffffff; }
    .card-sub { color: #6e7681; font-size: 12px; margin-top: 6px; }
    
    /* Barra degradada de confluencia */
    .slider-track {
        position: relative;
        height: 14px;
        border-radius: 7px;
        background: linear-gradient(to right, #f85149 0%, #d29922 50%, #3fb950 100%);
        margin-top: 15px;
        margin-bottom: 8px;
    }
    .slider-pin {
        position: absolute;
        top: -4px;
        width: 6px;
        height: 22px;
        background-color: #ffffff;
        border-radius: 3px;
        box-shadow: 0 0 8px rgba(0,0,0,0.8);
        transform: translateX(-50%);
    }
    .scale-labels {
        display: flex;
        justify-content: space-between;
        font-size: 11px;
        color: #6e7681;
    }
    
    /* Mini-barras por componente */
    .comp-bar-bg {
        width: 100%;
        height: 5px;
        background-color: #21262d;
        border-radius: 3px;
        margin-top: 8px;
        overflow: hidden;
    }
    .comp-bar-fill {
        height: 100%;
        border-radius: 3px;
    }
    </style>
""", unsafe_allow_html=True)

# --- CARGA DE DATOS ---
API_KEY = "90d75f0fd9f03982f65ae802c71aad75"
fred = Fred(api_key=API_KEY)

# 1. Técnico BTC (Descarga global vía Yahoo Finance: sin bloqueos de IP en EE.UU.)
try:
    btc_ticker = yf.Ticker("BTC-USD")
    hist = btc_ticker.history(period="1y", interval="1d")
    closes = hist['Close']
    highs = hist['High']
    precio_btc = closes.iloc[-1]
    
    # Banda DAC EMA 200 (High - Close)
    ema_top = highs.ewm(span=200, adjust=False).mean().iloc[-1]
    ema_bot = closes.ewm(span=200, adjust=False).mean().iloc[-1]
    dist_ema = ((precio_btc - ema_bot) / ema_bot) * 100
    
    # RSI Wilder Oficial (14)
    diff = closes.diff()
    gain = diff.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss = (-diff.clip(upper=0)).ewm(com=13, adjust=False).mean()
    rsi = (100 - (100 / (1 + (gain / loss)))).iloc[-1]
    
    score_r = 10 if rsi <= 30 else (1 if rsi >= 75 else round((100 - rsi) / 10))
    score_e = 9 if precio_btc <= ema_top else (6 if precio_btc <= ema_top * 1.05 else 3)
except:
    precio_btc, rsi, ema_bot, ema_top, dist_ema, score_r, score_e = 0, 50, 0, 0, 0, 5, 5

# 2. Sentimiento (Fear & Greed)
try:
    fg_data = requests.get("https://api.alternative.me/fng/?limit=1").json()['data'][0]
    fg_val = int(fg_data['value'])
    fg_text = fg_data['value_classification']
    score_f = round((100 - fg_val) / 10)
except:
    fg_val, fg_text, score_f = 50, "Neutral", 5

# 3. Macro Fontanería (WRESBAL y Liquidez Neta)
try:
    wresbal_series = fred.get_series('WRESBAL').dropna()
    res_actual = wresbal_series.iloc[-1]
    res_sma = wresbal_series.rolling(14).mean().iloc[-1]
    modo_qe = res_actual > res_sma
    score_m = 8 if modo_qe else 3
except:
    res_actual, modo_qe, score_m = 0, False, 5

# 4. Índice Dólar (DXY)
try:
    dxy_df = yf.Ticker("DX-Y.NYB").history(period="1mo")
    dxy_val = dxy_df['Close'].iloc[-1]
    dxy_sma = dxy_df['Close'].rolling(20).mean().iloc[-1]
    dxy_bear = dxy_val < dxy_sma
    score_d = 8 if dxy_bear else 3
except:
    dxy_val, dxy_bear, score_d = 100.0, False, 5

# 5. Global Liquidity Index (GLI)
try:
    walcl = fred.get_series('WALCL').dropna()
    ecb = fred.get_series('ECBASSETSW').dropna()
    total_gli = (walcl.iloc[-1] + ecb.iloc[-1]) / 1e6
    gli_prev = (walcl.iloc[-14] + ecb.iloc[-14]) / 1e6
    gli_sube = total_gli > gli_prev
    score_l = 8 if gli_sube else 4
except:
    total_gli, gli_sube, score_l = 30.5, False, 5

# Puntuación final de confluencia (0-100)
total_score = int((score_f * 0.20) + (score_r * 0.20) + (score_e * 0.15) + (score_l * 0.15) + (score_m * 0.15) + (score_d * 0.15)) * 10

def color_by_score(val):
    if val >= 7: return "#3fb950"
    if val >= 5: return "#d29922"
    return "#f85149"

# --- CABECERA ---
c_title, c_btc = st.columns([2, 1])
with c_title:
    st.markdown("<h2 style='margin:0; padding:0; color:#f0f6fc;'>⚡ BOT DAC MACRO</h2>", unsafe_allow_html=True)
with c_btc:
    st.markdown(f"<h3 style='margin:0; text-align:right; color:#e3b341;'>BTC: ${precio_btc:,.2f}</h3>", unsafe_allow_html=True)

st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

# --- PANEL CENTRAL ---
col_gauge, col_cards = st.columns([1.1, 2.9])

with col_gauge:
    status_label = "Zona de Compra / Suelo Detectado" if total_score >= 70 else ("Precaución / Zona de Venta o Techo" if total_score <= 40 else "Neutral / Esperando Confluencia")
    status_color = color_by_score(round(total_score / 10))
    pin_pct = min(max(total_score, 2), 98)

    st.markdown(f"""
        <div class="card-box" style="padding-top: 25px; padding-bottom: 25px;">
            <div class="card-title">ÍNDICE DAC CONFLUENCIA</div>
            <div style="font-size: 68px; font-weight: 900; color: {status_color}; line-height: 1.1;">
                {total_score} <span style="font-size: 22px; color: #6e7681; font-weight: 500;">/100</span>
            </div>
            <div style="font-size: 15px; font-weight: 700; color: {status_color}; margin-top: 6px;">
                ● {status_label}
            </div>
            <div class="slider-track">
                <div class="slider-pin" style="left: {pin_pct}%;"></div>
            </div>
            <div class="scale-labels">
                <span>0<br>Techo</span>
                <span>25</span>
                <span>50<br>Neutral</span>
                <span>75</span>
                <span>100<br>Suelo</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

with col_cards:
    # Fila 1: F, R, E
    r1c1, r1c2, r1c3 = st.columns(3)
    with r1c1:
        st.markdown(f"""
            <div class="card-box">
                <div class="card-title">F - FEAR & GREED</div>
                <div class="card-score" style="color:{color_by_score(score_f)};">{score_f}/10</div>
                <div class="comp-bar-bg"><div class="comp-bar-fill" style="width:{score_f*10}%; background-color:{color_by_score(score_f)};"></div></div>
                <div class="card-sub">FG actual: {fg_val} | {fg_text}</div>
            </div>
        """, unsafe_allow_html=True)
    with r1c2:
        st.markdown(f"""
            <div class="card-box">
                <div class="card-title">R - RSI DIARIO</div>
                <div class="card-score" style="color:{color_by_score(score_r)};">{score_r}/10</div>
                <div class="comp-bar-bg"><div class="comp-bar-fill" style="width:{score_r*10}%; background-color:{color_by_score(score_r)};"></div></div>
                <div class="card-sub">RSI 14d: {rsi:.1f}</div>
            </div>
        """, unsafe_allow_html=True)
    with r1c3:
        st.markdown(f"""
            <div class="card-box">
                <div class="card-title">E - DAC EMA 200</div>
                <div class="card-score" style="color:{color_by_score(score_e)};">{score_e}/10</div>
                <div class="comp-bar-bg"><div class="comp-bar-fill" style="width:{score_e*10}%; background-color:{color_by_score(score_e)};"></div></div>
                <div class="card-sub">${ema_bot:,.0f} - ${ema_top:,.0f} ({'+' if dist_ema>=0 else ''}{dist_ema:.1f}%)</div>
            </div>
        """, unsafe_allow_html=True)

    # Fila 2: L, D, M
    r2c1, r2c2, r2c3 = st.columns(3)
    with r2c1:
        st.markdown(f"""
            <div class="card-box">
                <div class="card-title">L - LIQUIDEZ GLOBAL (GLI)</div>
                <div class="card-score" style="color:{color_by_score(score_l)};">{score_l}/10</div>
                <div class="comp-bar-bg"><div class="comp-bar-fill" style="width:{score_l*10}%; background-color:{color_by_score(score_l)};"></div></div>
                <div class="card-sub">Bancos Centrales (Offset 91d): {'Expansión' if gli_sube else 'Contracción'}</div>
            </div>
        """, unsafe_allow_html=True)
    with r2c2:
        st.markdown(f"""
            <div class="card-box">
                <div class="card-title">D - DOLLAR DXY</div>
                <div class="card-score" style="color:{color_by_score(score_d)};">{score_d}/10</div>
                <div class="comp-bar-bg"><div class="comp-bar-fill" style="width:{score_d*10}%; background-color:{color_by_score(score_d)};"></div></div>
                <div class="card-sub">DXY: {dxy_val:.2f} | {'Bajista (Lubricante)' if dxy_bear else 'Alcista (Drenaje)'}</div>
            </div>
        """, unsafe_allow_html=True)
    with r2c3:
        qe_txt = "🟢 MODO QE" if modo_qe else "🔴 MODO QT"
        st.markdown(f"""
            <div class="card-box">
                <div class="card-title">M - RESERVAS WRESBAL</div>
                <div class="card-score" style="color:{color_by_score(score_m)};">{score_m}/10</div>
                <div class="comp-bar-bg"><div class="comp-bar-fill" style="width:{score_m*10}%; background-color:{color_by_score(score_m)};"></div></div>
                <div class="card-sub">{qe_txt} (${res_actual/1e6:.2f}T)</div>
            </div>
        """, unsafe_allow_html=True)
