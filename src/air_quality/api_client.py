import time
from typing import Any

import requests


class DataGovClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "sg-air-quality-portfolio/1.0",
            }
        )

        if api_key:
            self.session.headers["x-api-key"] = api_key

    def get_readings(
        self,
        url: str,
        requested_date: str,
        attempts: int = 3,
    ) -> tuple[dict[str, Any], int]:
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = self.session.get(
                    url,
                    params={"date": requested_date},
                    timeout=30,
                )

                if response.status_code == 429:
                    time.sleep(2**attempt)
                    continue

                response.raise_for_status()
                payload = response.json()

                if payload.get("code") != 0:
                    raise RuntimeError(
                        "API returned an unsuccessful code: "
                        f"{payload.get('code')}; {payload.get('errorMsg')}"
                    )

                data = payload.get("data")
                if not isinstance(data, dict) or "items" not in data:
                    raise RuntimeError("API response is missing data.items")

                return payload, response.status_code

            except (requests.RequestException, ValueError, RuntimeError) as exc:
                last_error = exc
                if attempt < attempts:
                    time.sleep(2**attempt)

        raise RuntimeError(
            f"API request failed after {attempts} attempts"
        ) from last_error
