"""Tests for risk scoring heuristics."""

from datetime import datetime, timezone, timedelta

from bot.services.chains.base import AddressInfo
from bot.services.risk_scorer import compute_risk_score


def test_empty_address_low_risk():
    info = AddressInfo(
        address="0x1234",
        chain="ethereum",
        balance="1.5 ETH",
        tx_count=50,
        first_seen=datetime.now(timezone.utc) - timedelta(days=365),
        last_active=datetime.now(timezone.utc) - timedelta(days=1),
    )
    score, level, reasons = compute_risk_score(info)
    assert score < 25
    assert level == "low"


def test_new_address_higher_risk():
    info = AddressInfo(
        address="0x5678",
        chain="ethereum",
        balance="0 ETH",
        tx_count=200,
        first_seen=datetime.now(timezone.utc) - timedelta(days=2),
        last_active=datetime.now(timezone.utc),
    )
    score, level, reasons = compute_risk_score(info)
    assert score > 30
    assert any("new" in r.lower() or "Young" in r or "Very" in r for r in reasons)


def test_mixer_label_critical():
    info = AddressInfo(
        address="0xabcd",
        chain="ethereum",
        balance="0 ETH",
        tx_count=1000,
        first_seen=datetime.now(timezone.utc) - timedelta(days=30),
        last_active=datetime.now(timezone.utc),
        labels=["tornado-cash-mixer"],
    )
    score, level, reasons = compute_risk_score(info)
    assert score >= 50
    assert any("mixer" in r.lower() for r in reasons)


def test_error_returns_unknown():
    info = AddressInfo(address="bad", chain="unknown", error="Could not fetch")
    score, level, reasons = compute_risk_score(info)
    assert level == "unknown"
    assert score == 0


def test_zero_balance_high_tx():
    info = AddressInfo(
        address="0xdead",
        chain="ethereum",
        balance="0 ETH",
        tx_count=500,
        first_seen=datetime.now(timezone.utc) - timedelta(days=180),
        last_active=datetime.now(timezone.utc) - timedelta(days=10),
    )
    score, level, reasons = compute_risk_score(info)
    assert any("drain" in r.lower() for r in reasons)
