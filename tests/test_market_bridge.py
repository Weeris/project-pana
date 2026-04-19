import pytest
from src.engine.market_bridge import GlobalOrderBook, Order, AssetType, ContagionEngine


def test_order_book_match():
    book = GlobalOrderBook()
    # Seller posts carbon credit at $50
    seller = Order("agent-A", AssetType.CARBON_CREDIT, "sell", 10, 50.0, "EU")
    book.add_order(seller)
    # Buyer bids $55 — should match immediately
    buyer = Order("agent-B", AssetType.CARBON_CREDIT, "buy", 5, 55.0, "EU")
    result = book.add_order(buyer)
    assert result["matched"] is True
    assert result["price"] == 50.0


def test_no_match():
    book = GlobalOrderBook()
    book.add_order(Order("agent-A", AssetType.CARBON_CREDIT, "sell", 10, 80.0, "EU"))
    result = book.add_order(Order("agent-B", AssetType.CARBON_CREDIT, "buy", 5, 50.0, "EU"))
    assert result["matched"] is False


def test_contagion_engine_detects_cascade():
    engine = ContagionEngine()
    hits = sum(
        len(engine.detect_liquidation_cascade("bank-A", 0.25, ["bank-B"]))
        for _ in range(100)
    )
    # With 35% probability per run, we expect at least some hits across 100 runs
    assert hits > 0, "Cascade detection should fire probabilistically"


def test_liquidity_gap():
    engine = ContagionEngine()
    gap = engine.compute_liquidity_gap(cash=50, liabilities=200, asset_value=300)
    assert gap == 200 - (50 + 150)  # = 0


def test_liquidity_gap_positive():
    engine = ContagionEngine()
    gap = engine.compute_liquidity_gap(cash=10, liabilities=200, asset_value=100)
    assert gap == 200 - (10 + 50)  # = 140


def test_best_bid_ask():
    book = GlobalOrderBook()
    book.carbon_bids = [(45.0, 10), (44.0, 5)]
    book.carbon_asks = [(50.0, 8), (51.0, 3)]
    best_bid, best_ask = book.best_bid_ask(AssetType.CARBON_CREDIT)
    assert best_bid == 45.0
    assert best_ask == 50.0
