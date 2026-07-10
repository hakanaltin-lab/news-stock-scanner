"""
V3 Market Intelligence Scanner

Main execution layer
"""

from scanner_core import MarketScanner


def load_demo_market():

    return [
        {
            "ticker": "NVDA",
            "news": 90,
            "sector": 95,
            "price": 88,
            "quality": 92,
            "risk": 15
        },
        {
            "ticker": "AMD",
            "news": 75,
            "sector": 90,
            "price": 80,
            "quality": 85,
            "risk": 20
        },
        {
            "ticker": "TSLA",
            "news": 70,
            "sector": 65,
            "price": 72,
            "quality": 70,
            "risk": 35
        }
    ]


def main():

    scanner = MarketScanner()

    stocks = load_demo_market()

    ranking = scanner.rank_market(stocks)

    print("\nV3 TOP OPPORTUNITIES\n")

    for stock in ranking:
        print(
            stock["ticker"],
            "Alpha:",
            stock["alpha_score"],
            "Risk:",
            stock["risk_score"]
        )


if __name__ == "__main__":
    main()
