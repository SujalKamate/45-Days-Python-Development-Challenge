# Digital Asset Portfolio Tracker with Profit-Loss Analysis

from datetime import date

portfolio  = {}
transactions = []
_tid = 1

ASSETS = {
    "BTC":  "Bitcoin",      "ETH":  "Ethereum",
    "BNB":  "BNB",          "SOL":  "Solana",
    "ADA":  "Cardano",      "XRP":  "Ripple",
    "DOGE": "Dogecoin",     "MATIC":"Polygon",
    "INFY": "Infosys",      "TCS":  "TCS",
    "RELIANCE":"Reliance",  "GOLD": "Gold (per 10g)",
}

def buy_asset(symbol, qty, buy_price, buy_date=None):
    global _tid
    if symbol not in ASSETS: print(f"  Unknown symbol '{symbol}'."); return None
    d = buy_date or date.today()
    tid = f"TXN{_tid:05d}"; _tid += 1
    cost = round(qty * buy_price, 2)
    if symbol not in portfolio:
        portfolio[symbol] = {"name":ASSETS[symbol],"qty":0,"avg_cost":0,"total_invested":0}
    p = portfolio[symbol]
    new_total = p["total_invested"] + cost
    new_qty   = p["qty"] + qty
    p["avg_cost"]       = round(new_total / new_qty, 2)
    p["qty"]            = round(new_qty, 6)
    p["total_invested"] = round(new_total, 2)
    transactions.append({"tid":tid,"type":"BUY","symbol":symbol,"qty":qty,
                         "price":buy_price,"total":cost,"date":d})
    print(f"  [{tid}] BUY  {qty} {symbol} @ Rs.{buy_price:,} = Rs.{cost:,} | Avg: Rs.{p['avg_cost']:,}")
    return tid

def sell_asset(symbol, qty, sell_price, sell_date=None):
    global _tid
    if symbol not in portfolio: print(f"  No holdings in {symbol}."); return None
    p = portfolio[symbol]
    if p["qty"] < qty: print(f"  Insufficient qty. Have {p['qty']} {symbol}."); return None
    d   = sell_date or date.today()
    tid = f"TXN{_tid:05d}"; _tid += 1
    proceeds  = round(qty * sell_price, 2)
    cost_basis= round(qty * p["avg_cost"], 2)
    pl        = round(proceeds - cost_basis, 2)
    pl_pct    = round(pl / cost_basis * 100, 2) if cost_basis else 0
    p["qty"]            = round(p["qty"] - qty, 6)
    p["total_invested"] = round(p["total_invested"] - cost_basis, 2)
    transactions.append({"tid":tid,"type":"SELL","symbol":symbol,"qty":qty,
                         "price":sell_price,"total":proceeds,"pl":pl,"date":d})
    status = "✔ PROFIT" if pl >= 0 else "✗ LOSS"
    print(f"  [{tid}] SELL {qty} {symbol} @ Rs.{sell_price:,} = Rs.{proceeds:,} | P/L: Rs.{pl:,} ({pl_pct}%) {status}")
    return tid

def update_prices(current_prices):
    print("\n  Portfolio Valuation:")
    total_invested = 0; total_current = 0
    for symbol, price in current_prices.items():
        if symbol in portfolio and portfolio[symbol]["qty"] > 0:
            p = portfolio[symbol]
            current_val = round(p["qty"] * price, 2)
            invested    = p["total_invested"]
            pl          = round(current_val - invested, 2)
            pl_pct      = round(pl / invested * 100, 2) if invested else 0
            sign        = "▲" if pl >= 0 else "▼"
            print(f"  {symbol:<8} {p['qty']:>10.4f} | Avg:Rs.{p['avg_cost']:>10,} | "
                  f"Now:Rs.{price:>10,} | {sign} Rs.{pl:>10,} ({pl_pct}%)")
            total_invested += invested; total_current += current_val
    total_pl  = round(total_current - total_invested, 2)
    total_pct = round(total_pl / total_invested * 100, 2) if total_invested else 0
    print(f"\n  Invested : Rs.{total_invested:,.2f}")
    print(f"  Current  : Rs.{total_current:,.2f}")
    sign = "▲" if total_pl >= 0 else "▼"
    print(f"  Total P/L: {sign} Rs.{total_pl:,.2f} ({total_pct}%)")

def transaction_history():
    print(f"\n  Transaction History:")
    print(f"  {'TID':<10} {'Type':<5} {'Symbol':<8} {'Qty':>8} {'Price':>12} {'Total':>12}")
    for t in transactions:
        print(f"  {t['tid']:<10} {t['type']:<5} {t['symbol']:<8} {t['qty']:>8.4f} "
              f"Rs.{t['price']:>10,} Rs.{t['total']:>10,}")

def profit_loss_summary():
    sell_txns = [t for t in transactions if t["type"] == "SELL"]
    if not sell_txns: print("  No sell transactions yet."); return
    realized  = sum(t["pl"] for t in sell_txns)
    winners   = [t for t in sell_txns if t["pl"] > 0]
    losers    = [t for t in sell_txns if t["pl"] < 0]
    print(f"\n{'='*50}\n  PROFIT / LOSS SUMMARY\n{'='*50}")
    print(f"  Realized P/L   : Rs.{realized:,}")
    print(f"  Winning Trades : {len(winners)}")
    print(f"  Losing Trades  : {len(losers)}")
    if winners:
        best = max(winners, key=lambda x: x["pl"])
        print(f"  Best Trade     : {best['symbol']} Rs.{best['pl']:,}")
    if losers:
        worst = min(losers, key=lambda x: x["pl"])
        print(f"  Worst Trade    : {worst['symbol']} Rs.{worst['pl']:,}")
    print(f"{'='*50}")

def main():
    print("=== Digital Asset Portfolio Tracker ===")
    buy_asset("BTC",   0.05,  4200000)
    buy_asset("ETH",   0.5,    250000)
    buy_asset("SOL",   10,      9500)
    buy_asset("INFY",  50,     1800)
    buy_asset("TCS",   20,     4100)
    buy_asset("GOLD",  2,      72000)
    buy_asset("BTC",   0.02,  4500000)
    sell_asset("SOL",  5,      12000)
    sell_asset("ETH",  0.2,   280000)
    sell_asset("INFY", 20,     1650)
    current_prices = {
        "BTC":4800000,"ETH":260000,"SOL":11500,
        "INFY":1900,"TCS":4300,"GOLD":75000,
    }
    update_prices(current_prices)
    transaction_history()
    profit_loss_summary()

if __name__ == "__main__":
    main()
