# CHANGELOG

## Unreleased

- **File blocking now checks every download in the queue.** Only the first 10 Sonarr/Radarr queue items were being read, so a download further down (for example one containing an `.exe`) was never checked. Radarr downloads it can't match to a movie are now checked too, as Sonarr's already were.
- **The stalled grace period now counts how long a download has been stalled**, not how long ago it was added. Before, a torrent added more than 5 minutes earlier was purged, blocklisted and replaced the first time a check found it stalled, even for a moment, so slow torrents for older releases were replaced again and again. A download that starts moving again starts the count again. The default grace period for new installs is now 60 minutes; an existing install keeps its saved value, so raise it under **Settings > General > Stalled downloads**.
- **Keys and passwords are kept out of the logs.** Any API key or password, and any `apikey=`, `token=` or `password=` in a web address quoted by an error, is replaced by `***` before it's written. Log files, and the file that holds the login, can now only be read by the account the app runs as. A download client that can't remove a torrent no longer shows its raw error, which for SABnzbd could include the API key.

## 0.4.5

`October 13 2026`

### Changes

* Addresses for download clients, Sonarr, Radarr, Prowlarr and Jackett start empty on a new install, with an example such as `http://192.168.1.10:8080`, instead of `localhost`, which inside a container is the container itself.
* Addresses must start with `http://` or `https://`. Addresses saved before this get `http://` added by themselves, so nothing needs re-entering.

## 0.4.4

`October 12 2026`

### Features

* **Remove downloads by hand** from the Downloads page: tick them and choose **Remove…**. Choose whether to delete their files, and whether to blocklist the ones Sonarr/Radarr are tracking so a replacement is searched for. Each removal is logged with who did it.
* **Run checks now** button on the Downloads page.
* **Help & contact** page: report a problem with a pre-filled GitHub issue, suggest an idea, check the version, and find the changelog and guide.

### Bugfixes

* Deluge: if its Web UI lost the connection to its daemon (Deluge restarted, or Disconnect clicked in its Connection Manager), every call hung until it timed out. Evictarr now checks the connection and reconnects by itself.


## 0.4.3

`October 12 2026`

* New Evictarr logo, in the web UI, the browser tab, the README and the Unraid icon.


## 0.4.2

`October 11 2026`

### Features

* **Samples and languages** on the Blocking tab:
  * **Don't download sample files.**
  * **My languages**, chosen with tick boxes.
  * **Only keep subtitles and extra audio in my languages**: separate subtitle and audio files in other languages are skipped, read from file names like `Movie.fr.srt`, `Subs/3_French.srt` or `Movie.ger.dts`. Audio files only count next to a video, so music is untouched. Files with no language in the name are kept unless you turn that off.
  * **Reject releases tagged with another language**, such as `GERMAN` after the title, unless also tagged `MULTi` or with one of your languages. Title words like "Italian" in *The Italian Job* don't count.
* Skipped files are logged with their reason, e.g. `3_French.srt (subtitle in French)`, and the Downloads page shows it per file.


## 0.4.1

`October 11 2026`

Fixes from a code review of 0.4.0.

### Security

* Creating the first account now needs a one-time **setup code** printed in Evictarr's log. Being on the local network wasn't proof enough: a reverse proxy that adds no forwarding headers, or Docker's port forwarding, can make an internet visitor look local.
* **Skip login on my local network** now only applies to the networks listed in the new **My local networks** setting (default `192.168.0.0/16, 10.0.0.0/8`), which leaves out Docker's own range.
* A saved password or API key is no longer reused when its address changes, in **Test connection** or when saving. Before, it could be sent to any server typed into the address field.
* The login lockout counts each attempt before checking the password, so many attempts sent at once can't get past it. Failures are forgotten after 15 minutes.

### Bugfixes

* Saving settings could briefly expose half-applied values to a running check. In the worst case, a name pattern like `*sample*` was read as text, matched every file, and every tracked download was rejected. Settings are now worked out in full before any of them change.
* With `IGNORE_OTHER_CATEGORIES` off, the Sonarr check could remove Radarr's stalled downloads (and the reverse) before they were blocklisted, so no replacement was searched for. Each check now only removes its own downloads, and ones belonging to neither are handled once.
* A download removed by hand between being listed and being purged no longer stops the rest of the batch from being removed, and a failure in one client doesn't stop removals from the others.
* The health status file is written atomically, so the Docker health check can't read half a file, and an unreadable file is reported cleanly.
* A damaged `settings.json` is moved aside and reported, instead of being silently replaced by defaults on the next save.
* An `IMPORT_LABELS` environment variable no longer overrides the post-import categories set in the web UI. It's copied into them on first start instead.
* The Logs page only reads the end of the log file, and the account file is read once instead of on every request.


## 0.4.0

`October 11 2026`

### Features

* **Web UI for everything.** Settings are made in the browser and saved to `/config/settings.json`, and changes apply as soon as you save, with no restart. Existing environment variables are copied in on first start.
  * **Settings** tabs for General, Blocking, Sonarr, Radarr, Download clients and Indexers, each with its own **Save** button and **Test connection** buttons.
  * Ticked groups (malware, archives, disc images, ROMs and so on) for file blocking and skipping.
* **Login.** The first account is created in the browser, from your local network only. Passwords need at least 8 characters, with an uppercase letter, a lowercase letter, a number and a special character, and are stored as scrypt hashes. 5 wrong attempts lock an address out for 5 minutes. An optional **skip login on my local network** never applies to requests through a reverse proxy. The login page warns against exposing Evictarr to the internet.
* **Downloads** start page: every download in every client, which of Sonarr/Radarr tracks it and from which indexer, and its files, marked with whether each will be blocked or skipped.
* **Logs** page with **Issues** (errors and warnings) and **Actions** filters, search, and **Download all logs** as a zip.
* **Several download clients at once.** Tick any combination of qBittorrent, RDTClient, Deluge, Transmission and SABnzbd. If one is down, the others keep being checked. RDTClient now has its own settings, so it can run alongside qBittorrent.
* **Prowlarr and Jackett** (optional): indexer health on the Downloads page, and rejected releases name the indexer they came from in the logs.
* An Unraid template in `unraid/evictarr.xml`, and the image now has a `/config` volume.

### Changes

* Evictarr no longer exits when a download client can't be reached at startup. It keeps running so you can fix the settings in the web UI.
* Log files are kept in `/config/logs`, with the last 5 rotated files.


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
* Added file blocking and skipping (`PURGE_FILES`, or `PURGE_EXTENSIONS`), checked every `PURGE_EXTENSIONS_INTERVAL` seconds (default 60) on downloads Sonarr/Radarr are tracking, with every supported client:
  * **Block:** a download containing a file matching `BLOCKED_EXTENSIONS` (default `@malware`: arj, lnk, exe, bat, cmd, com, scr, pif, vbs, ps1) or `BLOCKED_NAMES` is blocklisted, removed with its files, and a replacement is searched for. Requested by binhex ([#4](https://github.com/steveharsant/purgarr/issues/4)).
  * **Skip:** files matching `SKIPPED_EXTENSIONS` or `SKIPPED_NAMES` (e.g. `*sample*`) aren't downloaded, and the rest of the download carries on. If nothing would be left, the download is rejected.
  * Ready-made groups: `@malware`, `@executables`, `@archives`, `@disc-images` and `@roms`. Extensions and names accept wildcards.
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
