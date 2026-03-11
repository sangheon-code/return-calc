import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, date, time as dtime
from return_calc import Portfolio, Trade, TradeType, TradeStatus, Holdings, CashFlow

st.set_page_config(page_title="수익률 계산기", page_icon="📊", layout="wide")

# ── 세션 상태 초기화 ──
if "trades" not in st.session_state:
    st.session_state.trades = []
if "cash_flows" not in st.session_state:
    st.session_state.cash_flows = []
if "holdings" not in st.session_state:
    st.session_state.holdings = []
if "initial_asset" not in st.session_state:
    st.session_state.initial_asset = 1000.0
if "spot_buy" not in st.session_state:
    st.session_state.spot_buy = 0.0
if "spot_sell" not in st.session_state:
    st.session_state.spot_sell = 0.0


def build_portfolio() -> Portfolio:
    p = Portfolio(
        initial_asset=st.session_state.initial_asset,
        spot_buy_total=st.session_state.spot_buy,
        spot_sell_total=st.session_state.spot_sell,
    )
    for t in st.session_state.trades:
        p.add_trade(t)
    for cf in st.session_state.cash_flows:
        p.cash_flows.append(cf)
    if st.session_state.holdings:
        p.set_holdings(st.session_state.holdings)
    return p


# ── 사이드바: 데이터 입력 ──
with st.sidebar:
    st.header("⚙️ 설정")

    st.session_state.initial_asset = st.number_input(
        "초기 자산 (USDT)", value=st.session_state.initial_asset, min_value=0.0, step=100.0
    )

    col_sb1, col_sb2 = st.columns(2)
    with col_sb1:
        st.session_state.spot_buy = st.number_input("현물 매수 총액", value=st.session_state.spot_buy, min_value=0.0, step=10.0)
    with col_sb2:
        st.session_state.spot_sell = st.number_input("현물 매도 총액", value=st.session_state.spot_sell, min_value=0.0, step=10.0)

    # ── 거래 추가 ──
    st.divider()
    st.subheader("거래 추가")
    with st.form("trade_form", clear_on_submit=True):
        t_asset = st.text_input("자산명", placeholder="BTCUSDT")
        t_col1, t_col2 = st.columns(2)
        with t_col1:
            t_type = st.selectbox("포지션", ["LONG", "SHORT"])
            t_entry = st.number_input("평균 매수가", min_value=0.0, value=0.0, format="%f")
            t_qty = st.number_input("수량", min_value=0.0, value=0.0, format="%f")
            t_lev = st.number_input("레버리지", min_value=1, max_value=125, value=20)
        with t_col2:
            t_status = st.selectbox("상태", ["진행중 (OPEN)", "마감 (CLOSED)"])
            t_exit = st.number_input("평균 매도가", min_value=0.0, value=0.0, format="%f")
            t_entry_fee = st.number_input("매수 수수료 (USDT)", min_value=0.0, value=0.0, format="%f")
            t_exit_fee = st.number_input("매도 수수료 (USDT)", min_value=0.0, value=0.0, format="%f")

        t_date_col1, t_date_col2 = st.columns(2)
        with t_date_col1:
            t_entry_date = st.date_input("진입 날짜", value=date.today())
            t_entry_time = st.time_input("진입 시간", value=dtime(0, 0))
        with t_date_col2:
            t_exit_date = st.date_input("청산 날짜", value=date.today())
            t_exit_time = st.time_input("청산 시간", value=dtime(0, 0))

        submitted_trade = st.form_submit_button("✅ 거래 추가", use_container_width=True)
        if submitted_trade and t_asset and t_entry > 0 and t_qty > 0:
            is_closed = "CLOSED" in t_status
            entry_dt = datetime.combine(t_entry_date, t_entry_time)
            exit_dt = datetime.combine(t_exit_date, t_exit_time) if is_closed else None
            trade = Trade(
                asset=t_asset.upper(),
                trade_type=TradeType.LONG if t_type == "LONG" else TradeType.SHORT,
                entry_price=t_entry,
                quantity=t_qty,
                entry_time=entry_dt,
                leverage=t_lev,
                exit_price=t_exit if is_closed and t_exit > 0 else None,
                exit_time=exit_dt,
                entry_fee=t_entry_fee,
                exit_fee=t_exit_fee,
                status=TradeStatus.CLOSED if is_closed else TradeStatus.OPEN,
            )
            st.session_state.trades.append(trade)
            st.toast(f"✅ {t_asset} 거래 추가됨")

    # ── 입출금 추가 ──
    st.divider()
    st.subheader("입출금 추가")
    with st.form("cashflow_form", clear_on_submit=True):
        cf_type = st.selectbox("유형", ["입금", "출금"])
        cf_amount = st.number_input("금액 (USDT)", min_value=0.0, value=0.0, step=100.0)
        cf_date = st.date_input("날짜", value=date.today(), key="cf_date")
        cf_desc = st.text_input("메모", placeholder="선택사항")
        submitted_cf = st.form_submit_button("✅ 입출금 추가", use_container_width=True)
        if submitted_cf and cf_amount > 0:
            amt = cf_amount if cf_type == "입금" else -cf_amount
            st.session_state.cash_flows.append(
                CashFlow(amount=amt, timestamp=datetime.combine(cf_date, dtime(0, 0)), description=cf_desc)
            )
            st.toast(f"✅ {cf_type} ${cf_amount:,.2f} 추가됨")

    # ── 보유 자산 추가 ──
    st.divider()
    st.subheader("현재 보유 자산")
    with st.form("holdings_form", clear_on_submit=True):
        h_asset = st.text_input("자산명", placeholder="USDT, BTC, ETH...")
        h_col1, h_col2 = st.columns(2)
        with h_col1:
            h_amount = st.number_input("보유 수량", min_value=0.0, value=0.0, format="%f")
        with h_col2:
            h_value = st.number_input("USDT 환산 가치", min_value=0.0, value=0.0, format="%f")
        submitted_h = st.form_submit_button("✅ 자산 추가", use_container_width=True)
        if submitted_h and h_asset and h_value > 0:
            st.session_state.holdings.append(
                Holdings(asset=h_asset.upper(), amount=h_amount, value_usdt=h_value)
            )
            st.toast(f"✅ {h_asset} 자산 추가됨")

    # ── 초기화 ──
    st.divider()
    if st.button("🗑️ 전체 초기화", use_container_width=True):
        st.session_state.trades = []
        st.session_state.cash_flows = []
        st.session_state.holdings = []
        st.session_state.spot_buy = 0.0
        st.session_state.spot_sell = 0.0
        st.rerun()

    # ── 샘플 데이터 ──
    if st.button("📋 샘플 데이터 불러오기", use_container_width=True):
        st.session_state.initial_asset = 1000.0
        st.session_state.trades = [
            Trade("LAUSDT", TradeType.LONG, 0.223557, 8800, datetime(2025, 3, 7, 22, 24), 20, 0.244086, datetime(2025, 3, 11, 15, 42), 1.0, 1.0, TradeStatus.CLOSED),
            Trade("PEOPLEUSDT", TradeType.LONG, 0.0068461, 282800, datetime(2025, 3, 7, 22, 18), 20, 0.007556, datetime(2025, 3, 9, 22, 48), 1.0, 1.0, TradeStatus.CLOSED),
            Trade("TAOUSDT", TradeType.LONG, 182.5, 5.54, datetime(2025, 3, 7, 22, 19), 20, 193.8, datetime(2025, 3, 9, 12, 38), 0.25, 0.25, TradeStatus.CLOSED),
            Trade("LAUSDT", TradeType.LONG, 0.2281, 670, datetime(2025, 3, 7, 22, 19), 20, 0.2289, datetime(2025, 3, 7, 22, 25), 0.075, 0.075, TradeStatus.CLOSED),
            Trade("TRBUSDT", TradeType.LONG, 15.03, 132.6, datetime(2025, 3, 9, 20, 10), 20, entry_fee=1.0, exit_fee=1.0, status=TradeStatus.OPEN),
            Trade("BTCUSDT", TradeType.LONG, 87920.1, 0.0297, datetime(2025, 3, 7, 19, 51), 20, entry_fee=1.25, exit_fee=1.25, status=TradeStatus.OPEN),
        ]
        st.session_state.holdings = [
            Holdings("USDT", 791.37, 791.37),
            Holdings("BTC", 0.0297, 156.96),
            Holdings("TRB", 132.6, 136.70),
        ]
        st.session_state.cash_flows = []
        st.session_state.spot_buy = 0.0
        st.session_state.spot_sell = 0.0
        st.rerun()


# ── 메인 화면 ──
st.title("📊 수익률 계산기")

portfolio = build_portfolio()

# ── 상단 요약 카드 ──
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("총 자산", f"$ {portfolio.total_asset_value:,.2f}")
with c2:
    st.metric("순이익", f"$ {portfolio.net_profit:,.2f}", delta=f"{portfolio.return_pct:+.4f}%")
with c3:
    st.metric("총 실현 수익금", f"$ {portfolio.total_realized_pnl:,.2f}")
with c4:
    st.metric("총 수수료", f"$ {portfolio.total_fees:,.2f}")

st.divider()

# ── 자산 현황 ──
col_chart, col_stats = st.columns([3, 2])

with col_chart:
    st.subheader("자산현황")
    if portfolio.holdings:
        alloc = portfolio.asset_allocation
        fig = go.Figure(data=[go.Pie(
            labels=[a["asset"] for a in alloc],
            values=[a["value_usdt"] for a in alloc],
            hole=0.55,
            textinfo="label+percent",
            marker=dict(colors=["#4F8BF9", "#2E5CB8", "#7CB342", "#FF7043", "#AB47BC", "#26C6DA"]),
        )])
        fig.update_layout(
            annotations=[dict(text=f"${portfolio.total_asset_value:,.0f}", x=0.5, y=0.5, font_size=22, showarrow=False)],
            height=350, margin=dict(t=20, b=20, l=20, r=20),
            showlegend=True, legend=dict(orientation="h", y=-0.1),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("보유 자산을 입력하면 파이차트가 표시됩니다.")

with col_stats:
    st.subheader("거래 통계")
    stat_col1, stat_col2 = st.columns(2)
    with stat_col1:
        st.metric("수익", f"{portfolio.win_count} 건")
        st.metric("손실", f"{portfolio.loss_count} 건")
    with stat_col2:
        st.metric("승률", f"{portfolio.win_rate}%")
        st.metric("총 거래", f"{len(portfolio.closed_trades)} 건")

    st.divider()
    st.subheader("수익률 공식")
    st.markdown(f"""
    | 항목 | 값 |
    |---|---|
    | 초기 자산 | $ {portfolio.initial_asset:,.2f} |
    | 총 입금 | $ {portfolio.total_deposit:,.2f} |
    | 총 출금 | $ {portfolio.total_withdrawal:,.2f} |
    | 현재 자산 | $ {portfolio.total_asset_value:,.2f} |
    | 순이익 | $ {portfolio.net_profit:,.2f} |
    | **수익률** | **{portfolio.return_pct:+.4f}%** |
    """)

# 승률 프로그레스 바
if portfolio.closed_trades:
    st.progress(portfolio.win_rate / 100, text=f"승률 {portfolio.win_rate}%")

st.divider()

# ── 통합 타임라인 ──
st.subheader("타임라인 (시간순)")

timeline = portfolio.timeline()

if timeline:
    # 수익률 차트
    times = [ev["time"] for ev in timeline]
    returns = [ev["cum_return_pct"] for ev in timeline]
    fig_line = go.Figure(data=[go.Scatter(
        x=times, y=returns, mode="lines+markers",
        line=dict(color="#4F8BF9", width=2),
        marker=dict(size=6),
        hovertemplate="%{x}<br>수익률: %{y:.4f}%<extra></extra>",
    )])
    fig_line.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig_line.update_layout(
        height=250, margin=dict(t=10, b=30, l=50, r=20),
        yaxis_title="누적 수익률 (%)", xaxis_title="",
    )
    st.plotly_chart(fig_line, use_container_width=True)

    # 타임라인 테이블 + 삭제 버튼
    for row_idx, ev in enumerate(timeline):
        src = ev["source"]
        idx = ev["index"]
        ret_color = "green" if ev["cum_return_pct"] >= 0 else "red"
        ret_str = f"{ev['cum_return_pct']:+.4f}%"

        col_time, col_type, col_desc, col_amt, col_ret, col_del = st.columns([2, 1.2, 3, 1.5, 1.5, 0.8])

        with col_time:
            st.text(ev["time"].strftime("%m-%d %H:%M"))
        with col_type:
            if "마감" in ev["type"]:
                st.markdown(f":blue[{ev['type']}]")
            elif "진행" in ev["type"]:
                st.markdown(f":orange[{ev['type']}]")
            elif ev["type"] == "입금":
                st.markdown(f":green[{ev['type']}]")
            else:
                st.markdown(f":red[{ev['type']}]")
        with col_desc:
            desc = ev["desc"]
            if ev["detail"]:
                desc += f"  ({ev['detail']})"
            st.text(desc)
        with col_amt:
            if ev["source"] == "trade" and ev["amount"] != 0:
                st.text(f"${ev['amount']:+,.2f}")
            elif ev["source"] == "cashflow":
                st.text(f"${ev['amount']:+,.2f}")
            else:
                st.text("—")
        with col_ret:
            st.markdown(f":{ret_color}[{ret_str}]")
        with col_del:
            btn_key = f"del_{src}_{idx}_{row_idx}"
            if st.button("✕", key=btn_key, help="삭제"):
                if src == "trade":
                    st.session_state.trades.pop(idx)
                elif src == "cashflow":
                    st.session_state.cash_flows.pop(idx)
                st.rerun()
else:
    st.info("👈 사이드바에서 거래, 입출금, 보유 자산을 추가하거나 **샘플 데이터**를 불러오세요.")
