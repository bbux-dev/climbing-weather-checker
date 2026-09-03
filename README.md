# Climbing Weather Checker

Prototype CLI for ranking nearby climbing areas by forecast climbability.

## Usage

```bash
./climb_weather.py 2026-09-05
```

Machine-readable output:

```bash
./climb_weather.py 2026-09-05 --json
```

Sort by distance from Folsom first:

```bash
./climb_weather.py 2026-09-05 --by-distance
```

Write a styled HTML report:

```bash
./climb_weather.py --html
./climb_weather.py 2026-09-05 --html
./climb_weather.py 2026-09-05 --html reports/saturday.html
```

Refresh cached weather data:

```bash
./climb_weather.py 2026-09-05 --refresh
```

## Scoring

The baseline rule is:

- dry forecast and max temperature `<= 75F` gives `100%`
- precipitation amount, precipitation probability, heat above `75F`, cold highs below `45F`, and strong wind subtract from the score

Results are sorted by highest climbability, then shortest straight-line distance from Folsom, CA.
The `Miles/Time` column shows straight-line miles plus a rough drive-time estimate using `miles / 35`, rounded to the nearest half hour.

Weather data comes from Open-Meteo's no-key forecast API.

## HTML Reports

`--html` writes a 7-day local report file using `assets/local-crag-background.png` for the climbing-themed background. When no path is passed, the file is named `climb-weather-YYYY-MM-DD.html`.
The report opens on a week overview grid showing the top 5 places as rows and the next 7 dates as columns. Cells are color-coded by climbability score, and hovering over a cell shows weather, distance, and scoring details.

The report embeds its weather and crag data as JSON, so the page can recalculate distances locally. Use the page controls to switch the origin between Folsom, Auburn, and Cameron Park, or to sort day reports by distance. Click a day tab to show that date's full report.

## Cache

Forecast API responses are cached locally in `.weather_cache/` by request URL. Re-running the same date or 7-day HTML range uses cached data unless `--refresh` is passed.
