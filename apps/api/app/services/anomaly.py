"""Conservative SUI movement outlier detection.

Rule amount-outlier-v2 (supersedes amount-outlier-v1):

* Separate baselines for incoming and outgoing movements. A wallet that receives
  small payments and sends large ones is not "unusual" every time it sends.
* Gas-only, failed and zero-net transactions are excluded. In v1 they counted as
  tiny outgoing movements, pulled the median and MAD towards zero, and made
  ordinary transfers look like outliers.
* The amount compared is the transfer amount with the sender's gas fee removed,
  when Tatum reports the fee.
* Robust z-score: (amount - median) / (1.4826 * MAD). The spread has a floor
  (5% of the median, at least 0.01 SUI) so a history of identical amounts does
  not produce a zero threshold.
* Only movements larger than usual are flagged. A large amount is a reason to
  look closer, never evidence of malicious activity.

Severity bands (robust z, roughly "standard deviations above typical"):
  medium: z >= 4   (under a normal model about 3 in 100,000 by chance)
  high:   z >= 12
Confidence is reported with the factors that produced it.
"""

from decimal import Decimal, InvalidOperation
from statistics import median
from typing import Any

RULE_VERSION = "amount-outlier-v2"
SOURCE = "tatum_sui_grpc"

MIN_BASELINE_SAMPLES = 10
MAD_SCALE = Decimal("1.4826")  # makes MAD comparable to a standard deviation for normal data
MEDIUM_Z = Decimal(4)
HIGH_Z = Decimal(12)
RELATIVE_SPREAD_FLOOR = Decimal("0.05")
MIN_THRESHOLD_SPREAD = Decimal("0.01")
EXCLUDED_KINDS = {"gas_only", "failed", "no_sui_change"}
DIRECTIONS = ("in", "out")


def _decimal(raw: Any) -> Decimal | None:
    if raw is None or isinstance(raw, bool) or not isinstance(raw, (str, int, float, Decimal)):
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
    return value if value.is_finite() else None


def _movement(tx: Any) -> tuple[str, Decimal] | None:
    """(direction, absolute transfer amount) for a baseline-eligible transaction, else None."""
    if not isinstance(tx, dict) or tx.get("activity_kind") in EXCLUDED_KINDS:
        return None
    raw = tx.get("transfer_amount_sui")
    value = _decimal(raw if raw is not None else tx.get("amount_sui"))
    if value is None or value == 0:
        return None
    direction = tx.get("direction")
    if direction not in DIRECTIONS:
        direction = "in" if value > 0 else "out"
    return direction, abs(value)


def _text(value: Decimal) -> str:
    text = format(value.normalize() if value != 0 else Decimal(0), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _sample_factor(n: int) -> float:
    """0.5 at the 10-sample minimum, approaching 1 as history grows."""
    return n / (n + MIN_BASELINE_SAMPLES)


def _direction_baseline(values: list[Decimal]) -> dict[str, Any]:
    n = len(values)
    if n < MIN_BASELINE_SAMPLES:
        return {
            "status": "thin_history",
            "sample_count": n,
            "minimum_sample_count": MIN_BASELINE_SAMPLES,
            "confidence": round(n / MIN_BASELINE_SAMPLES * 0.5, 2),
        }
    center = median(values)
    mad = median([abs(v - center) for v in values])
    spread = max(MAD_SCALE * mad, RELATIVE_SPREAD_FLOOR * center, MIN_THRESHOLD_SPREAD)
    return {
        "status": "established",
        "sample_count": n,
        "median_sui": _text(center),
        "median_absolute_deviation_sui": _text(mad),
        "robust_spread_sui": _text(spread),
        "spread_floor_applied": spread != MAD_SCALE * mad,
        "medium_threshold_sui": _text(center + MEDIUM_Z * spread),
        "high_threshold_sui": _text(center + HIGH_Z * spread),
        "confidence": round(_sample_factor(n), 2),
    }


class AnomalyDetectionService:
    """Median + MAD outlier detection with separate incoming and outgoing baselines."""

    def establish_baseline(self, transactions: list[dict[str, Any]]) -> dict[str, Any]:
        by_direction: dict[str, list[Decimal]] = {d: [] for d in DIRECTIONS}
        excluded = {kind: 0 for kind in sorted(EXCLUDED_KINDS)}
        uninterpretable = 0
        for tx in transactions:
            kind = tx.get("activity_kind") if isinstance(tx, dict) else None
            if kind in EXCLUDED_KINDS:
                excluded[kind] += 1
                continue
            movement = _movement(tx)
            if movement is None:
                uninterpretable += 1
                continue
            by_direction[movement[0]].append(movement[1])

        directions = {d: _direction_baseline(values) for d, values in by_direction.items()}
        established = [d for d in DIRECTIONS if directions[d]["status"] == "established"]
        sample_count = sum(len(v) for v in by_direction.values())
        return {
            "status": "established" if established else "thin_history",
            "method": "median_absolute_deviation",
            "rule_version": RULE_VERSION,
            "sample_count": sample_count,
            "minimum_sample_count": MIN_BASELINE_SAMPLES,
            "uninterpretable_count": uninterpretable,
            "excluded": excluded,
            "directions": directions,
            "assessed_directions": established,
            "confidence": max((directions[d]["confidence"] for d in DIRECTIONS), default=0.0),
        }

    def detect_anomalies(self, transactions: list[dict[str, Any]], baseline: dict[str, Any]) -> list[dict[str, Any]]:
        if baseline.get("status") != "established":
            return []
        directions = baseline.get("directions") or {}
        counterparty_counts: dict[str, int] = {}
        for tx in transactions:
            cp = tx.get("counterparty") if isinstance(tx, dict) else None
            if isinstance(cp, str):
                counterparty_counts[cp] = counterparty_counts.get(cp, 0) + 1

        findings = []
        for tx in transactions:
            movement = _movement(tx)
            digest = tx.get("digest") if isinstance(tx, dict) else None
            if movement is None or not isinstance(digest, str):
                continue
            direction, amount = movement
            stats = directions.get(direction) or {}
            if stats.get("status") != "established":
                continue
            center = Decimal(stats["median_sui"])
            spread = Decimal(stats["robust_spread_sui"])
            z = (amount - center) / spread
            if z < MEDIUM_Z:
                continue
            severity = "high" if z >= HIGH_Z else "medium"
            n = int(stats["sample_count"])
            sample_factor = _sample_factor(n)
            separation = min(1.0, float((z - MEDIUM_Z) / (HIGH_Z - MEDIUM_Z)))
            confidence = round(sample_factor * (0.5 + 0.5 * separation), 2)
            counterparty = tx.get("counterparty")
            seen = counterparty_counts.get(counterparty, 0) if isinstance(counterparty, str) else 0
            label = "outgoing" if direction == "out" else "incoming"
            threshold = Decimal(stats["medium_threshold_sui"])
            findings.append({
                "type": "unusual_sui_movement",
                "severity": severity,
                "amount_sui": _text(amount),
                "threshold_sui": _text(threshold),
                "baseline_median_sui": stats["median_sui"],
                "robust_z": round(float(z), 1),
                "transaction_digest": digest,
                "counterparty": counterparty,
                "counterparty_occurrences": seen,
                "direction": direction,
                "evidence": [{
                    "type": "transaction",
                    "ref": digest,
                    "source": SOURCE,
                    "timestamp": tx.get("timestamp_ms"),
                }],
                "confidence": confidence,
                "confidence_factors": [
                    f"{n} {label} transfers in the baseline (sample factor {sample_factor:.2f})",
                    f"{float(z):.1f} robust deviations above the typical {label} amount (separation {separation:.2f})",
                ],
                "rationale": (
                    f"This {label} movement of {_text(amount)} SUI is {float(z):.1f} robust deviations above this wallet's "
                    f"typical {label} amount of {stats['median_sui']} SUI (flag threshold {_text(threshold)} SUI, "
                    f"{n} transfers observed). This is an unusual-pattern signal, not evidence of malicious activity."
                ),
                "uncertainty": round(1 - confidence, 2),
                "rule_version": RULE_VERSION,
            })
        return findings


anomaly_service = AnomalyDetectionService()
