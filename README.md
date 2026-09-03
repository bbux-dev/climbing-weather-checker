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

## Cache

Forecast API responses are cached locally in `.weather_cache/` by request URL. Re-running the same date uses cached data unless `--refresh` is passed.
