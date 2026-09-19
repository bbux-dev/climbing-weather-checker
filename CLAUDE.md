# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this project is

A single-file Python CLI (`climb_weather.py`) that ranks local climbing areas by forecast
"climbability" using the Open-Meteo no-key forecast API. It prints a table, can emit JSON, and can
render a styled 7-day HTML report that GitHub Actions publishes to GitHub Pages.

No dependencies beyond the Python 3.12 standard library. Do not add third-party packages.

## Layout

| Path | Purpose |
| --- | --- |
| `climb_weather.py` | Everything: area list, scoring, caching, CLI, HTML rendering |
| `test_climb_weather.py` | `unittest` suite, run with `python3 -m unittest` |
| `.github/workflows/pages.yml` | Runs tests, builds `site/index.html`, deploys to Pages |
| `assets/local-crag-background.png` | Background image copied into the published site |
| `CHANGELOG.md` | User-facing changes; add to `## Unreleased` → `### Added` |
| `README.md` | Usage docs |
| `LESSON.md` | Narrative walkthrough of how the app was built, for non-programmers |

`.weather_cache/`, `reports/`, and `site/` are generated and gitignored.

## Commands

```bash
python3 -m unittest -v                 # full test suite (no network needed)
./climb_weather.py 2026-09-19          # ranked table for a date
./climb_weather.py 2026-09-19 --json   # machine-readable
./climb_weather.py --types boulder     # filter by climbing type
./climb_weather.py --html reports/x.html   # 7-day HTML report
./climb_weather.py 2026-09-19 --refresh    # bypass the cache
```

Live runs hit Open-Meteo and write to `.weather_cache/` keyed by request URL. Tests never hit the
network — they patch `urllib.request.urlopen` or feed `rank_area_from_daily` fixture dicts.

## Adding a climbing area

This is the most common request ("add weather for <Mountain Project URL>"). Steps:

1. **Fetch the Mountain Project page** (WebFetch) for the area's GPS coordinates, rock type, and
   which disciplines it has. Use MP's own decimal lat/lon — do not guess coordinates.
2. **Append a `ClimbingArea` to the `AREAS` list** in `climb_weather.py`. Keep the list grouped the
   way it already reads: roped crags first, boulder-only areas at the end. Example:

   ```python
   ClimbingArea(
       name="Mount Tam Boulders (Mill Valley, CA)",
       lat=37.91055,
       lon=-122.59474,
       notes="Marin volcanic bouldering",
       mountain_project_url="https://www.mountainproject.com/area/106326205/mount-tam-boulders",
       climbing_types=(ClimbingType.BOULDER,),
       rock_type=ROCK_TYPE_BASALT,
   ),
   ```

   - `name`: `"Area Name (Town, CA)"` when the town is not already obvious in the name.
   - `notes`: a short phrase, usually `"<region> <rock> <discipline>"`.
   - `climbing_types`: a tuple of `ClimbingType` members, or `ALL_CLIMBING_TYPES`. Omit it to get
     `DEFAULT_CLIMBING_TYPES` (sport, trad, top-rope). A boulder-only area is
     `(ClimbingType.BOULDER,)` and is hidden unless the user passes `--types boulder` or `--types all`.
   - `rock_type`: one of the `ROCK_TYPE_*` constants; defaults to granite. This only changes
     behavior for `ROCK_TYPE_SANDSTONE`, which forces a `0%` score on rain days and for
     `SANDSTONE_DRYOUT_DAYS_AFTER_RAIN` days after. Map volcanic rock to `ROCK_TYPE_BASALT`; only
     introduce a new `ROCK_TYPE_*` constant if it comes with a scoring rule.
3. **Add a test** in `test_climb_weather.py` next to the other area tests, asserting the
   coordinates, climbing types, and rock type. Add any new import to the `from climb_weather import`
   block (it is alphabetized-ish — keep it tidy).
4. **Add a `CHANGELOG.md` line** under `## Unreleased` → `### Added`.
5. **Verify**: `python3 -m unittest -q`, then run the CLI with a type filter that includes the new
   area and confirm it appears with a plausible score and distance.

README only needs an edit if the change affects usage, not for a new area.

## Conventions

- Named module-level constants instead of magic numbers — every scoring threshold and penalty is a
  constant near the top of the file. Follow that when adding rules.
- `ClimbingArea` is a frozen dataclass; areas are static data in the source, not config. The
  CHANGELOG lists "make climbing areas configurable outside the script" as planned — do not do that
  unless asked.
- Distances are straight-line from an origin in `ORIGINS`, with drive time estimated as
  `miles / ESTIMATED_TRAVEL_SPEED_MPH` rounded to half hours. Also listed as planned work: real
  driving distance.
- HTML is built with string concatenation and `html.escape`; report data is embedded as JSON so the
  page can re-sort, re-filter, and change origin client-side without a server.
- Keep the code readable for a non-programmer audience — `LESSON.md` teaches this repo as an example
  of building an app with an LLM. Prefer plain, explicit code over clever code.

## Before finishing

Run `python3 -m unittest -v`. The Pages workflow runs the same suite and will block a deploy on
failure. Do not commit or push unless asked.
