import datetime as dt
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from climb_weather import (
    AREAS,
    cache_path_for,
    ClimbingType,
    ClimingType,
    climbability_score,
    estimated_drive_time_hours,
    filter_areas_by_climbing_type,
    format_distance_time,
    HTML_BACKGROUND_IMAGE_PATH,
    ClimbingArea,
    forecast_url,
    fetch_forecast,
    forecast_start_for_area,
    miles_between,
    rank_area,
    rank_area_from_daily,
    read_cached_payload,
    ROCK_TYPE_BASALT,
    ROCK_TYPE_SANDSTONE,
    render_week_html_report,
    parse_climbing_types,
    report_dates,
    render_html_report,
    sandstone_wet_weather_checker,
    sort_rows,
    weather_verification_url,
    write_html_report,
    write_cached_payload,
)


class ClimbabilityScoreTest(unittest.TestCase):
    def test_dry_and_75_or_cooler_is_100_percent(self):
        score, reasons = climbability_score(
            temp_max_f=75,
            precipitation_in=0,
            precipitation_probability=0,
            wind_mph=10,
        )

        self.assertEqual(score, 100)
        self.assertEqual(reasons, ["dry and <= 75F"])

    def test_heat_reduces_score(self):
        score, reasons = climbability_score(
            temp_max_f=80,
            precipitation_in=0,
            precipitation_probability=0,
            wind_mph=10,
        )

        self.assertEqual(score, 80)
        self.assertIn("high 80F", reasons)

    def test_rain_reduces_score(self):
        score, reasons = climbability_score(
            temp_max_f=70,
            precipitation_in=0.25,
            precipitation_probability=50,
            wind_mph=10,
        )

        self.assertLess(score, 100)
        self.assertIn("0.25 in precip", reasons)

    def test_folsom_to_nearby_point_distance(self):
        self.assertAlmostEqual(miles_between((38.67796, -121.17606), (38.67796, -121.17606)), 0)

    def test_estimated_drive_time_rounds_to_half_hours(self):
        self.assertEqual(estimated_drive_time_hours(0), 0)
        self.assertEqual(estimated_drive_time_hours(2), 0.5)
        self.assertEqual(estimated_drive_time_hours(48), 1.5)
        self.assertEqual(estimated_drive_time_hours(60), 1.5)
        self.assertEqual(estimated_drive_time_hours(112), 3)

    def test_format_distance_time(self):
        self.assertEqual(format_distance_time(2), "2/~0.5h")
        self.assertEqual(format_distance_time(112), "112/~3h")
        self.assertEqual(format_distance_time(60), "60/~1.5h")

    def test_auburn_quarry_is_included(self):
        auburn_quarry = next(area for area in AREAS if area.name == "Auburn Quarry (Auburn, CA)")

        self.assertAlmostEqual(auburn_quarry.lat, 38.91231)
        self.assertAlmostEqual(auburn_quarry.lon, -121.03567)

    def test_castle_rock_is_sandstone(self):
        castle_rock = next(area for area in AREAS if area.name == "Castle Rock State Park")

        self.assertEqual(castle_rock.rock_type, ROCK_TYPE_SANDSTONE)

    def test_all_areas_have_mountain_project_links(self):
        for area in AREAS:
            self.assertTrue(area.mountain_project_url.startswith("https://www.mountainproject.com/"))

    def test_climing_type_alias_matches_corrected_enum_name(self):
        self.assertIs(ClimingType, ClimbingType)

    def test_sacramento_area_bouldering_locations_are_included(self):
        expected = {
            "Rocklin (Deer Creek Park)": (38.78712, -121.24077),
            "Giant Boulder Park (Rocklin, CA)": (38.83052, -121.257),
            "The Nut Tree Boulders (Vacaville, CA)": (38.38524, -121.98691),
            "Putah Creek (Vacaville, CA)": (38.5174, -122.056),
            "Pie Shop Bouldering (South Lake Tahoe, CA)": (38.87495, -120.01322),
        }

        for name, coords in expected.items():
            area = next(area for area in AREAS if area.name == name)
            self.assertEqual(area.climbing_types, (ClimbingType.BOULDER,))
            self.assertAlmostEqual(area.lat, coords[0])
            self.assertAlmostEqual(area.lon, coords[1])

    def test_mount_tam_boulders_is_included(self):
        mount_tam = next(area for area in AREAS if area.name == "Mount Tam Boulders (Mill Valley, CA)")

        self.assertEqual(mount_tam.climbing_types, (ClimbingType.BOULDER,))
        self.assertAlmostEqual(mount_tam.lat, 37.91055)
        self.assertAlmostEqual(mount_tam.lon, -122.59474)
        self.assertEqual(mount_tam.rock_type, ROCK_TYPE_BASALT)

    def test_default_climbing_type_filter_excludes_boulder_only_locations(self):
        selected_types = parse_climbing_types(None)
        areas = filter_areas_by_climbing_type(AREAS, selected_types)

        self.assertNotIn("Rocklin (Deer Creek Park)", [area.name for area in areas])
        self.assertIn("Auburn Quarry (Auburn, CA)", [area.name for area in areas])

    def test_boulder_climbing_type_filter_includes_boulder_locations(self):
        selected_types = parse_climbing_types(["boulder"])
        areas = filter_areas_by_climbing_type(AREAS, selected_types)

        self.assertIn("Rocklin (Deer Creek Park)", [area.name for area in areas])
        self.assertIn("Pie Shop Bouldering (South Lake Tahoe, CA)", [area.name for area in areas])
        self.assertNotIn("Auburn Quarry (Auburn, CA)", [area.name for area in areas])

    def test_all_climbing_type_filter_includes_boulder_only_locations(self):
        selected_types = parse_climbing_types(["all"])
        areas = filter_areas_by_climbing_type(AREAS, selected_types)

        self.assertIn("Rocklin (Deer Creek Park)", [area.name for area in areas])
        self.assertIn("Auburn Quarry (Auburn, CA)", [area.name for area in areas])

    def test_weather_verification_url_uses_noaa_point_forecast(self):
        auburn_quarry = next(area for area in AREAS if area.name == "Auburn Quarry (Auburn, CA)")

        url = weather_verification_url(auburn_quarry)

        self.assertEqual(url, "https://forecast.weather.gov/MapClick.php?lat=38.91231&lon=-121.03567")

    def test_sandstone_forecast_start_includes_dryout_lookback(self):
        castle_rock = next(area for area in AREAS if area.name == "Castle Rock State Park")
        auburn_quarry = next(area for area in AREAS if area.name == "Auburn Quarry (Auburn, CA)")
        start_date = dt.date(2026, 9, 5)

        self.assertEqual(forecast_start_for_area(castle_rock, start_date), dt.date(2026, 9, 3))
        self.assertEqual(forecast_start_for_area(auburn_quarry, start_date), start_date)

    def test_sandstone_wet_weather_checker_blocks_two_days_after_rain(self):
        castle_rock = next(area for area in AREAS if area.name == "Castle Rock State Park")
        daily = {
            "time": ["2026-09-03", "2026-09-04", "2026-09-05", "2026-09-06"],
            "precipitation_sum": [0.01, 0, 0, 0],
        }

        reason = sandstone_wet_weather_checker(castle_rock, dt.date(2026, 9, 5), daily)

        self.assertEqual(reason, "sandstone wet weather: 2 day(s) after rain")
        self.assertIsNone(sandstone_wet_weather_checker(castle_rock, dt.date(2026, 9, 6), daily))

    def test_sandstone_wet_weather_checker_sets_score_to_zero(self):
        castle_rock = next(area for area in AREAS if area.name == "Castle Rock State Park")
        daily = {
            "time": ["2026-09-03", "2026-09-04", "2026-09-05"],
            "temperature_2m_max": [70, 70, 70],
            "temperature_2m_min": [50, 50, 50],
            "precipitation_sum": [0.01, 0, 0],
            "precipitation_probability_max": [0, 0, 0],
            "wind_speed_10m_max": [8, 8, 8],
        }

        row = rank_area_from_daily(castle_rock, dt.date(2026, 9, 5), daily, 2, (38.0, -121.0))

        self.assertEqual(row["score"], 0)
        self.assertEqual(row["reasons"], ["sandstone wet weather: 2 day(s) after rain"])

    def test_report_dates_returns_next_seven_days(self):
        dates = report_dates(dt.date(2026, 9, 5))

        self.assertEqual(len(dates), 7)
        self.assertEqual(dates[0], dt.date(2026, 9, 5))
        self.assertEqual(dates[-1], dt.date(2026, 9, 11))

    def test_default_sort_is_score_then_distance(self):
        rows = [
            {"name": "A", "score": 80, "distance_miles": 10},
            {"name": "B", "score": 100, "distance_miles": 50},
            {"name": "C", "score": 100, "distance_miles": 20},
        ]

        sort_rows(rows)

        self.assertEqual([row["name"] for row in rows], ["C", "B", "A"])

    def test_by_distance_sort_is_distance_then_score(self):
        rows = [
            {"name": "A", "score": 80, "distance_miles": 10},
            {"name": "B", "score": 100, "distance_miles": 50},
            {"name": "C", "score": 100, "distance_miles": 20},
        ]

        sort_rows(rows, by_distance=True)

        self.assertEqual([row["name"] for row in rows], ["A", "C", "B"])

    def test_cache_round_trip_uses_url_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            url = "https://example.test/weather?date=2026-09-05&lat=1"
            payload = {"daily": {"time": ["2026-09-05"]}}

            write_cached_payload(url, payload, cache_dir)

            self.assertTrue(cache_path_for(url, cache_dir).exists())
            self.assertEqual(read_cached_payload(url, cache_dir), payload)

    def test_invalid_cache_returns_none(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            url = "https://example.test/weather?date=2026-09-05&lat=1"
            cache_path_for(url, cache_dir).write_text("not json", encoding="utf-8")

            self.assertIsNone(read_cached_payload(url, cache_dir))

    def test_rank_area_uses_custom_cache_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            area = ClimbingArea("Cached Crag", 38.0, -121.0, "test", "https://www.mountainproject.com/")
            date = dt.date(2026, 9, 5)
            payload = {
                "daily": {
                    "time": [date.isoformat()],
                    "temperature_2m_max": [70],
                    "temperature_2m_min": [50],
                    "precipitation_sum": [0],
                    "precipitation_probability_max": [0],
                    "wind_speed_10m_max": [8],
                }
            }
            write_cached_payload(forecast_url(area, date, date), payload, cache_dir)

            row = rank_area(area, date, (38.0, -121.0), cache_dir=cache_dir)

            self.assertEqual(row["score"], 100)
            self.assertEqual(row["name"], "Cached Crag")

    def test_refresh_falls_back_to_cache_when_api_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            area = ClimbingArea("Cached Crag", 38.0, -121.0, "test", "https://www.mountainproject.com/")
            date = dt.date(2026, 9, 5)
            payload = {"daily": {"time": [date.isoformat()]}}
            write_cached_payload(forecast_url(area, date, date), payload, cache_dir)

            with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
                daily = fetch_forecast(area, date, date, refresh=True, cache_dir=cache_dir)

            self.assertEqual(daily, payload["daily"])

    def test_html_report_escapes_content_and_uses_background(self):
        rows = [sample_ranked_row()]

        report = render_html_report(rows, dt.date(2026, 9, 5), [])

        self.assertIn("assets/local-crag-background.png", report)
        self.assertIn("Test &lt;Crag&gt;", report)
        self.assertIn("Granite \\u0026 trees", report)
        self.assertIn("https://www.mountainproject.com/area/test-crag", report)
        self.assertIn("https://forecast.weather.gov/MapClick.php?lat=38.00000\\u0026lon=-121.00000", report)
        self.assertIn('<script id="report-data" type="application/json">', report)
        self.assertIn('"origins":', report)
        self.assertIn('"Auburn, CA"', report)
        self.assertIn('"Cameron Park, CA"', report)
        self.assertIn('"allClimbingTypes":', report)
        self.assertIn('"selectedClimbingTypes":', report)
        self.assertIn('id="origin-select"', report)
        self.assertIn('id="sort-by-distance"', report)
        self.assertIn('id="type-controls"', report)
        self.assertIn("matchesSelectedTypes", report)

    def test_write_html_report_creates_parent_and_relative_background_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "reports" / "saturday.html"

            write_html_report([sample_ranked_row()], dt.date(2026, 9, 5), [], output_path)

            report = output_path.read_text(encoding="utf-8")
            expected_background_path = Path(
                os.path.relpath(HTML_BACKGROUND_IMAGE_PATH, start=output_path.parent)
            ).as_posix()
            self.assertTrue(output_path.exists())
            self.assertIn(expected_background_path, report)

    def test_week_html_report_embeds_days_overview_and_tabs(self):
        start_date = dt.date(2026, 9, 5)
        dates = [date.isoformat() for date in report_dates(start_date)]
        rows_by_date = {date: [sample_ranked_row(date)] for date in dates}

        report = render_week_html_report(rows_by_date, start_date, [])

        self.assertIn('"days":', report)
        self.assertIn('"dates":', report)
        self.assertIn("Top ${reportData.overviewTopAreaCount} Places This Week", report)
        self.assertIn('data-view="overview"', report)
        self.assertIn("scoreTooltip", report)
        self.assertIn("areaLink", report)
        self.assertIn("weatherLink", report)
        self.assertIn('id="type-controls"', report)
        self.assertIn('"allClimbingTypes":', report)
        self.assertIn('"selectedClimbingTypes":', report)
        self.assertIn("matchesSelectedTypes", report)
        self.assertIn('target="_blank"', report)
        self.assertIn('rel="noopener noreferrer"', report)
        self.assertIn("Sort day reports by distance", report)


def sample_ranked_row(date: str = "2026-09-05"):
    return {
        "name": "Test <Crag>",
        "mountain_project_url": "https://www.mountainproject.com/area/test-crag",
        "weather_verification_url": "https://forecast.weather.gov/MapClick.php?lat=38.00000&lon=-121.00000",
        "rock_type": "granite",
        "climbing_types": ["sport"],
        "date": date,
        "lat": 38.0,
        "lon": -121.0,
        "score": 100,
        "distance_miles": 35,
        "temp_max_f": 70,
        "temp_min_f": 50,
        "precipitation_in": 0,
        "precipitation_probability": 0,
        "wind_mph": 8,
        "reasons": ["dry and <= 75F"],
        "notes": "Granite & trees",
    }


if __name__ == "__main__":
    unittest.main()
