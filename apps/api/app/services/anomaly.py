from decimal import Decimal, InvalidOperation
from statistics import median
from typing import Any

MIN_BASELINE_SAMPLES = 10
RULE_VERSION = "amount-outlier-v1"
MIN_THRESHOLD_SPREAD = Decimal("0.01")
SOURCE = "tatum_sui_grpc"


def _amount(tx: Any) -> Decimal | None:
    """Absolute SUI movement as an exact Decimal, or None when not interpretable."""
    if not isinstance(tx, dict):
        return None
    raw = tx.get("amount_sui")
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
    return abs(value) if value.is_finite() else None


def _text(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


class AnomalyDetectionService:
    """Conservative SUI movement outlier detection (median + MAD) over normalized activity."""

    def establish_baseline(self, transactions: list[dict[str, Any]]) -> dict[str, Any]:
        observations = [value for value in (_amount(tx) for tx in transactions) if value is not None]
        if len(observations) < MIN_BASELINE_SAMPLES:
            return {
                "status": "thin_history",
                "confidence": round(len(observations) / MIN_BASELINE_SAMPLES, 2),
                "sample_count": len(observations),
                "minimum_sample_count": MIN_BASELINE_SAMPLES,
            }
        center = median(observations)
        mad = median([abs(value - center) for value in observations])
        return {
            "status": "established",
            "method": "median_absolute_deviation",
            "median_net_sui_movement": _text(center),
            "median_absolute_deviation": _text(mad),
            "sample_count": len(observations),
            "confidence": round(min(1.0, len(observations) / 50), 2),
        }

    def detect_anomalies(self, transactions: list[dict[str, Any]], baseline: dict[str, Any]) -> list[dict[str, Any]]:
        if baseline.get("status") != "established":
            return []
        center = Decimal(str(baseline["median_net_sui_movement"]))
        mad = Decimal(str(baseline["median_absolute_deviation"]))
        threshold = center + max(6 * mad, MIN_THRESHOLD_SPREAD)
        findings = []
        for tx in transactions:
            movement = _amount(tx)
            digest = tx.get("digest") if isinstance(tx, dict) else None
            if movement is None or movement <= threshold or not isinstance(digest, str):
                continue
            findings.append({
                "type": "unusual_sui_movement",
                "severity": "high" if movement >= threshold * 10 else "medium",
                "amount_sui": _text(movement),
                "threshold_sui": _text(threshold),
                "transaction_digest": digest,
                "counterparty": tx.get("counterparty"),
                "direction": tx.get("direction"),
                "evidence": [{
                    "type": "transaction",
                    "ref": digest,
                    "source": SOURCE,
                    "timestamp": tx.get("timestamp_ms"),
                }],
                "rationale": (
                    f"Net SUI movement of {_text(movement)} SUI exceeded the observed-history threshold "
                    f"of {_text(threshold)} SUI. This is an unusual-pattern signal, not evidence of malicious activity."
                ),
                "uncertainty": round(1 - float(baseline["confidence"]), 2),
                "rule_version": RULE_VERSION,
            })
        return findings


anomaly_service = AnomalyDetectionService()
