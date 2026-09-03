import tempfile
import unittest
from pathlib import Path

from climb_weather import (
    cache_path_for,
    climbability_score,
    estimated_drive_time_hours,
    format_distance_time,
    miles_between,
    read_cached_payload,
    sort_rows,
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
        self.assertEqual(estimated_drive_time_hours(48), 1.5)
        self.assertEqual(estimated_drive_time_hours(60), 1.5)
        self.assertEqual(estimated_drive_time_hours(112), 3)

    def test_format_distance_time(self):
        self.assertEqual(format_distance_time(112), "112/~3h")
        self.assertEqual(format_distance_time(60), "60/~1.5h")

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


if __name__ == "__main__":
    unittest.main()
