"""
Risk and performance analysis of an equal-weighted portfolio of the
Big Five Canadian banks (NYSE listings), benchmarked against the S&P 500.

Metrics: annualized return and volatility, beta, CAPM alpha, Sharpe,
Sortino, Calmar and Treynor ratios, maximum drawdown, historical
Value at Risk (VaR) and Expected Shortfall (CVaR).
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
from pathlib import Path

# Setup

TICKERS = {
    "RY": "Royal Bank of Canada",
    "TD": "Toronto-Dominion Bank",
    "BMO": "Bank of Montreal",
    "BNS": "Scotiabank",
    "CM": "CIBC",
}
BENCHMARK = "^GSPC"            # S&P 500 index

START_DATE = "2025-01-01"
END_DATE = "2026-01-01"

WEIGHTS = np.full(len(TICKERS), 1 / len(TICKERS))   # equal distribution
PORTFOLIO_VALUE = 1_000_000    # for assumption, USD
RISK_FREE_RATE = 0.07          # annual
TRADING_DAYS = 252


# Data

def load_prices(tickers, start, end):
    """Download daily closing prices for one or more tickers."""
    prices = yf.download(tickers, start=start, end=end,
                         auto_adjust=True, progress=False)["Close"]
    return prices.dropna(how="all")

# Risk Metrics

def annualized_return(daily_returns):
    return (1 + daily_returns.mean()) ** TRADING_DAYS - 1


def annualized_volatility(daily_returns):
    return daily_returns.std() * np.sqrt(TRADING_DAYS)


def beta(portfolio, market):
    """Cov(Rp, Rm) / Var(Rm), using matching dates only."""
    aligned = pd.concat([portfolio, market], axis=1, join="inner").dropna()
    aligned.columns = ["portfolio", "market"]
    return aligned["portfolio"].cov(aligned["market"]) / aligned["market"].var()


def capm_alpha(portfolio, market, b, rf): # Jensen's Alpha, annualized
    rf_daily = rf / TRADING_DAYS
    excess_p = portfolio.mean() - rf_daily
    excess_m = market.mean() - rf_daily
    return (excess_p - b * excess_m) * TRADING_DAYS


def downside_deviation(daily_returns, target_annual):
    shortfall = np.minimum(daily_returns - target_annual / TRADING_DAYS, 0)
    return np.sqrt((shortfall ** 2).mean()) * np.sqrt(TRADING_DAYS)


def max_drawdown(daily_returns):
    wealth = (1 + daily_returns).cumprod()
    peak = wealth.cummax()
    return ((peak - wealth) / peak).max()


def historical_var(daily_returns, confidence, value):
    return -np.percentile(daily_returns, 100 * (1 - confidence)) * value


def expected_shortfall(daily_returns, confidence, value):
    cutoff = np.percentile(daily_returns, 100 * (1 - confidence))
    return -daily_returns[daily_returns <= cutoff].mean() * value


def compute_metrics(portfolio, market, rf):
    ann_ret = annualized_return(portfolio)
    ann_vol = annualized_volatility(portfolio)
    b = beta(portfolio, market)
    dd = downside_deviation(portfolio, rf)
    mdd = max_drawdown(portfolio)

    return {
        "Annual return": ann_ret,
        "Annual volatility": ann_vol,
        "Beta": b,
        "Alpha (CAPM)": capm_alpha(portfolio, market, b, rf),
        "Sharpe ratio": (ann_ret - rf) / ann_vol,
        "Sortino ratio": (ann_ret - rf) / dd,
        "Treynor ratio": (ann_ret - rf) / b,
        "Calmar ratio": ann_ret / mdd,
        "Downside deviation": dd,
        "Max drawdown": mdd,
        "VaR 90% (1-day)": historical_var(portfolio, 0.90, PORTFOLIO_VALUE),
        "VaR 95% (1-day)": historical_var(portfolio, 0.95, PORTFOLIO_VALUE),
        "VaR 99% (1-day)": historical_var(portfolio, 0.99, PORTFOLIO_VALUE),
        "CVaR 95% (1-day)": expected_shortfall(portfolio, 0.95, PORTFOLIO_VALUE),
    }

# Output

PERCENT_METRICS = {"Annual return", "Annual volatility", "Alpha (CAPM)",
                   "Downside deviation", "Max drawdown"}
DOLLAR_METRICS = {"VaR 90% (1-day)", "VaR 95% (1-day)",
                  "VaR 99% (1-day)", "CVaR 95% (1-day)"}


def print_report(metrics):
    width = 44
    print("\n" + "=" * width)
    print(" Big Five Canadian Banks: Risk Report")
    print(f" {START_DATE} to {END_DATE}, benchmark {BENCHMARK}")
    print(f" Risk-free rate {RISK_FREE_RATE:.1%}, "
          f"portfolio ${PORTFOLIO_VALUE:,.0f}")
    print("=" * width)

    for name, value in metrics.items():
        if name in PERCENT_METRICS:
            text = f"{value:.2%}"
        elif name in DOLLAR_METRICS:
            text = f"${value:,.0f}"
        else:
            text = f"{value:.3f}"
        print(f" {name:<26}{text:>16}")
    print("=" * width + "\n")


def plot_results(prices, portfolio, market):
    fig, (ax_price, ax_growth, ax_dd) = plt.subplots(
        3, 1, figsize=(12, 11), sharex=True,
        gridspec_kw={"height_ratios": [3, 3, 1.5]},
    )

    # Closing prices
    prices.rename(columns=TICKERS).plot(ax=ax_price, linewidth=1.4)
    ax_price.set_title("Closing Prices of the Big Five Canadian Banks")
    ax_price.set_ylabel("Price (USD)")
    ax_price.legend(loc="upper left", fontsize=9)

    # Growth of $1: portfolio vs benchmark
    growth_p = (1 + portfolio).cumprod()
    growth_m = (1 + market).cumprod()
    ax_growth.plot(growth_p, label="Equal-weighted bank portfolio", linewidth=1.8)
    ax_growth.plot(growth_m, label="S&P 500", linewidth=1.4, linestyle="--")
    ax_growth.axhline(1, color="grey", linewidth=0.8)
    ax_growth.set_title("Growth of $1")
    ax_growth.set_ylabel("Value (USD)")
    ax_growth.legend(loc="upper left", fontsize=9)

    # Drawdown
    drawdown = growth_p / growth_p.cummax() - 1
    ax_dd.fill_between(drawdown.index, drawdown, 0, color="tab:red", alpha=0.35)
    ax_dd.set_title("Portfolio Drawdown")
    ax_dd.set_ylabel("Drawdown")
    ax_dd.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
    ax_dd.set_xlabel("Date")

    for ax in (ax_price, ax_growth, ax_dd):
        ax.grid(alpha=0.3)

    fig.tight_layout()
    image_dir = Path(__file__).parent / "images"
    image_dir.mkdir(exist_ok=True)
    fig.savefig(image_dir / "risk_dashboard.png", dpi=150, bbox_inches="tight")
    plt.show()

def main():
    prices = load_prices(list(TICKERS), START_DATE, END_DATE)[list(TICKERS)]
    market = load_prices(BENCHMARK, START_DATE, END_DATE).squeeze()

    stock_returns = prices.pct_change().dropna()
    portfolio = stock_returns.dot(WEIGHTS)
    market_returns = market.pct_change().dropna()

    metrics = compute_metrics(portfolio, market_returns, RISK_FREE_RATE)
    print_report(metrics)
    plot_results(prices, portfolio, market_returns)


if __name__ == "__main__":
    main()