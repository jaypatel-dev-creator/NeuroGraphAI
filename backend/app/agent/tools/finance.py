import yfinance as yf
from langchain_core.tools import tool


@tool
def finance(ticker: str) -> str:
    """
    Get current stock price and basic info for a ticker symbol.
    Input must be a valid stock ticker symbol.
    Example: 'AAPL', 'GOOGL', 'TSLA', 'RELIANCE.NS'
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        price = info.get("currentPrice") or info.get("regularMarketPrice", "N/A")
        name = info.get("longName", ticker)
        currency = info.get("currency", "USD")
        change = info.get("regularMarketChangePercent", 0)
        direction = "▲" if change >= 0 else "▼"

        return (
            f"{name} ({ticker})\n"
            f"Price: {price} {currency}\n"
            f"Change: {direction} {abs(change):.2f}%"
        )
    except Exception as e:
        return f"Finance fetch error: {str(e)}"