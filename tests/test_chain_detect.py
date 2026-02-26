"""Tests for chain detection."""

from bot.services.chain_analyzer import detect_chain


def test_detect_ethereum():
    assert detect_chain("0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18") == "ethereum"


def test_detect_bitcoin_legacy():
    assert detect_chain("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") == "bitcoin"


def test_detect_bitcoin_segwit():
    assert detect_chain("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy") == "bitcoin"


def test_detect_bitcoin_bech32():
    assert detect_chain("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq") == "bitcoin"


def test_detect_tron():
    assert detect_chain("TN2YqTv5v7ATaA4PkCxQELzpSwKBe3RhSJ") == "tron"


def test_detect_solana():
    assert detect_chain("7EcDhSYGxXyscszYEp35KHN8vvw3svAuLKTzXwCFLtV") == "solana"


def test_detect_unknown():
    assert detect_chain("not-an-address") is None
    assert detect_chain("") is None
