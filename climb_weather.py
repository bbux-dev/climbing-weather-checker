#!/usr/bin/env python3
"""Rank local climbing areas by forecast climbability."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


FOLSOM_CA = (38.67796, -121.17606)
CACHE_DIR = Path(".weather_cache")
EARTH_RADIUS_MILES = 3958.8
ESTIMATED_TRAVEL_SPEED_MPH = 35.0
DRIVE_TIME_ROUNDING_INCREMENT_HOURS = 0.5
BASE_CLIMBABILITY_SCORE = 100.0
MIN_CLIMBABILITY_SCORE = 0
MAX_CLIMBABILITY_SCORE = 100
IDEAL_MAX_TEMP_F = 75.0
COLD_MAX_TEMP_F = 45.0
STRONG_WIND_MPH = 25.0
RAIN_PENALTY_PER_INCH = 120.0
MAX_RAIN_PENALTY = 70.0
PRECIP_PROBABILITY_PENALTY_PER_PERCENT = 0.4
MAX_PRECIP_PROBABILITY_PENALTY = 40.0
HEAT_PENALTY_PER_DEGREE_F = 4.0
MAX_HEAT_PENALTY = 50.0
COLD_PENALTY_PER_DEGREE_F = 2.0
MAX_COLD_PENALTY = 30.0
WIND_PENALTY_PER_MPH = 1.5
MAX_WIND_PENALTY = 20.0


@dataclass(frozen=True)
class ClimbingArea:
    name: str
    lat: float
    lon: float
    notes: str


AREAS = [
    ClimbingArea("Donner Summit", 39.3269, -120.3186, "Truckee granite"),
    ClimbingArea("Sugar Loaf (Kyburz, CA)", 38.7738, -120.2974, "Highway 50 crags"),
    ClimbingArea("Cosumnes River Gorge (Placerville, CA)", 38.6524, -120.7066, "Placerville granite"),
    ClimbingArea("Lovers Leap (Strawberry, CA)", 38.8006, -120.1399, "Strawberry multi-pitch"),
    ClimbingArea("South Lake Tahoe Crags (South Lake Tahoe, CA)", 38.9399, -119.9772, "Tahoe basin"),
    ClimbingArea("The Emeralds (Camp Spaulding, CA)", 39.3197, -120.6394, "Camp Spaulding area"),
    ClimbingArea("The Grotto (Rawhide, CA)", 37.9491, -120.4158, "Rawhide basalt"),
    ClimbingArea("Yosemite Valley (Yosemite, CA)", 37.7456, -119.5936, "Yosemite climbing"),
    ClimbingArea("Castle Rock State Park", 37.2303, -122.0956, "Santa Cruz Mountains"),
]


def parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc


def miles_between(origin: tuple[float, float], dest: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, origin)
    lat2, lon2 = map(math.radians, dest)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return EARTH_RADIUS_MILES * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def estimated_drive_time_hours(distance_miles: float) -> float:
    raw_hours = distance_miles / ESTIMATED_TRAVEL_SPEED_MPH
    increments = raw_hours / DRIVE_TIME_ROUNDING_INCREMENT_HOURS
    rounded_increments = math.floor(increments + 0.5)
    return rounded_increments * DRIVE_TIME_ROUNDING_INCREMENT_HOURS


def format_distance_time(distance_miles: float) -> str:
    hours = estimated_drive_time_hours(distance_miles)
    if hours.is_integer():
        time = f"{hours:.0f}h"
    else:
        time = f"{hours:.1f}h"
    return f"{distance_miles:.0f}/~{time}"


def forecast_url(area: ClimbingArea, date: dt.date) -> str:
    params = {
        "latitude": f"{area.lat:.5f}",
        "longitude": f"{area.lon:.5f}",
        "daily": ",".join(
            [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "precipitation_probability_max",
                "wind_speed_10m_max",
            ]
        ),
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "America/Los_Angeles",
        "start_date": date.isoformat(),
        "end_date": date.isoformat(),
    }
    return "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)


def cache_path_for(url: str, cache_dir: Path = CACHE_DIR) -> Path:
    cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return cache_dir / f"{cache_key}.json"


def read_cached_payload(url: str, cache_dir: Path = CACHE_DIR) -> dict[str, Any] | None:
    cache_path = cache_path_for(url, cache_dir)
    if not cache_path.exists():
        return None

    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_cached_payload(url: str, payload: dict[str, Any], cache_dir: Path = CACHE_DIR) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_path_for(url, cache_dir)
    cache_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def fetch_daily_forecast(
    area: ClimbingArea,
    date: dt.date,
    refresh: bool = False,
    cache_dir: Path = CACHE_DIR,
) -> dict[str, Any]:
    url = forecast_url(area, date)
    if not refresh:
        cached_payload = read_cached_payload(url, cache_dir)
        if cached_payload is not None:
            return daily_from_payload(area, date, cached_payload)

    request = urllib.request.Request(url, headers={"User-Agent": "climb-weather-prototype/0.1"})

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{area.name}: weather API returned {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"{area.name}: weather API request failed: {exc}") from exc

    write_cached_payload(url, payload, cache_dir)
    return daily_from_payload(area, date, payload)


def daily_from_payload(area: ClimbingArea, date: dt.date, payload: dict[str, Any]) -> dict[str, Any]:
    if "daily" not in payload or not payload["daily"].get("time"):
        raise RuntimeError(f"{area.name}: no forecast data returned for {date}")

    return payload["daily"]


def first(daily: dict[str, Any], key: str, default: float = 0.0) -> float:
    values = daily.get(key) or [default]
    value = values[0]
    return default if value is None else float(value)


def climbability_score(
    temp_max_f: float,
    precipitation_in: float,
    precipitation_probability: float,
    wind_mph: float,
) -> tuple[int, list[str]]:
    reasons = []
    score = BASE_CLIMBABILITY_SCORE

    if precipitation_in > 0:
        rain_penalty = min(MAX_RAIN_PENALTY, precipitation_in * RAIN_PENALTY_PER_INCH)
        score -= rain_penalty
        reasons.append(f"{precipitation_in:.2f} in precip")

    if precipitation_probability > 0:
        probability_penalty = min(
            MAX_PRECIP_PROBABILITY_PENALTY,
            precipitation_probability * PRECIP_PROBABILITY_PENALTY_PER_PERCENT,
        )
        score -= probability_penalty
        reasons.append(f"{precipitation_probability:.0f}% precip chance")

    if temp_max_f > IDEAL_MAX_TEMP_F:
        heat_penalty = min(MAX_HEAT_PENALTY, (temp_max_f - IDEAL_MAX_TEMP_F) * HEAT_PENALTY_PER_DEGREE_F)
        score -= heat_penalty
        reasons.append(f"high {temp_max_f:.0f}F")

    if temp_max_f < COLD_MAX_TEMP_F:
        cold_penalty = min(MAX_COLD_PENALTY, (COLD_MAX_TEMP_F - temp_max_f) * COLD_PENALTY_PER_DEGREE_F)
        score -= cold_penalty
        reasons.append(f"cold high {temp_max_f:.0f}F")

    if wind_mph > STRONG_WIND_MPH:
        wind_penalty = min(MAX_WIND_PENALTY, (wind_mph - STRONG_WIND_MPH) * WIND_PENALTY_PER_MPH)
        score -= wind_penalty
        reasons.append(f"wind {wind_mph:.0f} mph")

    if not reasons:
        reasons.append("dry and <= 75F")

    return max(MIN_CLIMBABILITY_SCORE, min(MAX_CLIMBABILITY_SCORE, round(score))), reasons


def rank_area(
    area: ClimbingArea,
    date: dt.date,
    origin: tuple[float, float],
    refresh: bool = False,
) -> dict[str, Any]:
    daily = fetch_daily_forecast(area, date, refresh=refresh)
    temp_max = first(daily, "temperature_2m_max")
    temp_min = first(daily, "temperature_2m_min")
    precipitation = first(daily, "precipitation_sum")
    precipitation_probability = first(daily, "precipitation_probability_max")
    wind = first(daily, "wind_speed_10m_max")
    score, reasons = climbability_score(temp_max, precipitation, precipitation_probability, wind)
    distance_miles = miles_between(origin, (area.lat, area.lon))

    return {
        "name": area.name,
        "score": score,
        "distance_miles": distance_miles,
        "drive_time_hours_estimate": estimated_drive_time_hours(distance_miles),
        "temp_max_f": temp_max,
        "temp_min_f": temp_min,
        "precipitation_in": precipitation,
        "precipitation_probability": precipitation_probability,
        "wind_mph": wind,
        "reasons": reasons,
        "notes": area.notes,
    }


def sort_rows(rows: list[dict[str, Any]], by_distance: bool = False) -> None:
    if by_distance:
        rows.sort(key=lambda row: (row["distance_miles"], -row["score"]))
    else:
        rows.sort(key=lambda row: (-row["score"], row["distance_miles"]))


def print_table(rows: list[dict[str, Any]], date: dt.date) -> None:
    print(f"Climbability forecast for {date.isoformat()} from Folsom, CA")
    print()
    area_width = max(24, *(len(row["name"]) for row in rows))
    header = (
        f"{'Rank':>4}  {'Area':<{area_width}} {'Score':>6} {'Miles/Time':>10} "
        f"{'Temp F':>13} {'Precip':>16} {'Wind':>8}  Why"
    )
    print(header)
    print("-" * len(header))
    for index, row in enumerate(rows, start=1):
        temp = f"{row['temp_min_f']:.0f}-{row['temp_max_f']:.0f}"
        precip = f"{row['precipitation_in']:.2f}in/{row['precipitation_probability']:.0f}%"
        why = "; ".join(row["reasons"])
        print(
            f"{index:>4}  {row['name']:<{area_width}} {row['score']:>5}% "
            f"{format_distance_time(row['distance_miles']):>10} {temp:>13} {precip:>16} "
            f"{row['wind_mph']:>6.0f}mph  {why}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rank nearby climbing areas by weather climbability for a date."
    )
    parser.add_argument("date", type=parse_date, help="Forecast date in YYYY-MM-DD format")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument(
        "--by-distance",
        action="store_true",
        help="Sort by distance first, then climbability score",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Fetch fresh weather data and update the local cache",
    )
    args = parser.parse_args(argv)

    rows = []
    failures = []
    for area in AREAS:
        try:
            rows.append(rank_area(area, args.date, FOLSOM_CA, refresh=args.refresh))
        except RuntimeError as exc:
            failures.append(str(exc))

    sort_rows(rows, by_distance=args.by_distance)

    if args.json:
        print(json.dumps({"date": args.date.isoformat(), "areas": rows, "errors": failures}, indent=2))
    else:
        print_table(rows, args.date)
        if failures:
            print()
            print("Warnings:")
            for failure in failures:
                print(f"- {failure}")

    return 1 if failures and not rows else 0


if __name__ == "__main__":
    sys.exit(main())
