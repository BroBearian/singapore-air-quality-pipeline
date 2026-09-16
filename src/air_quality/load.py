from typing import Any

from supabase import Client


def save_raw_response(client: Client, record: dict[str, Any]) -> None:
    client.table("raw_api_responses").insert(record).execute()


def upsert_readings(client: Client, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    affected = 0
    # Small HTTP batches make backfills resilient to request-size limits.
    for offset in range(0, len(rows), 250):
        response = client.rpc(
            "upsert_air_quality_readings",
            {"p_rows": rows[offset : offset + 250]},
        ).execute()
        affected += int(response.data or 0)
    return affected


def save_quality_results(
    client: Client,
    results: list[dict[str, Any]],
) -> None:
    if results:
        client.table("data_quality_results").insert(results).execute()
