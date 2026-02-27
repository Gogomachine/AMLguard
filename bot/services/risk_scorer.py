"""
Heuristic risk scoring based on on-chain data.
Provides a preliminary score before AI analysis refines it.
"""

from datetime import datetime, timezone

from bot.services.chains.base import AddressInfo


def compute_risk_score(info: AddressInfo) -> tuple[float, str, list[str]]:
    """
    Compute a risk score (0-100) based on on-chain heuristics.

    Returns: (score, risk_level, reasons)
    """
    score = 0.0
    reasons: list[str] = []

    if info.error:
        return 0.0, "unknown", ["Could not fetch data for analysis"]

    # --- Age analysis ---
    if info.first_seen:
        age_days = (datetime.now(timezone.utc) - info.first_seen).days
        if age_days < 7:
            score += 25
            reasons.append(f"Very new address ({age_days}d old)")
        elif age_days < 30:
            score += 15
            reasons.append(f"Young address ({age_days}d old)")
        elif age_days < 90:
            score += 5
    else:
        score += 10
        reasons.append("Unable to determine address age")

    # --- Activity patterns ---
    if info.tx_count == 0:
        score += 5
        reasons.append("No transactions found")
    elif info.tx_count > 10000:
        score += 15
        reasons.append(f"Extremely high tx count ({info.tx_count:,})")

    # --- Dormancy ---
    if info.last_active:
        dormant_days = (datetime.now(timezone.utc) - info.last_active).days
        if dormant_days > 365:
            score += 10
            reasons.append(f"Dormant for {dormant_days}d — sudden reactivation is suspicious")

    # --- Contract flag ---
    if info.is_contract:
        score += 5
        reasons.append("Address is a smart contract")

    # --- Balance anomalies ---
    # Parse numeric balance
    try:
        balance_num = float(info.balance.split()[0])
        if balance_num == 0 and info.tx_count and info.tx_count > 100:
            score += 20
            reasons.append("Zero balance with high tx history — possible drain")
    except (ValueError, IndexError):
        pass

    # --- Name tag from explorer ---
    if info.name_tag:
        tag_lower = info.name_tag.lower()
        for keyword in ("phish", "hack", "exploit", "scam", "steal", "heist", "fake"):
            if keyword in tag_lower:
                score += 50
                reasons.append(f"Explorer label: {info.name_tag}")
                break
        for keyword in ("tornado", "mixer"):
            if keyword in tag_lower:
                score += 40
                reasons.append(f"Explorer label: {info.name_tag}")
                break

    # --- Counterparty analysis ---
    if info.counterparties:
        risky_count = len(info.counterparties)
        score += min(30, risky_count * 15)
        reasons.append(
            f"Interacted with {risky_count} flagged address(es): "
            + "; ".join(info.counterparties[:3])
        )

    # --- Labels ---
    for label in info.labels:
        if "mixer" in label.lower() or "tornado" in label.lower():
            score += 40
            reasons.append(f"Known mixer/tumbler label: {label}")
        elif "exchange" in label.lower():
            score -= 5  # Exchanges are generally lower risk
        elif "scam" in label.lower() or "phishing" in label.lower():
            score += 50
            reasons.append(f"Flagged: {label}")

    # Clamp
    score = max(0.0, min(100.0, score))

    # Determine level
    if score < 25:
        level = "low"
    elif score < 50:
        level = "medium"
    elif score < 75:
        level = "high"
    else:
        level = "critical"

    return score, level, reasons
