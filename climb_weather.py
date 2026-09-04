#!/usr/bin/env python3
"""Rank local climbing areas by forecast climbability."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import math
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


FOLSOM_CA = (38.67796, -121.17606)
ORIGINS = {
    "Folsom, CA": FOLSOM_CA,
    "Auburn, CA": (38.8966, -121.0769),
    "Cameron Park, CA": (38.6688, -120.9872),
}
CACHE_DIR = Path(".weather_cache")
DEFAULT_HTML_REPORT_TEMPLATE = "climb-weather-{date}.html"
HTML_BACKGROUND_IMAGE_PATH = Path("assets/local-crag-background.png")
HTML_REPORT_DAYS = 7
OVERVIEW_TOP_AREA_COUNT = 5
EARTH_RADIUS_MILES = 3958.8
ESTIMATED_TRAVEL_SPEED_MPH = 35.0
DRIVE_TIME_ROUNDING_INCREMENT_HOURS = 0.5
MIN_NONZERO_DRIVE_TIME_HOURS = 0.5
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
WEATHER_VERIFICATION_URL = "https://forecast.weather.gov/MapClick.php?lat={lat:.5f}&lon={lon:.5f}"
ROCK_TYPE_GRANITE = "granite"
ROCK_TYPE_BASALT = "basalt"
ROCK_TYPE_LIMESTONE = "limestone"
ROCK_TYPE_SANDSTONE = "sandstone"
SANDSTONE_DRYOUT_DAYS_AFTER_RAIN = 2
SANDSTONE_RAIN_THRESHOLD_IN = 0.0


@dataclass(frozen=True)
class ClimbingArea:
    name: str
    lat: float
    lon: float
    notes: str
    mountain_project_url: str
    rock_type: str = ROCK_TYPE_GRANITE


AREAS = [
    ClimbingArea(
        "Donner Summit",
        39.3269,
        -120.3186,
        "Truckee granite",
        "https://www.mountainproject.com/area/105733935/donner-summit",
    ),
    ClimbingArea(
        "Sugar Loaf (Kyburz, CA)",
        38.7738,
        -120.2974,
        "Highway 50 crags",
        "https://www.mountainproject.com/area/105734010/sugarloaf-area",
    ),
    ClimbingArea(
        "Cosumnes River Gorge (Placerville, CA)",
        38.6524,
        -120.7066,
        "Placerville granite",
        "https://www.mountainproject.com/area/105733956/cosumnes-river-gorge",
    ),
    ClimbingArea(
        "Lovers Leap (Strawberry, CA)",
        38.8006,
        -120.1399,
        "Strawberry multi-pitch",
        "https://www.mountainproject.com/area/105733959/lovers-leap",
    ),
    ClimbingArea(
        "South Lake Tahoe Crags (South Lake Tahoe, CA)",
        38.9399,
        -119.9772,
        "Tahoe basin",
        "https://www.mountainproject.com/area/110561742/south-shore",
    ),
    ClimbingArea(
        "The Emeralds (Camp Spaulding, CA)",
        39.3197,
        -120.6394,
        "Camp Spaulding area",
        "https://www.mountainproject.com/area/105733929/the-emeralds",
    ),
    ClimbingArea(
        "The Grotto (Rawhide, CA)",
        37.9491,
        -120.4158,
        "Rawhide basalt",
        "https://www.mountainproject.com/area/105734135/the-grotto",
        ROCK_TYPE_BASALT,
    ),
    ClimbingArea(
        "Yosemite Valley (Yosemite, CA)",
        37.7456,
        -119.5936,
        "Yosemite climbing",
        "https://www.mountainproject.com/area/105833388/yosemite-valley",
    ),
    ClimbingArea(
        "Castle Rock State Park",
        37.2303,
        -122.0956,
        "Santa Cruz Mountains",
        "https://www.mountainproject.com/area/105733890/castle-rock-and-sanborn-area",
        ROCK_TYPE_SANDSTONE,
    ),
    ClimbingArea(
        "Auburn Quarry (Auburn, CA)",
        38.91231,
        -121.03567,
        "Auburn limestone sport climbing",
        "https://www.mountainproject.com/area/105733941/cave-valley-aka-auburn-quarry",
        ROCK_TYPE_LIMESTONE,
    ),
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
    if distance_miles <= 0:
        return 0.0

    raw_hours = distance_miles / ESTIMATED_TRAVEL_SPEED_MPH
    increments = raw_hours / DRIVE_TIME_ROUNDING_INCREMENT_HOURS
    rounded_increments = math.floor(increments + 0.5)
    return max(
        MIN_NONZERO_DRIVE_TIME_HOURS,
        rounded_increments * DRIVE_TIME_ROUNDING_INCREMENT_HOURS,
    )


def format_distance_time(distance_miles: float) -> str:
    hours = estimated_drive_time_hours(distance_miles)
    if hours.is_integer():
        time = f"{hours:.0f}h"
    else:
        time = f"{hours:.1f}h"
    return f"{distance_miles:.0f}/~{time}"


def forecast_url(area: ClimbingArea, start_date: dt.date, end_date: dt.date) -> str:
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
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    return "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)


def weather_verification_url(area: ClimbingArea) -> str:
    return WEATHER_VERIFICATION_URL.format(lat=area.lat, lon=area.lon)


def forecast_start_for_area(area: ClimbingArea, start_date: dt.date) -> dt.date:
    if area.rock_type == ROCK_TYPE_SANDSTONE:
        return start_date - dt.timedelta(days=SANDSTONE_DRYOUT_DAYS_AFTER_RAIN)
    return start_date


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


def fetch_forecast(
    area: ClimbingArea,
    start_date: dt.date,
    end_date: dt.date,
    refresh: bool = False,
    cache_dir: Path = CACHE_DIR,
) -> dict[str, Any]:
    url = forecast_url(area, start_date, end_date)
    cached_payload = read_cached_payload(url, cache_dir)
    if cached_payload is not None and not refresh:
        return daily_from_payload(area, start_date, end_date, cached_payload)

    request = urllib.request.Request(url, headers={"User-Agent": "climb-weather-prototype/0.1"})

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if cached_payload is not None:
            return daily_from_payload(area, start_date, end_date, cached_payload)
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{area.name}: weather API returned {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        if cached_payload is not None:
            return daily_from_payload(area, start_date, end_date, cached_payload)
        raise RuntimeError(f"{area.name}: weather API request failed: {exc}") from exc

    write_cached_payload(url, payload, cache_dir)
    return daily_from_payload(area, start_date, end_date, payload)


def fetch_daily_forecast(
    area: ClimbingArea,
    date: dt.date,
    refresh: bool = False,
    cache_dir: Path = CACHE_DIR,
) -> dict[str, Any]:
    return fetch_forecast(area, date, date, refresh=refresh, cache_dir=cache_dir)


def daily_from_payload(
    area: ClimbingArea,
    start_date: dt.date,
    end_date: dt.date,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if "daily" not in payload or not payload["daily"].get("time"):
        raise RuntimeError(f"{area.name}: no forecast data returned for {start_date} to {end_date}")

    return payload["daily"]


def first(daily: dict[str, Any], key: str, default: float = 0.0) -> float:
    values = daily.get(key) or [default]
    value = values[0]
    return default if value is None else float(value)


def value_at(daily: dict[str, Any], key: str, index: int, default: float = 0.0) -> float:
    values = daily.get(key) or []
    if index >= len(values):
        return default
    value = values[index]
    return default if value is None else float(value)


def sandstone_wet_weather_checker(
    area: ClimbingArea,
    date: dt.date,
    daily: dict[str, Any],
) -> str | None:
    if area.rock_type != ROCK_TYPE_SANDSTONE:
        return None

    dates = daily.get("time") or []
    precipitation_values = daily.get("precipitation_sum") or []
    last_rain_date = None
    for index, date_text in enumerate(dates):
        try:
            candidate_date = dt.date.fromisoformat(date_text)
        except ValueError:
            continue
        if candidate_date > date:
            continue
        precipitation = 0.0
        if index < len(precipitation_values) and precipitation_values[index] is not None:
            precipitation = float(precipitation_values[index])
        if precipitation > SANDSTONE_RAIN_THRESHOLD_IN:
            last_rain_date = candidate_date

    if last_rain_date is None:
        return None

    days_since_rain = (date - last_rain_date).days
    if 0 <= days_since_rain <= SANDSTONE_DRYOUT_DAYS_AFTER_RAIN:
        if days_since_rain == 0:
            return "sandstone wet weather: rain today"
        return f"sandstone wet weather: {days_since_rain} day(s) after rain"

    return None


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
    cache_dir: Path = CACHE_DIR,
) -> dict[str, Any]:
    daily = fetch_forecast(
        area,
        forecast_start_for_area(area, date),
        date,
        refresh=refresh,
        cache_dir=cache_dir,
    )
    date_key = date.isoformat()
    available_dates = daily.get("time") or []
    index = available_dates.index(date_key) if date_key in available_dates else 0
    return rank_area_from_daily(area, date, daily, index, origin)


def rank_area_from_daily(
    area: ClimbingArea,
    date: dt.date,
    daily: dict[str, Any],
    index: int,
    origin: tuple[float, float],
) -> dict[str, Any]:
    temp_max = value_at(daily, "temperature_2m_max", index)
    temp_min = value_at(daily, "temperature_2m_min", index)
    precipitation = value_at(daily, "precipitation_sum", index)
    precipitation_probability = value_at(daily, "precipitation_probability_max", index)
    wind = value_at(daily, "wind_speed_10m_max", index)
    score, reasons = climbability_score(temp_max, precipitation, precipitation_probability, wind)
    sandstone_reason = sandstone_wet_weather_checker(area, date, daily)
    if sandstone_reason:
        score = MIN_CLIMBABILITY_SCORE
        reasons = [sandstone_reason]
    distance_miles = miles_between(origin, (area.lat, area.lon))

    return {
        "name": area.name,
        "mountain_project_url": area.mountain_project_url,
        "weather_verification_url": weather_verification_url(area),
        "rock_type": area.rock_type,
        "date": date.isoformat(),
        "lat": area.lat,
        "lon": area.lon,
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


def report_dates(start_date: dt.date, days: int = HTML_REPORT_DAYS) -> list[dt.date]:
    return [start_date + dt.timedelta(days=offset) for offset in range(days)]


def rank_week(
    start_date: dt.date,
    origin: tuple[float, float],
    refresh: bool = False,
    days: int = HTML_REPORT_DAYS,
    cache_dir: Path = CACHE_DIR,
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    dates = report_dates(start_date, days)
    end_date = dates[-1]
    rows_by_date = {date.isoformat(): [] for date in dates}
    failures = []

    for area in AREAS:
        try:
            daily = fetch_forecast(
                area,
                forecast_start_for_area(area, start_date),
                end_date,
                refresh=refresh,
                cache_dir=cache_dir,
            )
        except RuntimeError as exc:
            failures.append(str(exc))
            continue

        available_dates = daily.get("time") or []
        for date in dates:
            date_key = date.isoformat()
            if date_key not in available_dates:
                failures.append(f"{area.name}: no forecast data returned for {date_key}")
                continue
            rows_by_date[date_key].append(
                rank_area_from_daily(area, date, daily, available_dates.index(date_key), origin)
            )

    for rows in rows_by_date.values():
        sort_rows(rows)

    return rows_by_date, failures


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


def score_class(score: int) -> str:
    if score >= 90:
        return "excellent"
    if score >= 75:
        return "good"
    if score >= 50:
        return "iffy"
    return "poor"


def render_html_report(
    rows: list[dict[str, Any]],
    date: dt.date,
    failures: list[str],
    background_image_path: str = HTML_BACKGROUND_IMAGE_PATH.as_posix(),
    by_distance: bool = False,
) -> str:
    generated_at = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    best_area = rows[0]["name"] if rows else "No areas ranked"
    payload = {
        "date": date.isoformat(),
        "generatedAt": generated_at,
        "bestArea": best_area,
        "defaultOrigin": "Folsom, CA",
        "initialSortByDistance": by_distance,
        "travelSpeedMph": ESTIMATED_TRAVEL_SPEED_MPH,
        "driveTimeRoundingIncrementHours": DRIVE_TIME_ROUNDING_INCREMENT_HOURS,
        "minNonzeroDriveTimeHours": MIN_NONZERO_DRIVE_TIME_HOURS,
        "earthRadiusMiles": EARTH_RADIUS_MILES,
        "origins": [
            {"name": name, "lat": coords[0], "lon": coords[1]}
            for name, coords in ORIGINS.items()
        ],
        "areas": rows,
        "errors": failures,
    }
    payload_json = (
        json.dumps(payload, sort_keys=True)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Climbability Forecast for {html.escape(date.isoformat())}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f2ec;
      --text: #20231f;
      --muted: #686c61;
      --line: #d9d1c4;
      --panel: #fffdfa;
      --excellent: #1f7a4d;
      --good: #587d2f;
      --iffy: #a46418;
      --poor: #a23b3b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        linear-gradient(rgba(22, 27, 22, 0.18), rgba(245, 242, 236, 0.92) 420px),
        url("{html.escape(background_image_path, quote=True)}") top center / 100% auto no-repeat,
        var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }}
    main {{
      width: min(1120px, calc(100% - 32px));
      margin: 0 auto;
      padding: 32px 0 48px;
    }}
    header {{
      min-height: 300px;
      display: flex;
      flex-direction: column;
      justify-content: flex-end;
      color: #fffdfa;
      text-shadow: 0 1px 8px rgba(0, 0, 0, 0.55);
      padding-bottom: 28px;
      margin-bottom: 20px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(2rem, 5vw, 4rem);
      line-height: 1;
      letter-spacing: 0;
    }}
    .summary {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 18px;
      color: #fffdfa;
    }}
    .summary > span {{
      border: 1px solid rgba(255, 253, 250, 0.35);
      background: rgba(32, 35, 31, 0.42);
      padding: 6px 10px;
      border-radius: 6px;
      backdrop-filter: blur(4px);
    }}
    .controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      margin-bottom: 16px;
      padding: 12px;
      background: rgba(255, 253, 250, 0.9);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .control {{
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-weight: 700;
    }}
    select {{
      appearance: none;
      background: #fffdfa;
      border: 1px solid var(--line);
      border-radius: 6px;
      color: var(--text);
      font: inherit;
      font-weight: 700;
      padding: 7px 34px 7px 10px;
      background-image:
        linear-gradient(45deg, transparent 50%, var(--muted) 50%),
        linear-gradient(135deg, var(--muted) 50%, transparent 50%);
      background-position:
        calc(100% - 17px) 50%,
        calc(100% - 12px) 50%;
      background-size: 5px 5px, 5px 5px;
      background-repeat: no-repeat;
    }}
    input[type="checkbox"] {{
      width: 18px;
      height: 18px;
      accent-color: var(--excellent);
    }}
    .report-grid {{
      display: grid;
      gap: 12px;
    }}
    .area-card {{
      display: grid;
      grid-template-columns: 48px minmax(220px, 1fr) 112px minmax(280px, 0.9fr);
      gap: 18px;
      align-items: center;
      background: var(--panel);
      border: 1px solid var(--line);
      border-left: 7px solid var(--good);
      border-radius: 8px;
      padding: 16px;
      box-shadow: 0 1px 0 rgba(0, 0, 0, 0.03);
    }}
    .area-card.excellent {{ border-left-color: var(--excellent); }}
    .area-card.good {{ border-left-color: var(--good); }}
    .area-card.iffy {{ border-left-color: var(--iffy); }}
    .area-card.poor {{ border-left-color: var(--poor); }}
    .rank {{
      color: var(--muted);
      font-weight: 700;
      font-size: 1.05rem;
    }}
    h2 {{
      margin: 0;
      font-size: 1.25rem;
      letter-spacing: 0;
    }}
    a {{
      color: inherit;
      text-decoration-color: rgba(31, 122, 77, 0.45);
      text-underline-offset: 3px;
    }}
    a:hover {{
      text-decoration-color: currentColor;
    }}
    .notes, .reason {{
      margin: 4px 0 0;
      color: var(--muted);
    }}
    .reason {{
      color: var(--text);
      font-weight: 600;
    }}
    .score-block {{
      text-align: right;
    }}
    .score {{
      font-size: 2.1rem;
      line-height: 1;
      font-weight: 800;
    }}
    .score-label {{
      color: var(--muted);
      font-size: 0.85rem;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
      margin: 0;
    }}
    .metrics div {{
      border-left: 1px solid var(--line);
      padding-left: 10px;
      min-width: 0;
    }}
    dt {{
      color: var(--muted);
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    dd {{
      margin: 2px 0 0;
      font-weight: 700;
      white-space: nowrap;
    }}
    .warnings {{
      margin-top: 24px;
      border: 1px solid #e2b7a0;
      background: #fff8f3;
      border-radius: 8px;
      padding: 16px;
    }}
    .warnings h2 {{
      font-size: 1rem;
    }}
    @media (max-width: 860px) {{
      .area-card {{
        grid-template-columns: 44px 1fr 92px;
      }}
      .metrics {{
        grid-column: 2 / -1;
      }}
    }}
    @media (max-width: 620px) {{
      main {{
        width: min(100% - 20px, 1120px);
        padding-top: 18px;
      }}
      header {{
        min-height: 240px;
      }}
      .area-card {{
        grid-template-columns: 1fr;
        gap: 10px;
      }}
      .rank, .score-block {{
        text-align: left;
      }}
      .metrics {{
        grid-column: auto;
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .metrics div {{
        border-left: 0;
        padding-left: 0;
        border-top: 1px solid var(--line);
        padding-top: 8px;
      }}
      .controls {{
        align-items: stretch;
      }}
      .control {{
        width: 100%;
        justify-content: flex-start;
      }}
      select {{
        min-width: 0;
        max-width: 210px;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Climbability Forecast</h1>
      <div class="summary">
        <span>Date: {html.escape(date.isoformat())}</span>
        <span>Origin: <span id="origin-summary">Folsom, CA</span></span>
        <span>Best: <span id="best-summary">{html.escape(best_area)}</span></span>
        <span>Generated: {html.escape(generated_at)}</span>
      </div>
    </header>
    <section class="controls" aria-label="Report controls">
      <label class="control" for="origin-select">
        Origin
        <select id="origin-select"></select>
      </label>
      <label class="control">
        <input id="sort-by-distance" type="checkbox">
        Sort by distance
      </label>
    </section>
    <section id="report-grid" class="report-grid"></section>
    <section id="warnings"></section>
  </main>
  <script id="report-data" type="application/json">{payload_json}</script>
  <script>
    const reportData = JSON.parse(document.getElementById("report-data").textContent);
    const originSelect = document.getElementById("origin-select");
    const sortByDistance = document.getElementById("sort-by-distance");
    const reportGrid = document.getElementById("report-grid");
    const originSummary = document.getElementById("origin-summary");
    const bestSummary = document.getElementById("best-summary");
    const warnings = document.getElementById("warnings");

    function escapeHtml(value) {{
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }}

    function milesBetween(origin, area) {{
      const lat1 = origin.lat * Math.PI / 180;
      const lon1 = origin.lon * Math.PI / 180;
      const lat2 = area.lat * Math.PI / 180;
      const lon2 = area.lon * Math.PI / 180;
      const dlat = lat2 - lat1;
      const dlon = lon2 - lon1;
      const a = Math.sin(dlat / 2) ** 2
        + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dlon / 2) ** 2;
      return reportData.earthRadiusMiles * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }}

    function estimatedDriveTimeHours(distanceMiles) {{
      if (distanceMiles <= 0) return 0;
      const rawHours = distanceMiles / reportData.travelSpeedMph;
      const increments = rawHours / reportData.driveTimeRoundingIncrementHours;
      return Math.max(
        reportData.minNonzeroDriveTimeHours,
        Math.floor(increments + 0.5) * reportData.driveTimeRoundingIncrementHours
      );
    }}

    function formatDistanceTime(distanceMiles) {{
      const hours = estimatedDriveTimeHours(distanceMiles);
      const time = Number.isInteger(hours) ? `${{hours.toFixed(0)}}h` : `${{hours.toFixed(1)}}h`;
      return `${{distanceMiles.toFixed(0)}}/~${{time}}`;
    }}

    function scoreClass(score) {{
      if (score >= 90) return "excellent";
      if (score >= 75) return "good";
      if (score >= 50) return "iffy";
      return "poor";
    }}
    function areaLink(area) {{
      const name = escapeHtml(area.name);
      if (!area.mountain_project_url) return name;
      return `<a href="${{escapeHtml(area.mountain_project_url)}}" target="_blank" rel="noopener noreferrer">${{name}}</a>`;
    }}
    function weatherLink(area, text) {{
      const label = escapeHtml(text);
      if (!area.weather_verification_url) return label;
      return `<a href="${{escapeHtml(area.weather_verification_url)}}" target="_blank" rel="noopener noreferrer" title="Verify with NOAA/NWS">${{label}}</a>`;
    }}

    function selectedOrigin() {{
      return reportData.origins.find((origin) => origin.name === originSelect.value) || reportData.origins[0];
    }}

    function rankedAreas() {{
      const origin = selectedOrigin();
      const areas = reportData.areas.map((area) => ({{
        ...area,
        distance_miles: milesBetween(origin, area),
      }}));

      if (sortByDistance.checked) {{
        areas.sort((a, b) => a.distance_miles - b.distance_miles || b.score - a.score);
      }} else {{
        areas.sort((a, b) => b.score - a.score || a.distance_miles - b.distance_miles);
      }}

      return areas;
    }}

    function renderWarnings() {{
      if (!reportData.errors.length) {{
        warnings.innerHTML = "";
        return;
      }}
      const items = reportData.errors.map((error) => `<li>${{escapeHtml(error)}}</li>`).join("");
      warnings.innerHTML = `<section class="warnings"><h2>Warnings</h2><ul>${{items}}</ul></section>`;
    }}

    function render() {{
      const origin = selectedOrigin();
      const areas = rankedAreas();
      originSummary.textContent = origin.name;
      bestSummary.textContent = areas.length ? areas[0].name : "No areas ranked";
      reportGrid.innerHTML = areas.map((area, index) => {{
        const reasons = escapeHtml(area.reasons.join("; "));
        const temp = `${{area.temp_min_f.toFixed(0)}}-${{area.temp_max_f.toFixed(0)}}F`;
        const precip = `${{area.precipitation_in.toFixed(2)}} in / ${{area.precipitation_probability.toFixed(0)}}%`;
        const wind = `${{area.wind_mph.toFixed(0)}} mph`;
        return `
      <article class="area-card ${{scoreClass(area.score)}}">
        <div class="rank">#${{index + 1}}</div>
        <div class="area-main">
          <h2>${{areaLink(area)}}</h2>
          <p class="notes">${{escapeHtml(area.notes)}}</p>
          <p class="reason">${{reasons}}</p>
        </div>
        <div class="score-block">
          <div class="score">${{area.score}}%</div>
          <div class="score-label">climbable</div>
        </div>
        <dl class="metrics">
          <div><dt>Miles/Time</dt><dd>${{formatDistanceTime(area.distance_miles)}}</dd></div>
          <div><dt>Temp</dt><dd>${{weatherLink(area, temp)}}</dd></div>
          <div><dt>Precip</dt><dd>${{weatherLink(area, precip)}}</dd></div>
          <div><dt>Wind</dt><dd>${{weatherLink(area, wind)}}</dd></div>
        </dl>
      </article>`;
      }}).join("");
    }}

    for (const origin of reportData.origins) {{
      const option = document.createElement("option");
      option.value = origin.name;
      option.textContent = origin.name;
      option.selected = origin.name === reportData.defaultOrigin;
      originSelect.appendChild(option);
    }}

    sortByDistance.checked = reportData.initialSortByDistance;
    originSelect.addEventListener("change", render);
    sortByDistance.addEventListener("change", render);
    renderWarnings();
    render();
  </script>
</body>
</html>
"""


def write_html_report(
    rows: list[dict[str, Any]],
    date: dt.date,
    failures: list[str],
    output_path: Path,
    by_distance: bool = False,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    background_path = os.path.relpath(HTML_BACKGROUND_IMAGE_PATH, start=output_path.parent)
    report = render_html_report(
        rows,
        date,
        failures,
        background_image_path=Path(background_path).as_posix(),
        by_distance=by_distance,
    )
    output_path.write_text(report, encoding="utf-8")
    return output_path


def render_week_html_report(
    rows_by_date: dict[str, list[dict[str, Any]]],
    start_date: dt.date,
    failures: list[str],
    background_image_path: str = HTML_BACKGROUND_IMAGE_PATH.as_posix(),
    by_distance: bool = False,
) -> str:
    generated_at = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    dates = [date.isoformat() for date in report_dates(start_date)]
    first_rows = rows_by_date.get(dates[0], [])
    best_area = first_rows[0]["name"] if first_rows else "No areas ranked"
    end_date = start_date + dt.timedelta(days=HTML_REPORT_DAYS - 1)
    payload = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dates": dates,
        "generatedAt": generated_at,
        "bestArea": best_area,
        "defaultOrigin": "Folsom, CA",
        "initialSortByDistance": by_distance,
        "overviewTopAreaCount": OVERVIEW_TOP_AREA_COUNT,
        "travelSpeedMph": ESTIMATED_TRAVEL_SPEED_MPH,
        "driveTimeRoundingIncrementHours": DRIVE_TIME_ROUNDING_INCREMENT_HOURS,
        "minNonzeroDriveTimeHours": MIN_NONZERO_DRIVE_TIME_HOURS,
        "earthRadiusMiles": EARTH_RADIUS_MILES,
        "origins": [
            {"name": name, "lat": coords[0], "lon": coords[1]}
            for name, coords in ORIGINS.items()
        ],
        "days": rows_by_date,
        "errors": failures,
    }
    payload_json = (
        json.dumps(payload, sort_keys=True)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>7-Day Climbability Forecast from {html.escape(start_date.isoformat())}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f2ec;
      --text: #20231f;
      --muted: #686c61;
      --line: #d9d1c4;
      --panel: #fffdfa;
      --excellent: #1f7a4d;
      --good: #587d2f;
      --iffy: #a46418;
      --poor: #a23b3b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        linear-gradient(rgba(22, 27, 22, 0.18), rgba(245, 242, 236, 0.92) 420px),
        url("{html.escape(background_image_path, quote=True)}") top center / 100% auto no-repeat,
        var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }}
    main {{
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 32px 0 48px;
    }}
    header {{
      min-height: 300px;
      display: flex;
      flex-direction: column;
      justify-content: flex-end;
      color: #fffdfa;
      text-shadow: 0 1px 8px rgba(0, 0, 0, 0.55);
      padding-bottom: 28px;
      margin-bottom: 20px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(2rem, 5vw, 4rem);
      line-height: 1;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 0;
      font-size: 1.25rem;
      letter-spacing: 0;
    }}
    .summary, .tabs, .controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }}
    .summary {{
      margin-top: 18px;
      color: #fffdfa;
    }}
    .summary > span {{
      border: 1px solid rgba(255, 253, 250, 0.35);
      background: rgba(32, 35, 31, 0.42);
      padding: 6px 10px;
      border-radius: 6px;
      backdrop-filter: blur(4px);
    }}
    .controls, .tabs {{
      margin-bottom: 14px;
      padding: 12px;
      background: rgba(255, 253, 250, 0.9);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .control {{
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-weight: 700;
    }}
    select, button {{
      font: inherit;
      font-weight: 700;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fffdfa;
      color: var(--text);
    }}
    select {{
      appearance: none;
      padding: 7px 34px 7px 10px;
      background-image:
        linear-gradient(45deg, transparent 50%, var(--muted) 50%),
        linear-gradient(135deg, var(--muted) 50%, transparent 50%);
      background-position: calc(100% - 17px) 50%, calc(100% - 12px) 50%;
      background-size: 5px 5px, 5px 5px;
      background-repeat: no-repeat;
    }}
    button {{
      cursor: pointer;
      padding: 7px 10px;
    }}
    button.active {{
      background: var(--text);
      border-color: var(--text);
      color: #fffdfa;
    }}
    input[type="checkbox"] {{
      width: 18px;
      height: 18px;
      accent-color: var(--excellent);
    }}
    .overview {{
      overflow-x: auto;
      background: rgba(255, 253, 250, 0.92);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }}
    .overview h2 {{
      margin-bottom: 10px;
    }}
    table {{
      width: 100%;
      min-width: 760px;
      border-collapse: separate;
      border-spacing: 0;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 9px;
      text-align: center;
    }}
    th:first-child, td:first-child {{
      text-align: left;
      position: sticky;
      left: 0;
      background: rgba(255, 253, 250, 0.97);
      z-index: 1;
    }}
    .score-cell {{
      color: #fffdfa;
      font-weight: 800;
      border-radius: 6px;
      cursor: help;
    }}
    .excellent {{ background: var(--excellent); }}
    .good {{ background: var(--good); }}
    .iffy {{ background: var(--iffy); }}
    .poor {{ background: var(--poor); }}
    .report-grid {{
      display: grid;
      gap: 12px;
    }}
    .area-card {{
      display: grid;
      grid-template-columns: 48px minmax(220px, 1fr) 112px minmax(280px, 0.9fr);
      gap: 18px;
      align-items: center;
      background: var(--panel);
      border: 1px solid var(--line);
      border-left: 7px solid var(--good);
      border-radius: 8px;
      padding: 16px;
      box-shadow: 0 1px 0 rgba(0, 0, 0, 0.03);
    }}
    .area-card.excellent {{ border-left-color: var(--excellent); background: var(--panel); }}
    .area-card.good {{ border-left-color: var(--good); background: var(--panel); }}
    .area-card.iffy {{ border-left-color: var(--iffy); background: var(--panel); }}
    .area-card.poor {{ border-left-color: var(--poor); background: var(--panel); }}
    .rank {{
      color: var(--muted);
      font-weight: 700;
      font-size: 1.05rem;
    }}
    .notes, .reason {{
      margin: 4px 0 0;
      color: var(--muted);
    }}
    .reason {{
      color: var(--text);
      font-weight: 600;
    }}
    .score-block {{
      text-align: right;
    }}
    .score {{
      font-size: 2.1rem;
      line-height: 1;
      font-weight: 800;
    }}
    .score-label {{
      color: var(--muted);
      font-size: 0.85rem;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
      margin: 0;
    }}
    .metrics div {{
      border-left: 1px solid var(--line);
      padding-left: 10px;
      min-width: 0;
    }}
    dt {{
      color: var(--muted);
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    dd {{
      margin: 2px 0 0;
      font-weight: 700;
      white-space: nowrap;
    }}
    .warnings {{
      margin-top: 24px;
      border: 1px solid #e2b7a0;
      background: #fff8f3;
      border-radius: 8px;
      padding: 16px;
    }}
    @media (max-width: 860px) {{
      .area-card {{ grid-template-columns: 44px 1fr 92px; }}
      .metrics {{ grid-column: 2 / -1; }}
    }}
    @media (max-width: 620px) {{
      main {{
        width: min(100% - 20px, 1180px);
        padding-top: 18px;
      }}
      header {{ min-height: 240px; }}
      .area-card {{
        grid-template-columns: 1fr;
        gap: 10px;
      }}
      .rank, .score-block {{ text-align: left; }}
      .metrics {{
        grid-column: auto;
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .metrics div {{
        border-left: 0;
        padding-left: 0;
        border-top: 1px solid var(--line);
        padding-top: 8px;
      }}
      .control {{ width: 100%; }}
      select {{ max-width: 220px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>7-Day Climbability Forecast</h1>
      <div class="summary">
        <span>Dates: {html.escape(start_date.isoformat())} to {html.escape(end_date.isoformat())}</span>
        <span>Origin: <span id="origin-summary">Folsom, CA</span></span>
        <span>Best: <span id="best-summary">{html.escape(best_area)}</span></span>
        <span>Generated: {html.escape(generated_at)}</span>
      </div>
    </header>
    <section class="controls" aria-label="Report controls">
      <label class="control" for="origin-select">Origin <select id="origin-select"></select></label>
      <label class="control"><input id="sort-by-distance" type="checkbox"> Sort day reports by distance</label>
    </section>
    <nav id="tabs" class="tabs" aria-label="Forecast days"></nav>
    <section id="overview"></section>
    <section id="report-grid" class="report-grid"></section>
    <section id="warnings"></section>
  </main>
  <script id="report-data" type="application/json">{payload_json}</script>
  <script>
    const reportData = JSON.parse(document.getElementById("report-data").textContent);
    const originSelect = document.getElementById("origin-select");
    const sortByDistance = document.getElementById("sort-by-distance");
    const tabs = document.getElementById("tabs");
    const overview = document.getElementById("overview");
    const reportGrid = document.getElementById("report-grid");
    const originSummary = document.getElementById("origin-summary");
    const bestSummary = document.getElementById("best-summary");
    const warnings = document.getElementById("warnings");
    let activeView = "overview";

    function escapeHtml(value) {{
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }}
    function dayLabel(dateText) {{
      return new Date(`${{dateText}}T12:00:00`).toLocaleDateString(undefined, {{ weekday: "short", month: "short", day: "numeric" }});
    }}
    function milesBetween(origin, area) {{
      const lat1 = origin.lat * Math.PI / 180;
      const lon1 = origin.lon * Math.PI / 180;
      const lat2 = area.lat * Math.PI / 180;
      const lon2 = area.lon * Math.PI / 180;
      const dlat = lat2 - lat1;
      const dlon = lon2 - lon1;
      const a = Math.sin(dlat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dlon / 2) ** 2;
      return reportData.earthRadiusMiles * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }}
    function estimatedDriveTimeHours(distanceMiles) {{
      if (distanceMiles <= 0) return 0;
      const rawHours = distanceMiles / reportData.travelSpeedMph;
      const increments = rawHours / reportData.driveTimeRoundingIncrementHours;
      return Math.max(reportData.minNonzeroDriveTimeHours, Math.floor(increments + 0.5) * reportData.driveTimeRoundingIncrementHours);
    }}
    function formatDistanceTime(distanceMiles) {{
      const hours = estimatedDriveTimeHours(distanceMiles);
      const time = Number.isInteger(hours) ? `${{hours.toFixed(0)}}h` : `${{hours.toFixed(1)}}h`;
      return `${{distanceMiles.toFixed(0)}}/~${{time}}`;
    }}
    function scoreClass(score) {{
      if (score >= 90) return "excellent";
      if (score >= 75) return "good";
      if (score >= 50) return "iffy";
      return "poor";
    }}
    function selectedOrigin() {{
      return reportData.origins.find((origin) => origin.name === originSelect.value) || reportData.origins[0];
    }}
    function areasForDate(dateText) {{
      const origin = selectedOrigin();
      const areas = (reportData.days[dateText] || []).map((area) => ({{
        ...area,
        distance_miles: milesBetween(origin, area),
      }}));
      if (sortByDistance.checked) {{
        areas.sort((a, b) => a.distance_miles - b.distance_miles || b.score - a.score);
      }} else {{
        areas.sort((a, b) => b.score - a.score || a.distance_miles - b.distance_miles);
      }}
      return areas;
    }}
    function scoreTooltip(area) {{
      return `${{area.name}}\\nScore: ${{area.score}}%\\nTemp: ${{area.temp_min_f.toFixed(0)}}-${{area.temp_max_f.toFixed(0)}}F\\nPrecip: ${{area.precipitation_in.toFixed(2)}} in / ${{area.precipitation_probability.toFixed(0)}}%\\nWind: ${{area.wind_mph.toFixed(0)}} mph\\nDistance: ${{formatDistanceTime(area.distance_miles)}}\\n${{area.reasons.join("; ")}}`;
    }}
    function areaLink(area) {{
      const name = escapeHtml(area.name);
      if (!area.mountain_project_url) return name;
      return `<a href="${{escapeHtml(area.mountain_project_url)}}" target="_blank" rel="noopener noreferrer">${{name}}</a>`;
    }}
    function weatherLink(area, text) {{
      const label = escapeHtml(text);
      if (!area.weather_verification_url) return label;
      return `<a href="${{escapeHtml(area.weather_verification_url)}}" target="_blank" rel="noopener noreferrer" title="Verify with NOAA/NWS">${{label}}</a>`;
    }}
    function overviewAreas() {{
      const byName = new Map();
      for (const dateText of reportData.dates) {{
        for (const area of areasForDate(dateText)) {{
          if (!byName.has(area.name)) byName.set(area.name, {{ area, scores: [] }});
          byName.get(area.name).scores.push(area.score);
        }}
      }}
      return Array.from(byName.values())
        .map((entry) => ({{
          ...entry.area,
          averageScore: entry.scores.reduce((sum, score) => sum + score, 0) / entry.scores.length,
        }}))
        .sort((a, b) => b.averageScore - a.averageScore || a.distance_miles - b.distance_miles)
        .slice(0, reportData.overviewTopAreaCount);
    }}
    function renderTabs() {{
      const buttons = [
        `<button type="button" data-view="overview" class="${{activeView === "overview" ? "active" : ""}}">Overview</button>`,
        ...reportData.dates.map((dateText) => `<button type="button" data-view="${{dateText}}" class="${{activeView === dateText ? "active" : ""}}">${{dayLabel(dateText)}}</button>`),
      ];
      tabs.innerHTML = buttons.join("");
      tabs.querySelectorAll("button").forEach((button) => {{
        button.addEventListener("click", () => {{
          activeView = button.dataset.view;
          render();
        }});
      }});
    }}
    function renderOverview() {{
      const topAreas = overviewAreas();
      const rows = topAreas.map((area) => {{
        const cells = reportData.dates.map((dateText) => {{
          const dayArea = areasForDate(dateText).find((candidate) => candidate.name === area.name);
          if (!dayArea) return `<td></td>`;
          return `<td><div class="score-cell ${{scoreClass(dayArea.score)}}" title="${{escapeHtml(scoreTooltip(dayArea))}}">${{dayArea.score}}%</div></td>`;
        }}).join("");
        return `<tr><td><strong>${{areaLink(area)}}</strong><br><span>${{escapeHtml(area.notes)}}</span></td>${{cells}}</tr>`;
      }}).join("");
      overview.innerHTML = `<section class="overview"><h2>Top ${{reportData.overviewTopAreaCount}} Places This Week</h2><table><thead><tr><th>Place</th>${{reportData.dates.map((dateText) => `<th>${{dayLabel(dateText)}}</th>`).join("")}}</tr></thead><tbody>${{rows}}</tbody></table></section>`;
      reportGrid.innerHTML = "";
    }}
    function renderDay(dateText) {{
      const areas = areasForDate(dateText);
      overview.innerHTML = "";
      reportGrid.innerHTML = areas.map((area, index) => {{
        const reasons = escapeHtml(area.reasons.join("; "));
        const temp = `${{area.temp_min_f.toFixed(0)}}-${{area.temp_max_f.toFixed(0)}}F`;
        const precip = `${{area.precipitation_in.toFixed(2)}} in / ${{area.precipitation_probability.toFixed(0)}}%`;
        const wind = `${{area.wind_mph.toFixed(0)}} mph`;
        return `<article class="area-card ${{scoreClass(area.score)}}">
          <div class="rank">#${{index + 1}}</div>
          <div class="area-main"><h2>${{areaLink(area)}}</h2><p class="notes">${{escapeHtml(area.notes)}}</p><p class="reason">${{reasons}}</p></div>
          <div class="score-block"><div class="score">${{area.score}}%</div><div class="score-label">climbable</div></div>
          <dl class="metrics">
            <div><dt>Miles/Time</dt><dd>${{formatDistanceTime(area.distance_miles)}}</dd></div>
            <div><dt>Temp</dt><dd>${{weatherLink(area, temp)}}</dd></div>
            <div><dt>Precip</dt><dd>${{weatherLink(area, precip)}}</dd></div>
            <div><dt>Wind</dt><dd>${{weatherLink(area, wind)}}</dd></div>
          </dl>
        </article>`;
      }}).join("");
    }}
    function renderWarnings() {{
      if (!reportData.errors.length) {{
        warnings.innerHTML = "";
        return;
      }}
      const items = reportData.errors.map((error) => `<li>${{escapeHtml(error)}}</li>`).join("");
      warnings.innerHTML = `<section class="warnings"><h2>Warnings</h2><ul>${{items}}</ul></section>`;
    }}
    function render() {{
      const origin = selectedOrigin();
      const firstDateAreas = areasForDate(reportData.dates[0]);
      originSummary.textContent = origin.name;
      bestSummary.textContent = firstDateAreas.length ? firstDateAreas[0].name : "No areas ranked";
      renderTabs();
      if (activeView === "overview") renderOverview();
      else renderDay(activeView);
      renderWarnings();
    }}
    for (const origin of reportData.origins) {{
      const option = document.createElement("option");
      option.value = origin.name;
      option.textContent = origin.name;
      option.selected = origin.name === reportData.defaultOrigin;
      originSelect.appendChild(option);
    }}
    sortByDistance.checked = reportData.initialSortByDistance;
    originSelect.addEventListener("change", render);
    sortByDistance.addEventListener("change", render);
    render();
  </script>
</body>
</html>
"""


def write_week_html_report(
    rows_by_date: dict[str, list[dict[str, Any]]],
    start_date: dt.date,
    failures: list[str],
    output_path: Path,
    by_distance: bool = False,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    background_path = os.path.relpath(HTML_BACKGROUND_IMAGE_PATH, start=output_path.parent)
    report = render_week_html_report(
        rows_by_date,
        start_date,
        failures,
        background_image_path=Path(background_path).as_posix(),
        by_distance=by_distance,
    )
    output_path.write_text(report, encoding="utf-8")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rank nearby climbing areas by weather climbability for a date."
    )
    parser.add_argument(
        "date",
        nargs="?",
        type=parse_date,
        default=dt.date.today(),
        help="Forecast date in YYYY-MM-DD format; defaults to today",
    )
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    output_group.add_argument(
        "--html",
        nargs="?",
        const="",
        metavar="PATH",
        help="Write a styled HTML report, optionally to PATH",
    )
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
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=CACHE_DIR,
        help="Directory for cached weather API responses",
    )
    args = parser.parse_args(argv)

    if args.html is not None:
        rows_by_date, failures = rank_week(args.date, FOLSOM_CA, refresh=args.refresh, cache_dir=args.cache_dir)
        output_path = Path(args.html) if args.html else Path(DEFAULT_HTML_REPORT_TEMPLATE.format(date=args.date.isoformat()))
        write_week_html_report(rows_by_date, args.date, failures, output_path, by_distance=args.by_distance)
        print(f"Wrote HTML report to {output_path}")
        return 1 if failures and not any(rows_by_date.values()) else 0

    rows = []
    failures = []
    for area in AREAS:
        try:
            rows.append(rank_area(area, args.date, FOLSOM_CA, refresh=args.refresh, cache_dir=args.cache_dir))
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
