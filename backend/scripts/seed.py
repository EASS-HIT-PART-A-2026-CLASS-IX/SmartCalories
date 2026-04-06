"""POST sample entries. Start the API first: uv run uvicorn calorie_tracker.main:app --reload"""

from __future__ import annotations

import os
import sys

import httpx

SAMPLES: list[dict[str, str | int]] = [
    {"name": "Greek yogurt", "calories": 120, "meal": "breakfast"},
    {"name": "Chicken rice bowl", "calories": 650, "meal": "lunch"},
    {"name": "Apple", "calories": 95, "meal": "snack"},
]


def main() -> None:
    base = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    with httpx.Client(timeout=10.0) as http:
        for row in SAMPLES:
            r = http.post(f"{base}/entries", json=row)
            r.raise_for_status()
            print("seeded:", r.json())
    print("done")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
