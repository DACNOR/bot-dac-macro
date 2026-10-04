import streamlit as st
import requests
import pandas as pd
import yfinance as yf
from fredapi import Fred
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="BOT DAC MACRO", layout="wide", initial_sidebar_state="collapsed")

# Auto-refresco cada 60 segundos
st_autorefresh(interval=60 * 1000, key="data_refresh")

# Estilos optimizados: tarjetas grandes y tipografía legible
st.markdown("""
    <style>
    /* Ocultar barra superior, icono de GitHub y menús */
    header[data-testid="stHeader"] {
        display: none !important;
    }

    .stApp { background-color: #0b0e14; color: #e1e7ec; }
    
    /* Contenedor principal con margen controlado */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        max-width: 96% !important;
    }

    /* Tarjetas principales ampliadas */
    .card-box {
        background-color: #131722;
        border-radius: 12px;
        padding: 22px 24px;
        border: 1px solid #232936;
        margin-bottom: 16px;
        min-height: 145px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    
    .card-title { 
        color: #8b949e; 
        font-size: 14px; 
        font-weight: 700; 
        letter-spacing: 0.8px; 
        text-transform: uppercase;
    }
    
    .card-score { 
        font-size: 32px; 
        font-weight: 900; 
        line-height: 1.2; 
        margin-top: 4px;
    }
    
    .card-sub { 
        color: #7d8590; 
        font-size: 13px; 
        font-weight: 500; 
        margin-top: 6px; 
    }
    
    /* Barra degradada de confluencia */
    .slider-track {
        position: relative;
        height: 16px;
        border-radius: 8px;
        background: linear-gradient(to right, #f85149 0%, #d29922 50%, #3fb950 100%);
        margin-top: 22px;
        margin-bottom: 10px;
    }
    .slider-pin {
        position: absolute;
        top: -5px;
        width: 7px;
        height: 26px;
        background-color: #ffffff;
        border-radius: 4px;
        box-shadow: 0 0 10px rgba(0,0,0,0.9);
        transform: translateX(-50%);
    }
    .scale-labels {
        display: flex;
        justify-content: space-between;
        font-size: 12px;
        color: #8b949e;
        font-weight: 600;
    }
    
    /* Mini-barras por componente */
    .comp-bar-bg {
        width: 100%;
        height: 7px;
        background-color: #21262d;
        border-radius: 4px;
        margin-top: 10px;
        overflow: hidden;
    }
    .comp-bar-fill {
        height: 100%;
        border-radius: 4px;
    }

    /* Cinta de precios superior */
    .ticker-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        justify-content: flex-end;
        align-items: center;
    }
    .ticker-item {
        background-color: #131722;
        border: 1px solid #232936;
        padding: 8px 14px;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 700;
    }
    </style>
""", unsafe_allow_html=True)

# --- FUNCIONES DE DESCARGA CON CACHÉ INTELIGENTE ---
API_KEY = "90d75f0fd9f03982f65ae802c71aad75"

@st.cache_data(ttl=900, show_spinner=False)
def get_btc_data():
    try:
        btc_ticker = yf.Ticker("BTC-USD")
        hist = btc_ticker.history(period="1y", interval="1d")
        return hist
    except:
        return pd.DataFrame()

@st.cache_data(ttl=60, show_spinner=False)
def get_alt_tickers():
    try:
        tickers = yf.Tickers("ETH-USD SOL-USD XRP-USD CVX-USD")
        p_eth = tickers.tickers['ETH-USD'].history(period="1d")['Close'].iloc[-1]
        p_sol = tickers.tickers['SOL-USD'].history(period="1d")['Close'].iloc[-1]
        p_xrp = tickers.tickers['XRP-USD'].history(period="1d")['Close'].iloc[-1]
        p_cvx = tickers.tickers['CVX-USD'].history(period="1d")['Close'].iloc[-1]
        return float(p_eth), float(p_sol), float(p_xrp), float(p_cvx)
    except:
        return 0.0, 0.0, 0.0, 0.0

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

# --- PROCESAMIENTO Y CÁLCULOS ---

# 1. Técnico BTC (Yahoo Finance)
hist = get_btc_data()
if not hist.empty:
    closes = hist['Close']
    highs = hist['High']
    precio_btc = closes.iloc[-1]
    
    # Banda DAC EMA 200
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
else:
    precio_btc, rsi, ema_bot, ema_top, dist_ema, score_r, score_e = 0, 50, 0, 0, 0, 5, 5

# 2. Descarga de Activos Clave
p_eth, p_sol, p_xrp, p_cvx = get_alt_tickers()

# 3. Sentimiento (Fear & Greed)
fg_val, fg_text = get_fear_and_greed()
score_f = round((100 - fg_val) / 10)

# 4 y 6. FRED (WRESBAL y GLI)
wresbal_series, walcl, ecb = get_fred_data(API_KEY)

# Macro Fontanería (WRESBAL)
if not wresbal_series.empty:
    res_actual = wresbal_series.iloc[-1]
    res_sma = wresbal_series.rolling(14).mean().iloc[-1]
    modo_qe = res_actual > res_sma
    score_m = 8 if modo_qe else 3
else:
    res_actual, modo_qe, score_m = 0, False, 5

# Global Liquidity Index (GLI)
if not walcl.empty and not ecb.empty:
    total_gli = (walcl.iloc[-1] + ecb.iloc[-1]) / 1e6
    gli_prev = (walcl.iloc[-14] + ecb.iloc[-14]) / 1e6
    gli_sube = total_gli > gli_prev
    score_l = 8 if gli_sube else 4
else:
    total_gli, gli_sube, score_l = 30.5, False, 5

# 5. Índice Dólar (DXY)
dxy_df = get_dxy_data()
if not dxy_df.empty:
    dxy_val = dxy_df['Close'].iloc[-1]
    dxy_sma = dxy_df['Close'].rolling(20).mean().iloc[-1]
    dxy_bear = dxy_val < dxy_sma
    score_d = 8 if dxy_bear else 3
else:
    dxy_val, dxy_bear, score_d = 100.0, False, 5

# Confluencia final (0-100)
total_score = int((score_f * 0.20) + (score_r * 0.20) + (score_e * 0.15) + (score_l * 0.15) + (score_m * 0.15) + (score_d * 0.15)) * 10

def color_by_score(val):
    if val >= 7: return "#3fb950"
    if val >= 5: return "#d29922"
    return "#f85149"

# --- CABECERA ---
c_title, c_assets = st.columns([1.1, 2.9])
with c_title:
    st.markdown("<h1 style='margin:0; padding:0; font-size:32px; font-weight:900; color:#f0f6fc;'>⚡ BOT DAC MACRO</h1>", unsafe_allow_html=True)

with c_assets:
    st.markdown(f"""
        <div class="ticker-bar">
            <div class="ticker-item"><span style="color:#8b949e;">BTC:</span> <span style="color:#e3b341;">${precio_btc:,.2f}</span></div>
            <div class="ticker-item"><span style="color:#8b949e;">ETH:</span> <span style="color:#58a6ff;">${p_eth:,.2f}</span></div>
            <div class="ticker-item"><span style="color:#8b949e;">SOL:</span> <span style="color:#bc8cff;">${p_sol:,.2f}</span></div>
            <div class="ticker-item"><span style="color:#8b949e;">XRP:</span> <span style="color:#3fb950;">${p_xrp:,.4f}</span></div>
            <div class="ticker-item"><span style="color:#8b949e;">CVX:</span> <span style="color:#f0883e;">${p_cvx:,.2f}</span></div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

# --- CUERPO PRINCIPAL ---
col_gauge, col_cards = st.columns([1.15, 2.85])

with col_gauge:
    status_label = "Zona de Compra / Suelo Detectado" if total_score >= 70 else ("Precaución / Zona de Venta o Techo" if total_score <= 40 else "Neutral / Esperando Confluencia")
    status_color = color_by_score(round(total_score / 10))
    pin_pct = min(max(total_score, 2), 98)

    st.markdown(f"""
        <div class="card-box" style="padding-top: 30px; padding-bottom: 30px; min-height: 310px;">
            <div class="card-title" style="font-size: 15px;">ÍNDICE DAC CONFLUENCIA</div>
            <div style="font-size: 78px; font-weight: 900; color: {status_color}; line-height: 1.0; margin: 10px 0;">
                {total_score} <span style="font-size: 26px; color: #6e7681; font-weight: 500;">/100</span>
            </div>
            <div style="font-size: 17px; font-weight: 700; color: {status_color};">
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
