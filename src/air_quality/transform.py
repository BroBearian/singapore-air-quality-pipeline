from typing import Any

UNIT_BY_METRIC = {
    "pm25_one_hourly": "µg/m³",
    "pm25_twenty_four_hourly": "µg/m³",
    "pm10_twenty_four_hourly": "µg/m³",
    "psi_twenty_four_hourly": "index",
    "so2_twenty_four_hourly": "µg/m³",
    "co_eight_hour_max": "mg/m³",
    "o3_eight_hour_max": "µg/m³",
    "no2_one_hour_max": "µg/m³",
    "co_sub_index": "index",
    "o3_sub_index": "index",
    "pm10_sub_index": "index",
    "pm25_sub_index": "index",
    "so2_sub_index": "index",
}


def flatten_payload(
    payload: dict[str, Any],
    endpoint_name: str,
    requested_date: str,
    run_id: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    items = payload.get("data", {}).get("items", [])

    for item in items:
        observed_at = item["timestamp"]
        published_at = item["updatedTimestamp"]
        readings = item.get("readings", {})

        for metric, regional_values in readings.items():
            unit = UNIT_BY_METRIC.get(metric, "unknown")

            for region, value in regional_values.items():
                rows.append(
                    {
                        "observed_at": observed_at,
                        "published_at": published_at,
                        "region": region,
                        "metric": metric,
                        "value": value,
                        "unit": unit,
                        "source_endpoint": endpoint_name,
                        "requested_date": requested_date,
                        "run_id": run_id,
                    }
                )

    return rows
