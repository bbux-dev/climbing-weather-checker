# Changelog

This project tracks user-facing climbing weather features as they are added.

## Unreleased

### Added

- Link crag names in HTML reports to their Mountain Project area pages.
- Link weather values in HTML reports to NOAA/NWS point forecasts for verification.
- Add sandstone wet-weather protection that forces sandstone areas to `0%` on rain days and for the next 2 days after rain.
- Mark Castle Rock State Park as sandstone.
- Add climbing type metadata for sport, trad, top-rope, and bouldering.
- Add `--types` filtering with boulder-only areas excluded by default.
- Add Sacramento-area bouldering locations for Rocklin, Giant Boulder Park, Nut Tree Boulders, Putah Creek, and Pie Shop Bouldering.
- Add Mount Tam Boulders (Mill Valley, CA) as a Marin volcanic bouldering location.

## 2026-09-03

### Added

- Add prototype CLI for ranking local climbing areas by forecast climbability.
- Add Open-Meteo forecast integration with local response caching and `--refresh`.
- Add `--by-distance` sorting.
- Add `Miles/Time` output using `miles / 35`, rounded to half-hour increments.
- Add local climbing areas including Donner Summit, Sugar Loaf, Cosumnes River Gorge, Lovers Leap, South Lake Tahoe, The Emeralds, The Grotto, Yosemite Valley, Castle Rock State Park, and Auburn Quarry.
- Add `--html` CLI output that writes a styled climbing weather report.
- Use a climbing-themed local crag background image for the HTML report.
- Embed report data in HTML and support in-page origin changes from Folsom, Auburn, and Cameron Park.
- Add in-page distance sorting for HTML reports.
- Add 7-day HTML forecast reports with day tabs.
- Add a week overview grid with top 5 places by date and hover details.
- Add GitHub Pages publishing through GitHub Actions.
- Add resilient Pages builds that fall back to cached weather data if refresh fails.

## Planned

- Replace straight-line distance and rough time estimates with real driving distance and duration.
- Make climbing areas configurable outside the script.
