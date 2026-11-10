
# Ambient Weather · Local station observations

This dashboard contains a weather station table in **2. Weather Conditions & Forecast**, separate from NWS forecasts and CDOT road-weather observations.

**Important:** Ambient Weather REST `/v1/devices` returns stations accessible under the **weather station owner's API key**, not every public station on the AmbientWeather.net community map. Local station owners must grant access; this integration cannot discover arbitrary nearby stations.

## Configure

1. At https://ambientweather.net/account create an Ambient Weather **Application Key** for the integration.
2. Each participating station owner creates an **API Key** and grants permission to use it. Do not put keys in GitHub files, Issues, browser code, or the public JSON feed.
3. In repository **Settings → Secrets and variables → Actions**, set:
   - `AMBIENT_APPLICATION_KEY`: application credential.
   - `AMBIENT_API_KEYS`: one or more owner API keys, comma-separated.
   - `AMBIENT_STATION_NAMES`: JSON object with **authorized station MACs** as keys and approved **public display labels** as values, e.g. `{"AA:BB:CC:DD:EE:FF":"Silverton – Public Station"}` (example MAC only).
4. Run GitHub Actions → **Refresh authorized Ambient Weather stations** → **Run workflow** after merging. The scheduled task polls approximately every hour, subject to GitHub scheduling delay.
5. Confirm the dashboard shows observation timestamps and the station reports as **Current** only if its latest observation is 30 minutes old or less.

## Public Ambient Weather stations — access policy

Ambient's community website permits manual viewing of public stations, but the published Nielsen-Kellerman terms prohibit ongoing automated scraping without prior written permission. Do **not** attempt to harvest public map data, undocumented endpoints or browser session payloads for this dashboard.

The hourly GitHub workflow is an authorized API integration only. To access public stations automatically, obtain written permission and an approved access method from Ambient Weather, or obtain participating station-owner API keys. Until then, the dashboard shows a transparent unconfigured state and links to the public map for manual review.

Source terms: https://ambientweather.com/terms (Content — Limitations on Use).
Official API: https://github.com/ambient-weather/api-docs/blob/master/apiary.apib

## Published fields

Only authorized station name, observation time, outdoor temperature (°F), humidity (%), wind speed/gust (mph), previous-hour rainfall (in), and **daily cumulative rainfall (in)** are written to `data/ambient_stations.json`. Source address, coordinates, station MAC and keys are not published.

The public JSON feed is not a secure data store. Do not add private station metadata or sensitive location labels.

The dashboard refreshes its *snapshot* on load and roughly every 5 minutes while open. Refreshing the page **does not** query Ambient directly or speed up the server-side polling. Stale status reflects the station observation age, not simply the file age.

If owner credentials are not supplied, the table remains visible with a clear **Awaiting authorized local station connections** message. A blank table is **not** evidence of benign weather.

Reference: https://ambientweather.docs.apiary.io/ — REST authentication and GET /v1/devices.

For incident operations, treat personally maintained stations as supplemental observations; verify significant values using NWS and other official sources.
