from air_quality.quality import run_quality_checks


def sample_row(region: str = "central") -> dict:
    return {
        "observed_at": "2026-09-16T11:00:00+08:00",
        "published_at": "2026-09-16T11:45:45+08:00",
        "region": region,
        "metric": "pm25_one_hourly",
        "value": 26,
    }


def test_negative_values_fail_quality_check() -> None:
    row = sample_row()
    row["value"] = -1
    rows = [row]

    results = run_quality_checks(
        rows,
        "00000000-0000-0000-0000-000000000001",
    )
    result_by_name = {result["rule_name"]: result for result in results}

    assert result_by_name["non_negative_values"]["status"] == "FAIL"


def test_partial_region_is_warning_and_duplicates_fail() -> None:
    row = sample_row()
    results = run_quality_checks([row], "test-run")
    by_rule = {result["rule_name"]: result for result in results}
    assert by_rule["pm25_regional_completeness"]["status"] == "WARN"

    results = run_quality_checks([row, row.copy()], "test-run")
    by_rule = {result["rule_name"]: result for result in results}
    assert by_rule["batch_uniqueness"]["status"] == "FAIL"


def test_naive_timestamp_fails() -> None:
    row = sample_row()
    row["observed_at"] = "2026-09-16T11:00:00"
    results = run_quality_checks([row], "test-run")
    by_rule = {result["rule_name"]: result for result in results}
    assert by_rule["timezone_aware_timestamps"]["status"] == "FAIL"
