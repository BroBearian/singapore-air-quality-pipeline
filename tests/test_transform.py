import json
from pathlib import Path

from air_quality.transform import flatten_payload

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as file:
        return json.load(file)


def test_pm25_fixture_is_flattened() -> None:
    rows = flatten_payload(
        payload=load_fixture("pm25_sample.json"),
        endpoint_name="pm25",
        requested_date="2026-09-16",
        run_id="00000000-0000-0000-0000-000000000001",
    )

    assert rows
    assert all(row["metric"] == "pm25_one_hourly" for row in rows)
    assert {row["region"] for row in rows} == {
        "central",
        "north",
        "south",
        "east",
        "west",
    }


def test_psi_fixture_contains_expected_metrics() -> None:
    rows = flatten_payload(
        payload=load_fixture("psi_sample.json"),
        endpoint_name="psi",
        requested_date="2026-09-16",
        run_id="00000000-0000-0000-0000-000000000001",
    )

    metrics = {row["metric"] for row in rows}
    assert "psi_twenty_four_hourly" in metrics
    assert "pm25_twenty_four_hourly" in metrics
    assert "pm10_twenty_four_hourly" in metrics
