import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path

from climb_weather import (
    AREAS,
    cache_path_for,
    climbability_score,
    estimated_drive_time_hours,
    format_distance_time,
    HTML_BACKGROUND_IMAGE_PATH,
    miles_between,
    read_cached_payload,
    render_week_html_report,
    report_dates,
    render_html_report,
    sort_rows,
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

    def test_html_report_escapes_content_and_uses_background(self):
        rows = [sample_ranked_row()]

        report = render_html_report(rows, dt.date(2026, 9, 5), [])

        self.assertIn("assets/local-crag-background.png", report)
        self.assertIn("Test &lt;Crag&gt;", report)
        self.assertIn("Granite \\u0026 trees", report)
        self.assertIn('<script id="report-data" type="application/json">', report)
        self.assertIn('"origins":', report)
        self.assertIn('"Auburn, CA"', report)
        self.assertIn('"Cameron Park, CA"', report)
        self.assertIn('id="origin-select"', report)
        self.assertIn('id="sort-by-distance"', report)

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
        self.assertIn("Sort day reports by distance", report)


def sample_ranked_row(date: str = "2026-09-05"):
    return {
        "name": "Test <Crag>",
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
