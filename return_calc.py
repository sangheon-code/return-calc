"""
수익률 계산기 - 거래 기록 기반 포트폴리오 성과 분석

수익률 공식:
- 수익률(%) = (순이익 ÷ (초기 자산 + 총 입금)) x 100
- 순이익 = 현재 자산가치[미실현 손익 포함] - 초기 자산 - 총 입금 + 총 출금
- 총 입금 = 대회 기간 총 입금액 + 현물 매도액
- 총 출금 = 대회 기간 총 출금액 + 현물 매수액
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TradeType(Enum):
    LONG = "long"
    SHORT = "short"


class TradeStatus(Enum):
    OPEN = "open"      # 진행중인 거래
    CLOSED = "closed"  # 마감된 거래


@dataclass
class Trade:
    """개별 거래 기록"""
    asset: str                    # 거래 자산 (예: "BTCUSDT", "TRBUSDT")
    trade_type: TradeType         # long / short
    entry_price: float            # 평균 매수가
    quantity: float               # 수량
    entry_time: datetime          # 진입 시간
    leverage: int = 20            # 레버리지
    exit_price: Optional[float] = None   # 평균 매도가 (마감 시)
    exit_time: Optional[datetime] = None # 청산 시간
    entry_fee: float = 0.0        # 매수 수수료
    exit_fee: float = 0.0         # 매도 수수료
    status: TradeStatus = TradeStatus.OPEN

    @property
    def fee(self) -> float:
        """총 수수료 (매수 + 매도)"""
        return self.entry_fee + self.exit_fee

    @property
    def is_closed(self) -> bool:
        return self.status == TradeStatus.CLOSED

    @property
    def entry_value(self) -> float:
        """진입 금액 (레버리지 미적용 증거금 기준)"""
        return self.entry_price * self.quantity

    @property
    def pnl(self) -> float:
        """실현/미실현 손익 (수수료 제외)"""
        if self.is_closed and self.exit_price is not None:
            price_diff = self.exit_price - self.entry_price
        else:
            return 0.0  # 미실현 손익은 current_price로 별도 계산

        if self.trade_type == TradeType.SHORT:
            price_diff = -price_diff

        return price_diff * self.quantity

    @property
    def pnl_with_fee(self) -> float:
        """수수료 포함 순손익"""
        return self.pnl - self.fee

    @property
    def return_pct(self) -> float:
        """개별 거래 수익률 (%)"""
        if self.entry_value == 0:
            return 0.0
        margin = self.entry_value / self.leverage
        if margin == 0:
            return 0.0
        return (self.pnl_with_fee / margin) * 100


@dataclass
class CashFlow:
    """입출금 기록"""
    amount: float        # 금액 (양수: 입금, 음수: 출금)
    timestamp: datetime
    description: str = ""


@dataclass
class Holdings:
    """현재 보유 자산"""
    asset: str       # 예: "USDT", "BTC", "TRB"
    amount: float    # 보유 수량
    value_usdt: float  # USDT 환산 가치


@dataclass
class Portfolio:
    """포트폴리오 계산기"""
    initial_asset: float                         # 초기 자산 (USDT)
    trades: list[Trade] = field(default_factory=list)
    cash_flows: list[CashFlow] = field(default_factory=list)
    holdings: list[Holdings] = field(default_factory=list)
    # 현물 거래 (선물/현물 통합 계좌용)
    spot_buy_total: float = 0.0   # 현물 매수 총액
    spot_sell_total: float = 0.0  # 현물 매도 총액

    def add_trade(self, trade: Trade):
        self.trades.append(trade)

    def add_cash_flow(self, amount: float, timestamp: datetime, description: str = ""):
        self.cash_flows.append(CashFlow(amount=amount, timestamp=timestamp, description=description))

    def set_holdings(self, holdings: list[Holdings]):
        self.holdings = holdings

    # ── 입출금 집계 ──

    @property
    def total_deposit(self) -> float:
        """총 입금 = 대회 기간 총 입금액 + 현물 매도액"""
        deposits = sum(cf.amount for cf in self.cash_flows if cf.amount > 0)
        return deposits + self.spot_sell_total

    @property
    def total_withdrawal(self) -> float:
        """총 출금 = 대회 기간 총 출금액 + 현물 매수액"""
        withdrawals = sum(abs(cf.amount) for cf in self.cash_flows if cf.amount < 0)
        return withdrawals + self.spot_buy_total

    # ── 총 자산 ──

    @property
    def total_asset_value(self) -> float:
        """총 자산 (현재 보유 자산 USDT 환산 합계)"""
        if self.holdings:
            return sum(h.value_usdt for h in self.holdings)
        # holdings가 설정되지 않은 경우 거래 기반으로 추정
        return self.estimated_current_asset

    @property
    def estimated_current_asset(self) -> float:
        """거래 기록 기반 추정 현재 자산"""
        closed_pnl = sum(t.pnl_with_fee for t in self.trades if t.is_closed)
        total_fees = sum(t.fee for t in self.trades if not t.is_closed)
        net_cash = sum(cf.amount for cf in self.cash_flows)
        return self.initial_asset + closed_pnl - total_fees + net_cash

    # ── 자산 비율 (파이차트) ──

    @property
    def asset_allocation(self) -> list[dict]:
        """자산별 비율 (%) - 파이차트용"""
        total = self.total_asset_value
        if total == 0:
            return []
        result = []
        for h in self.holdings:
            result.append({
                "asset": h.asset,
                "value_usdt": h.value_usdt,
                "percentage": round((h.value_usdt / total) * 100, 2)
            })
        return sorted(result, key=lambda x: x["percentage"], reverse=True)

    # ── 마감 거래 통계 ──

    @property
    def closed_trades(self) -> list[Trade]:
        return [t for t in self.trades if t.is_closed]

    @property
    def open_trades(self) -> list[Trade]:
        return [t for t in self.trades if not t.is_closed]

    @property
    def total_realized_pnl(self) -> float:
        """총 실현 수익금"""
        return round(sum(t.pnl_with_fee for t in self.closed_trades), 2)

    @property
    def total_fees(self) -> float:
        """총 지불 수수료"""
        return round(sum(t.fee for t in self.trades), 2)

    @property
    def win_count(self) -> int:
        """수익 거래 수"""
        return sum(1 for t in self.closed_trades if t.pnl_with_fee > 0)

    @property
    def loss_count(self) -> int:
        """손실 거래 수"""
        return sum(1 for t in self.closed_trades if t.pnl_with_fee <= 0)

    @property
    def win_rate(self) -> float:
        """승률 (%)"""
        total = len(self.closed_trades)
        if total == 0:
            return 0.0
        return round((self.win_count / total) * 100, 1)

    # ── 수익률 (공식 기반) ──

    @property
    def net_profit(self) -> float:
        """순이익 = 현재 자산가치 - 초기 자산 - 총 입금 + 총 출금"""
        return self.total_asset_value - self.initial_asset - self.total_deposit + self.total_withdrawal

    @property
    def return_pct(self) -> float:
        """수익률(%) = (순이익 ÷ (초기 자산 + 총 입금)) x 100"""
        denominator = self.initial_asset + self.total_deposit
        if denominator == 0:
            return 0.0
        return round((self.net_profit / denominator) * 100, 4)

    # ── 타임라인 (시간순 이벤트 + 누적 수익률) ──

    def timeline(self) -> list[dict]:
        """거래와 입출금을 시간순으로 합치고 각 시점의 누적 수익률을 계산"""
        events: list[dict] = []

        for i, t in enumerate(self.trades):
            if t.is_closed and t.exit_time:
                events.append({
                    "time": t.exit_time,
                    "type": "거래(마감)",
                    "desc": f"{t.asset} {t.trade_type.value.upper()} {t.leverage}x",
                    "detail": f"매수 {t.entry_price:g} → 매도 {t.exit_price:g} / 수량 {t.quantity:g}",
                    "amount": t.pnl_with_fee,
                    "fee": t.fee,
                    "source": "trade",
                    "index": i,
                })
            else:
                events.append({
                    "time": t.entry_time,
                    "type": "거래(진행중)",
                    "desc": f"{t.asset} {t.trade_type.value.upper()} {t.leverage}x",
                    "detail": f"매수 {t.entry_price:g} / 수량 {t.quantity:g}",
                    "amount": 0.0,
                    "fee": t.fee,
                    "source": "trade",
                    "index": i,
                })

        for i, cf in enumerate(self.cash_flows):
            cf_type = "입금" if cf.amount > 0 else "출금"
            events.append({
                "time": cf.timestamp,
                "type": cf_type,
                "desc": cf.description or cf_type,
                "detail": "",
                "amount": cf.amount,
                "fee": 0.0,
                "source": "cashflow",
                "index": i,
            })

        events.sort(key=lambda e: e["time"])

        # 누적 수익률 계산: 각 이벤트 시점까지의 실현 PnL 기반
        cum_realized_pnl = 0.0
        cum_deposit = self.spot_sell_total   # 현물 매도액은 항상 포함
        cum_withdrawal = self.spot_buy_total  # 현물 매수액은 항상 포함
        cum_fees = 0.0

        for ev in events:
            if ev["source"] == "trade":
                t = self.trades[ev["index"]]
                if t.is_closed:
                    cum_realized_pnl += t.pnl
                cum_fees += t.fee
            elif ev["source"] == "cashflow":
                cf = self.cash_flows[ev["index"]]
                if cf.amount > 0:
                    cum_deposit += cf.amount
                else:
                    cum_withdrawal += abs(cf.amount)

            # 해당 시점 추정 자산 = 초기 + 누적실현PnL - 누적수수료 + 누적입금 - 누적출금
            est_asset = (self.initial_asset + cum_realized_pnl - cum_fees
                         + cum_deposit - cum_withdrawal)
            net_profit = est_asset - self.initial_asset - cum_deposit + cum_withdrawal
            denom = self.initial_asset + cum_deposit
            ret_pct = round((net_profit / denom) * 100, 4) if denom != 0 else 0.0

            ev["cum_return_pct"] = ret_pct
            ev["est_asset"] = round(est_asset, 2)

        return events

    # ── 최근 1개월 거래 요약 ──

    def recent_trades_summary(self, days: int = 30) -> dict:
        """최근 N일 거래 요약"""
        cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta
        cutoff = cutoff - timedelta(days=days)

        recent = [t for t in self.closed_trades
                  if t.exit_time and t.exit_time >= cutoff]

        pnl = sum(t.pnl_with_fee for t in recent)
        fees = sum(t.fee for t in recent)
        wins = sum(1 for t in recent if t.pnl_with_fee > 0)
        losses = sum(1 for t in recent if t.pnl_with_fee <= 0)
        total = len(recent)

        return {
            "총 실현 수익금": round(pnl, 2),
            "총 지불 수수료": round(-fees, 2),
            "수익": wins,
            "손실": losses,
            "승률": round((wins / total) * 100, 1) if total > 0 else 0.0,
        }

    # ── 전체 리포트 출력 ──

    def print_report(self):
        print("=" * 60)
        print("                    자산현황")
        print("=" * 60)

        print(f"\n  총 자산: $ {self.total_asset_value:,.2f}")
        print(f"  원화: ₩ {self.total_asset_value * 1388:,.0f}")  # 대략적 환율

        # 자산 비율
        if self.holdings:
            print(f"\n  {'자산':<10} {'비율':>10}")
            print("  " + "-" * 25)
            for alloc in self.asset_allocation:
                print(f"  {alloc['asset']:<10} {alloc['percentage']:>9.2f} %")

        # 수익률
        print(f"\n  누적 수익률: {self.return_pct:+.2f} %")
        print(f"  순이익: $ {self.net_profit:,.2f}")

        # 최근 거래 요약
        print(f"\n{'=' * 60}")
        print("                  최근 1개월 거래")
        print("=" * 60)
        summary = self.recent_trades_summary()
        print(f"  총 실현 수익금: $ {summary['총 실현 수익금']:,.1f}")
        print(f"  총 지불 수수료: $ {summary['총 지불 수수료']:,.1f}")
        print(f"  수익: {summary['수익']} 건")
        print(f"  손실: {summary['손실']} 건")
        print(f"  승률: {summary['승률']:.1f}%")

        # 진행중인 거래
        if self.open_trades:
            print(f"\n{'=' * 60}")
            print("                   진행중인 거래")
            print("=" * 60)
            print(f"  {'거래일':<18} {'자산':<12} {'평균매수가':>12} {'수량':>10} {'수익금':>10}")
            print("  " + "-" * 62)
            for t in self.open_trades:
                print(f"  {t.entry_time.strftime('%m-%d %H:%M'):<18} "
                      f"{t.asset:<12} "
                      f"{t.entry_price:>12,.2f} "
                      f"{t.quantity:>10,.4f} "
                      f"{'--':>10}")
                print(f"  {'':18} {t.leverage}x {'':>12} {'':>10} {'':>10}")

        # 마감된 거래
        if self.closed_trades:
            print(f"\n{'=' * 60}")
            print("                    마감된 거래")
            print("=" * 60)
            print(f"  {'기간':<28} {'자산':<12} {'매수가':>10} {'매도가':>10} {'수익금':>10} {'수익률':>8}")
            print("  " + "-" * 80)
            for t in self.closed_trades:
                period = ""
                if t.entry_time and t.exit_time:
                    period = f"{t.entry_time.strftime('%m-%d %H:%M')} ~ {t.exit_time.strftime('%m-%d %H:%M')}"
                pnl_str = f"${t.pnl_with_fee:,.2f}"
                ret_str = f"{t.return_pct:+.2f}%"
                print(f"  {period:<28} "
                      f"{t.asset:<12} "
                      f"{t.entry_price:>10,.4f} "
                      f"{t.exit_price:>10,.4f} "
                      f"{pnl_str:>10} "
                      f"{ret_str:>8}")
                print(f"  {'':28} {t.leverage}x {'':>10} {t.quantity:>10,.2f} {'':>10} {'':>8}")

        print(f"\n{'=' * 60}")


# ── 사용 예시: 이미지 데이터 재현 ──

if __name__ == "__main__":
    portfolio = Portfolio(initial_asset=1000.0)

    # === 마감된 거래 (마감된 거래 섹션) ===

    # LAUSDT (03-07 22:24 ~ 03-11 15:42) - $203.5 / 206.96%
    portfolio.add_trade(Trade(
        asset="LAUSDT",
        trade_type=TradeType.LONG,
        entry_price=0.223557,
        quantity=8800,
        exit_price=0.244086,
        entry_time=datetime(2025, 3, 7, 22, 24),
        exit_time=datetime(2025, 3, 11, 15, 42),
        leverage=20,
        entry_fee=1.0,
        exit_fee=1.0,
        status=TradeStatus.CLOSED,
    ))

    # PEOPLEUSDT (03-07 22:18 ~ 03-09 22:48) - $199.4 / 208.11%
    portfolio.add_trade(Trade(
        asset="PEOPLEUSDT",
        trade_type=TradeType.LONG,
        entry_price=0.0068461,
        quantity=282800,
        exit_price=0.007556,
        entry_time=datetime(2025, 3, 7, 22, 18),
        exit_time=datetime(2025, 3, 9, 22, 48),
        leverage=20,
        entry_fee=1.0,
        exit_fee=1.0,
        status=TradeStatus.CLOSED,
    ))

    # TAOUSDT (03-07 22:19 ~ 03-09 12:38) - $69.01 / 129.68%
    portfolio.add_trade(Trade(
        asset="TAOUSDT",
        trade_type=TradeType.LONG,
        entry_price=182.5,
        quantity=5.54,
        exit_price=193.8,
        entry_time=datetime(2025, 3, 7, 22, 19),
        exit_time=datetime(2025, 3, 9, 12, 38),
        leverage=20,
        entry_fee=0.25,
        exit_fee=0.25,
        status=TradeStatus.CLOSED,
    ))

    # LAUSDT (03-07 22:19 ~ 03-07 22:25) - $0.38 / 5.01%
    portfolio.add_trade(Trade(
        asset="LAUSDT",
        trade_type=TradeType.LONG,
        entry_price=0.2281,
        quantity=670,
        exit_price=0.2289,
        entry_time=datetime(2025, 3, 7, 22, 19),
        exit_time=datetime(2025, 3, 7, 22, 25),
        leverage=20,
        entry_fee=0.075,
        exit_fee=0.075,
        status=TradeStatus.CLOSED,
    ))

    # === 진행중인 거래 ===

    # TRBUSDT (03-09 20:10) - 평균매수가 15.03, 수량 132.6
    portfolio.add_trade(Trade(
        asset="TRBUSDT",
        trade_type=TradeType.LONG,
        entry_price=15.03,
        quantity=132.6,
        entry_time=datetime(2025, 3, 9, 20, 10),
        leverage=20,
        entry_fee=1.0,
        exit_fee=1.0,
        status=TradeStatus.OPEN,
    ))

    # BTCUSDT (03-07 19:51) - 평균매수가 87920.1, 수량 0.0297
    portfolio.add_trade(Trade(
        asset="BTCUSDT",
        trade_type=TradeType.LONG,
        entry_price=87920.1,
        quantity=0.0297,
        entry_time=datetime(2025, 3, 7, 19, 51),
        leverage=20,
        entry_fee=1.25,
        exit_fee=1.25,
        status=TradeStatus.OPEN,
    ))

    # === 현재 보유 자산 (파이차트 데이터) ===
    portfolio.set_holdings([
        Holdings(asset="USDT", amount=791.37, value_usdt=791.37),
        Holdings(asset="BTC", amount=0.0297, value_usdt=156.96),
        Holdings(asset="TRB", amount=132.6, value_usdt=136.70),
    ])

    # === 리포트 출력 ===
    portfolio.print_report()

    # === 수익률 공식 검증 예시 ===
    print("\n\n" + "=" * 60)
    print("          수익률 공식 검증 (문서 예시)")
    print("=" * 60)

    # 예시 1: 초기 1000, 100 수익 → 10%
    p1 = Portfolio(initial_asset=1000)
    p1.set_holdings([Holdings("USDT", 1100, 1100)])
    print(f"\n1. 초기 1000, 100 수익 → 자산 1100")
    print(f"   수익률: {p1.return_pct}% (기대: 10.00%)")

    # 예시 2: 100 출금 → 자산 1000, 여전히 10%
    p2 = Portfolio(initial_asset=1000)
    p2.add_cash_flow(-100, datetime.now(), "출금")
    p2.set_holdings([Holdings("USDT", 1000, 1000)])
    print(f"\n2. +100 수익 후 100 출금 → 자산 1000")
    print(f"   수익률: {p2.return_pct}% (기대: 10.00%)")

    # 예시 3: 300 손실 → 자산 700
    p3 = Portfolio(initial_asset=1000)
    p3.add_cash_flow(-100, datetime.now(), "출금")
    p3.set_holdings([Holdings("USDT", 700, 700)])
    print(f"\n3. 300 손실 → 자산 700")
    print(f"   수익률: {p3.return_pct}% (기대: -20.00%)")

    # 예시 4: 300 입금 → 자산 1000
    p4 = Portfolio(initial_asset=1000)
    p4.add_cash_flow(-100, datetime.now(), "출금")
    p4.add_cash_flow(300, datetime.now(), "입금")
    p4.set_holdings([Holdings("USDT", 1000, 1000)])
    print(f"\n4. 300 입금 → 자산 1000")
    print(f"   수익률: {p4.return_pct}% (기대: -15.38%)")

    # 예시 5: 1000 수익 → 자산 2000
    p5 = Portfolio(initial_asset=1000)
    p5.add_cash_flow(-100, datetime.now(), "출금")
    p5.add_cash_flow(300, datetime.now(), "입금")
    p5.set_holdings([Holdings("USDT", 2000, 2000)])
    print(f"\n5. 1000 수익 → 자산 2000")
    print(f"   수익률: {p5.return_pct}% (기대: 61.54%)")
