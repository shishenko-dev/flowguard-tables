"""Business-rule, duplicate and anomaly analysis for FlowGuard Tables."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import math
import re
import statistics
from time import perf_counter
from typing import Any, Iterable

from .classifier import IntentClassifier


PHONE_RE = re.compile(r"\D+")
EMAIL_RE = re.compile(r"\s+")
ACTIVE_STATUSES = {"new", "pending", "confirmed", "rescheduled"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def normalize_phone(value: Any) -> str:
    digits = PHONE_RE.sub("", _text(value))
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return digits


def normalize_email(value: Any) -> str:
    return EMAIL_RE.sub("", _text(value).lower())


def normalize_name(value: Any) -> str:
    return " ".join(_text(value).lower().split())


def parse_amount(value: Any) -> float | None:
    if value is None or value == "":
        return None
    cleaned = _text(value).replace(" ", "").replace(",", ".")
    try:
        amount = float(cleaned)
    except ValueError:
        return None
    return amount if math.isfinite(amount) else None


def parse_datetime(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _identity_key(record: dict[str, Any]) -> str:
    phone = normalize_phone(record.get("phone"))
    email = normalize_email(record.get("email"))
    name = normalize_name(record.get("client_name"))
    if phone:
        return f"phone:{phone}"
    if email:
        return f"email:{email}"
    if name:
        return f"name:{name}"
    return f"anonymous:{_text(record.get('id'))}"


def _stable_id(record: dict[str, Any], index: int) -> str:
    existing = _text(record.get("id"))
    if existing:
        return existing
    seed = "|".join(
        [
            _identity_key(record),
            _text(record.get("scheduled_at")),
            _text(record.get("service")),
            str(index),
        ]
    )
    return "FG-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8].upper()


def _amount_outliers(records: list[dict[str, Any]]) -> set[int]:
    values = [(index, parse_amount(record.get("amount"))) for index, record in enumerate(records)]
    numeric = [(index, value) for index, value in values if value is not None]
    if len(numeric) < 5:
        return set()
    sample = [value for _, value in numeric]
    median = statistics.median(sample)
    deviations = [abs(value - median) for value in sample]
    mad = statistics.median(deviations)
    if mad == 0:
        nonzero = [value for value in deviations if value > 0]
        if not nonzero:
            return set()
        mad = statistics.median(nonzero)
    return {
        index
        for index, value in numeric
        if 0.6745 * abs(value - median) / mad > 3.5
    }


def analyze_records(
    raw_records: Iterable[dict[str, Any]], classifier: IntentClassifier | None = None
) -> dict[str, Any]:
    started = perf_counter()
    classifier = classifier or IntentClassifier()
    records = [dict(record) for record in raw_records]
    if len(records) > 5_000:
        raise ValueError("A single run is limited to 5,000 records")

    identity_groups: dict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        identity_groups[_identity_key(record)].append(index)
    duplicate_indexes = {
        index for indexes in identity_groups.values() if len(indexes) > 1 for index in indexes
    }
    amount_outliers = _amount_outliers(records)

    results: list[dict[str, Any]] = []
    intent_counts: dict[str, int] = defaultdict(int)
    for index, record in enumerate(records):
        record_id = _stable_id(record, index)
        client_name = _text(record.get("client_name"))
        phone = normalize_phone(record.get("phone"))
        email = normalize_email(record.get("email"))
        status = _text(record.get("status")).lower() or "new"
        scheduled_at = parse_datetime(record.get("scheduled_at"))
        amount = parse_amount(record.get("amount"))
        prediction = classifier.predict(_text(record.get("notes")))
        intent_counts[prediction.label] += 1

        score = 0
        reasons: list[str] = []
        flags: list[str] = []

        if not client_name:
            score += 25
            reasons.append("Client name is missing")
            flags.append("missing_name")
        if not phone and not email:
            score += 30
            reasons.append("No valid contact channel")
            flags.append("missing_contact")
        if record.get("scheduled_at") and scheduled_at is None:
            score += 25
            reasons.append("Scheduled date cannot be parsed")
            flags.append("invalid_date")
        if index in duplicate_indexes:
            score += 22
            reasons.append("Possible repeat request for the same person")
            flags.append("duplicate")
        if index in amount_outliers:
            score += 24
            reasons.append("Amount is an unusual statistical outlier")
            flags.append("amount_outlier")
        if status == "cancelled" and amount and amount > 0:
            score += 18
            reasons.append("Cancelled record still contains a positive amount")
            flags.append("cancelled_with_amount")

        intent_weights = {
            "complaint": 28,
            "payment_issue": 24,
            "contact_problem": 20,
            "cancellation": 14,
            "reschedule": 12,
        }
        if prediction.confidence >= 0.34 and prediction.label in intent_weights:
            score += intent_weights[prediction.label]
            reasons.append(f"Note classified as {prediction.label.replace('_', ' ')}")
            flags.append(f"intent_{prediction.label}")
        if (
            prediction.label in {"cancellation", "reschedule"}
            and prediction.confidence >= 0.34
            and status in ACTIVE_STATUSES
        ):
            score += 12
            reasons.append("Structured status may conflict with the client note")
            flags.append("status_note_conflict")

        score = min(score, 100)
        if score >= 60:
            priority, action = "critical", "Review now"
        elif score >= 20:
            priority, action = "attention", "Check today"
        else:
            priority, action = "normal", "Monitor"

        results.append(
            {
                "id": record_id,
                "client_name": client_name or "Unknown client",
                "phone": phone,
                "email": email,
                "service": _text(record.get("service")) or "Unspecified",
                "scheduled_at": scheduled_at.isoformat() if scheduled_at else _text(record.get("scheduled_at")),
                "status": status,
                "amount": amount,
                "source": _text(record.get("source")) or "unknown",
                "owner": _text(record.get("owner")) or "unassigned",
                "notes": _text(record.get("notes")),
                "risk_score": score,
                "priority": priority,
                "recommended_action": action,
                "flags": flags,
                "reasons": reasons or ["No material issues detected"],
                "intent": prediction.as_dict(),
            }
        )

    results.sort(key=lambda row: (-row["risk_score"], row["id"]))
    duplicate_group_count = sum(1 for indexes in identity_groups.values() if len(indexes) > 1)
    attention_count = sum(row["priority"] != "normal" for row in results)
    critical_count = sum(row["priority"] == "critical" for row in results)
    anomaly_count = sum("amount_outlier" in row["flags"] for row in results)
    duration_ms = round((perf_counter() - started) * 1000, 2)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": len(results),
            "attention": attention_count,
            "critical": critical_count,
            "duplicate_groups": duplicate_group_count,
            "anomalies": anomaly_count,
            "processing_ms": duration_ms,
        },
        "intent_distribution": dict(sorted(intent_counts.items())),
        "records": results,
        "method": {
            "duplicate_detection": "normalised phone, email or client name",
            "anomaly_detection": "robust modified z-score using median absolute deviation",
            "note_classification": "local multinomial Naive Bayes model",
            "external_data_transfers": 0,
        },
    }
