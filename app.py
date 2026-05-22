import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import FinanceDataReader as fdr
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def now_kst():
    return datetime.now(ZoneInfo("Asia/Seoul"))
import time

st.set_page_config(page_title="KOSPI 이격도 모니터", page_icon="📈", layout="wide")
st.title("📈 KOSPI 50일 이격도 모니터")

# --- 데이터 함수 ---
@st.cache_data(ttl=3600)
def get_historical(extra_days=100):
    today = datetime.today()
    start = (today - timedelta(days=extra_days + 100)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")
    df = fdr.DataReader("KS11", start, end)  # KS11 = KOSPI 지수
    df = df.rename(columns={"Close": "종가"})
    df["MA50"] = df["종가"].rolling(window=50).mean()
    df["이격도"] = (df["종가"] / df["MA50"] - 1) * 100
    return df.dropna()

def get_realtime_kospi():
    """장중 실시간 지수 (네이버 비공식)"""
    try:
        url = "https://polling.finance.naver.com/api/realtime/domestic/index/KOSPI"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=3)
        return float(r.json()["datas"][0]["nv"]) / 100
    except Exception:
        return None

def is_market_open():
    now = now_kst()
    if now.weekday() >= 5:
        return False
    t = now.hour * 60 + now.minute
    return 9 * 60 <= t <= 15 * 60 + 30

# --- 사이드바 ---
period = st.sidebar.selectbox("조회 기간 (일)", [30, 60, 90, 180, 365], index=2)
auto_refresh = st.sidebar.checkbox("자동 새로고침 (10초)", value=True)
st.sidebar.markdown("---")
st.sidebar.caption(f"마지막 갱신: {now_kst():%Y-%m-%d %H:%M:%S}")

# --- 데이터 로드 ---
df = get_historical(period)
df_view = df.tail(period).copy()

# 장중이면 마지막 종가를 실시간 값으로 교체
realtime = get_realtime_kospi() if is_market_open() else None
if realtime:
    df_view.loc[df_view.index[-1], "종가"] = realtime
    df_view.loc[df_view.index[-1], "이격도"] = (realtime / df_view["MA50"].iloc[-1] - 1) * 100

current_price = df_view["종가"].iloc[-1]
current_ma50 = df_view["MA50"].iloc[-1]
current_disp = df_view["이격도"].iloc[-1]

# --- 상단 지표 카드 ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("KOSPI 현재", f"{current_price:,.2f}")
col2.metric("50일 이동평균", f"{current_ma50:,.2f}")
col3.metric("이격도", f"{current_disp:+.2f}%")
col4.metric("시장 상태", "🟢 장중" if is_market_open() else "🔴 장 마감")

# --- 차트 (위/아래 두 칸 분리) ---
fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,         # x축 공유 (날짜)
    vertical_spacing=0.08,      # 두 그래프 사이 간격
    row_heights=[0.55, 0.45],     # 위 55%, 아래 45%
    subplot_titles=("KOSPI 지수 & 50일 이동평균", "이격도 (%)")
)

# 위쪽: KOSPI와 이동평균
fig.add_trace(go.Scatter(
    x=df_view.index, y=df_view["종가"],
    name="KOSPI", line=dict(color="#2563eb", width=2),
    hovertemplate="%{y:,.2f}<extra>KOSPI</extra>"
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=df_view.index, y=df_view["MA50"],
    name="50일 이동평균", line=dict(color="#f59e0b", width=2, dash="dash"),
    hovertemplate="%{y:,.2f}<extra>MA50</extra>"
), row=1, col=1)

# 현재 위치 별표
fig.add_trace(go.Scatter(
    x=[df_view.index[-1]], y=[current_price],
    mode="markers", name="현재",
    marker=dict(size=14, color="red", symbol="star",
                line=dict(width=1, color="white")),
    hovertemplate="현재: %{y:,.2f}<extra></extra>"
), row=1, col=1)

# 아래쪽: 이격도
fig.add_trace(go.Scatter(
    x=df_view.index, y=df_view["이격도"],
    name="이격도 (%)", line=dict(color="#10b981", width=1.5),
    fill="tozeroy", fillcolor="rgba(16, 185, 129, 0.15)",
    hovertemplate="%{y:+.2f}%<extra>이격도</extra>"
), row=2, col=1)

# 이격도 기준선
fig.add_hline(y=30, line=dict(color="black", width=2),
              annotation_text="+30%", annotation_position="right",
              row=2, col=1)
fig.add_hline(y=-30, line=dict(color="black", width=2),
              annotation_text="-30%", annotation_position="right",
              row=2, col=1)
fig.add_hline(y=0, line=dict(color="gray", width=1, dash="dot"),
              row=2, col=1)

fig.update_layout(
    height=800,
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
    margin=dict(l=20, r=20, t=60, b=20),
)
fig.update_yaxes(title_text="KOSPI 지수", row=1, col=1)
fig.update_yaxes(
    title_text="이격도 (%)",
    ticksuffix="%",
    range=[-35, 35],                          # 항상 ±35%까지 보이게
    tickvals=[-30, -20, -10, 0, 10, 20, 30],  # 눈금 위치 고정
    row=2, col=1
)
fig.update_xaxes(title_text="날짜", row=2, col=1)

st.plotly_chart(fig, use_container_width=True)

# --- 일별 데이터 표 ---
st.subheader("일별 데이터")
table_df = df_view[["종가", "MA50", "이격도"]].copy()
table_df = table_df.sort_index(ascending=False)  # 최근 날짜를 맨 위로
table_df.index = table_df.index.strftime("%Y-%m-%d")
table_df.index.name = "날짜"
table_df.columns = ["KOSPI 지수", "50일 이동평균", "이격도 (%)"]
table_df = table_df.round(2)
st.dataframe(table_df, use_container_width=True, height=(len(table_df) + 1) * 35 + 3)

# --- 자동 새로고침 ---
if auto_refresh and is_market_open():
    time.sleep(10)
    st.rerun()