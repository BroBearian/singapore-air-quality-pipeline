from collections import Counter
from datetime import UTC, datetime
from typing import Any

VALID_REGIONS = {"central", "north", "south", "east", "west"}


def make_result(
    run_id: str,
    rule_name: str,
    status: str,
    actual_value: str,
    expected_value: str,
    details: str,
) -> dict[str, str]:
    return {
        "run_id": run_id,
        "checked_at": datetime.now(UTC).isoformat(),
        "rule_name": rule_name,
        "status": status,
        "actual_value": actual_value,
        "expected_value": expected_value,
        "details": details,
    }


def run_quality_checks(
    rows: list[dict[str, Any]],
    run_id: str,
) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []

    regions = {row["region"] for row in rows}
    results.append(
        make_result(
            run_id,
            "valid_regions",
            "PASS" if regions.issubset(VALID_REGIONS) else "FAIL",
            ",".join(sorted(regions)),
            ",".join(sorted(VALID_REGIONS)),
            "Every region must be recognised.",
        )
    )

    bad_timestamps = 0
    for row in rows:
        try:
            observed_at = datetime.fromisoformat(row["observed_at"])
            published_at = datetime.fromisoformat(row["published_at"])
            if observed_at.tzinfo is None or published_at.tzinfo is None:
                bad_timestamps += 1
        except (KeyError, TypeError, ValueError):
            bad_timestamps += 1
    results.append(
        make_result(
            run_id,
            "timezone_aware_timestamps",
            "PASS" if bad_timestamps == 0 else "FAIL",
            str(bad_timestamps),
            "0",
            "Observation and publication timestamps must have UTC offsets.",
        )
    )

    negative_count = sum(row["value"] < 0 for row in rows)
    results.append(
        make_result(
            run_id,
            "non_negative_values",
            "PASS" if negative_count == 0 else "FAIL",
            str(negative_count),
            "0",
            "Measurements must not be negative.",
        )
    )

    keys = [
        (row["observed_at"], row["region"], row["metric"])
        for row in rows
    ]
    duplicate_count = len(keys) - len(set(keys))
    results.append(
        make_result(
            run_id,
            "batch_uniqueness",
            "PASS" if duplicate_count == 0 else "FAIL",
            str(duplicate_count),
            "0",
            "No duplicate timestamp-region-metric keys are allowed.",
        )
    )

    results.append(
        make_result(
            run_id,
            "non_empty_batch",
            "PASS" if rows else "FAIL",
            str(len(rows)),
            "> 0",
            "The extracted batch must contain records.",
        )
    )

    pm25_counts = Counter(
        row["observed_at"]
        for row in rows
        if row["metric"] == "pm25_one_hourly"
    )
    incomplete_hours = sum(count < 5 for count in pm25_counts.values())
    results.append(
        make_result(
            run_id,
            "pm25_regional_completeness",
            "PASS" if pm25_counts and incomplete_hours == 0 else "WARN",
            str(incomplete_hours),
            "0 incomplete hours",
            "Each PM2.5 observation normally contains five regions.",
        )
    )

    return results
