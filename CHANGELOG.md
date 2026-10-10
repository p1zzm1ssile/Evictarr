# CHANGELOG

## 0.3.0 (Evictarr)

`October 10 2026`

First release as Evictarr, a community-maintained fork of [Purgarr](https://github.com/steveharsant/purgarr) by Steve Harsant. Everything below 0.3.0 is Steve's original Purgarr history.

### Features

* Added `IGNORE_OTHER_CATEGORIES` option. When `True`, the stalled purge only touches downloads whose category is listed in `SONARR_LABELS` (for Sonarr) or `RADARR_LABELS` (for Radarr), so downloads in any other category are never removed or blocklisted.

* Added Deluge support (Deluge 1.3 and 2.x, through the Web UI). Set `DOWNLOAD_CLIENT=deluge` along with `DELUGE_URL` and `DELUGE_PASSWORD` ([#5](https://github.com/steveharsant/purgarr/issues/5)).
* Added Transmission support. Set `DOWNLOAD_CLIENT=transmission` along with `TRANSMISSION_URL`, and `TRANSMISSION_USER`/`TRANSMISSION_PASSWORD` if needed ([#9](https://github.com/steveharsant/purgarr/issues/9)).
* Added SABnzbd support. Set `DOWNLOAD_CLIENT=sabnzbd` along with `SABNZBD_URL` and `SABNZBD_API_KEY`. A Usenet download counts as stalled when it has made no progress for `TORRENT_AGE` minutes ([#6](https://github.com/steveharsant/purgarr/issues/6)).
* Added RDTClient support with `DOWNLOAD_CLIENT=rdtclient`, using the `QBIT_*` settings ([#13](https://github.com/steveharsant/purgarr/issues/13)).
* Added `PURGE_FAILED_IMPORTS` (off by default) to remove and blocklist downloads Sonarr/Radarr couldn't import, and search for a replacement ([#13](https://github.com/steveharsant/purgarr/issues/13)).
* Added `PURGE_EXTENSIONS`: downloads Sonarr/Radarr are tracking that contain blocked file types (`BLOCKED_EXTENSIONS`, default `arj,lnk,exe,bat,cmd,com,scr,pif,vbs,ps1`) are blocklisted, removed and their files deleted, so a clean release is searched for. Checked every `PURGE_EXTENSIONS_INTERVAL` seconds (default 60). Works with every supported client. Requested by binhex ([#4](https://github.com/steveharsant/purgarr/issues/4)).
* Added a health check: a status bar in the web UI, a `/health` endpoint, `healthcheck.py` and a Docker `HEALTHCHECK` ([#14](https://github.com/steveharsant/purgarr/issues/14)).
* Clearer logs: every check now logs one line saying what it found and did, for example "Sonarr check: purged 2 stalled download(s), blocklisted 2 in Sonarr (next check in 300s)", or why it failed ([#14](https://github.com/steveharsant/purgarr/issues/14)).
* `DOWNLOAD_CLIENT` can be used instead of `TORRENT_CLIENT`, and `REQUEST_TIMEOUT` sets how long to wait for a response (default 30 seconds).

### Bugfixes

* Label lists are now trimmed of whitespace, so the default `IMPORT_LABELS` value matches `radarr-imported` (it previously ended up as ` radarr-imported` and never matched).
* Fixed qBittorrent 5.2+ login: the session cookie is now `QBT_SID_<port>` instead of `SID`, which caused "SID cookie not found in response" ([#16](https://github.com/steveharsant/purgarr/issues/16)).
* Stalled torrents are now blocklisted in Sonarr/Radarr *before* being removed from qBittorrent, and are matched to the Arr queue by torrent hash (falling back to title) across every queue page, not just the first. Previously a stalled release often wasn't found, so no replacement search was triggered ([#12](https://github.com/steveharsant/purgarr/issues/12)).
* RDTClient logins without a session cookie (when its authentication is off) are no longer treated as failures, and an expired qBittorrent session is renewed straight away instead of failing until the next refresh.
* An error during a check (for example Sonarr being unreachable) no longer stops that check for good. It is logged, shown in the health status, and the check runs again next interval.
* If the Sonarr/Radarr queue can't be read, stalled downloads are kept until the next run instead of being removed without a blocklist and replacement search.
* Every request now has a timeout, so an unresponsive server can't hang a check forever.
* Log lines in the web UI are now HTML-escaped, so a download name can't inject markup into the page.
* `.env.tmpl` used `SONARR_IMPORT_LABEL`/`RADARR_IMPORT_LABEL`, which Purgarr never read. They are now `SONARR_IMPORTED_LABEL`/`RADARR_IMPORTED_LABEL`.
* The Sonarr and Radarr stalled daemons no longer share one `self.service`, which meant whichever thread started last was used by both.

## 0.2.0

`June 6 2025`

### Features

* Added basic webUI to watch logs.
  * Made log out put autoscroll.
  * Added colourisation of logs.
  * Added `WEB_HOST` and `WEB_PORT` envvar options.
* Added log stream output options. (Configurable with `LOG_OUTPUT`)
* Added new log level type: `ACTION`
* Improved log messages defining which torrents are being actioned.

## 0.1.2

`May 27 2025`

* **Bugfix:** Various minor bugfixes

## 0.1.1

`May 27 2025`

* **Bugfix:** Prepend http(s) protocol before host string of *arr stack to not cause initalisation errors.

## 0.1.0

`May 26 2025`

* Initial release
