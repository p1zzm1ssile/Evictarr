# Purgarr

> ***Plunder the best, purge the rest!***

Purgarr is a lightweight companion to your Arr stack designed to keep your download queue clean and ready for high quality downloads.

**Features Include:**

* Cleans your download client of media imported by Sonarr and Radarr.
* Detects and removes stalled downloads.
* Adds stalled downloads to Sonarr's and Radarr's blocklist.
* Triggers a search to replace low quality downloads.
* Optionally removes downloads that Sonarr or Radarr failed to import, and searches for a replacement.
* Can be limited to Sonarr's and Radarr's own categories, leaving everything else in your client alone.
* Health status in the web UI, at `/health`, and as a Docker health check.

**Supported download clients:** qBittorrent, RDTClient, Deluge, Transmission and SABnzbd.

> ***Note:** Purgarr is still in a pre-release state.*

## Minimum Setup

### Commandline

```bash
docker run --name purgarr \
  -e QBIT_URL='ip-address-or-hostname-with-port' \
  -e QBIT_PASSWORD='password' \
  -e SONARR_API_KEY='password' \
  -e SONARR_URL='ip-address-or-hostname-with-port' \
  -e RADARR_API_KEY='password' \
  -e RADARR_URL='ip-address-or-hostname-with-port' \
  -p  9891:9891 \
  ghcr.io/steveharsant/purgarr:latest
```

### Docker Compose

```yaml
services:
  purgarr:
    image: ghcr.io/steveharsant/purgarr:latest
    container_name: purgarr
    environment:
      - QBIT_URL='ip-address-or-hostname-with-port'
      - QBIT_PASSWORD='password'
      - SONARR_API_KEY='password'
      - SONARR_URL='ip-address-or-hostname-with-port'
      - RADARR_API_KEY='password'
      - RADARR_URL='ip-address-or-hostname-with-port'
    ports:
      - 9891:9891
    restart: unless-stopped
```

## Download Clients

Choose the client with `DOWNLOAD_CLIENT` (or the older name, `TORRENT_CLIENT`). The default is `qbittorrent`.

### qBittorrent

Set `QBIT_URL`, and `QBIT_PASSWORD` (and `QBIT_USER` if it isn't `admin`). Works with qBittorrent 4.x and 5.x, including 5.2.

### RDTClient

Set `DOWNLOAD_CLIENT=rdtclient`. RDTClient copies qBittorrent's API, so use the `QBIT_*` settings to point Purgarr at it. If RDTClient's authentication is turned off, any username and password will do.

### Deluge

Set `DOWNLOAD_CLIENT=deluge` and give Purgarr the address and password of the Deluge **Web UI** (port 8112 by default), not the daemon. The Web UI must have a daemon set up in its Connection Manager. If it isn't already connected, Purgarr connects it to the first daemon listed.

Purgarr reads categories from Deluge's **Label** plugin, which is what Sonarr and Radarr use. Deluge labels are always lowercase, so keep `SONARR_LABELS`, `RADARR_LABELS` and the imported labels in lowercase too.

Deluge has no "stalled" state of its own. Purgarr treats a torrent as stalled when it is downloading with no seeds connected and nothing being received, and it is older than `TORRENT_AGE`.

### Transmission

Set `DOWNLOAD_CLIENT=transmission`, `TRANSMISSION_URL`, and `TRANSMISSION_USER` and `TRANSMISSION_PASSWORD` if Transmission has authentication turned on.

Sonarr and Radarr store their category in a label on Transmission 4.0 and newer, and as a subfolder of the download folder on older versions. Purgarr checks both.

Transmission has no "stalled" state of its own either. Purgarr treats a torrent as stalled when it is downloading with no peers sending anything, and it is older than `TORRENT_AGE`.

### SABnzbd

Set `DOWNLOAD_CLIENT=sabnzbd`, `SABNZBD_URL` and `SABNZBD_API_KEY` (from SABnzbd's Config > General page).

Usenet downloads don't stall the way torrents do, and SABnzbd doesn't say when a download was added. Purgarr watches each active download and treats it as stalled when its remaining size hasn't changed for longer than `TORRENT_AGE` minutes. Time with the queue paused doesn't count. Because of this, a download is never purged on the first check after Purgarr starts.

Sonarr's default SABnzbd category is `tv` and Radarr's is `movies`, so set `SONARR_LABELS` and `RADARR_LABELS` to match if you use `IGNORE_OTHER_CATEGORIES`.

Sonarr and Radarr remove completed downloads from SABnzbd themselves, so the imported purge has nothing to do with SABnzbd.

## Removing Failed Imports

Set `PURGE_FAILED_IMPORTS=True` to clear downloads that finished but that Sonarr or Radarr couldn't import, for example "No files found are eligible for import". Purgarr asks Sonarr/Radarr to remove the download from the client, add the release to the blocklist and, if `RETRY_SEARCH` is on, search for another.

This is off by default because it also catches downloads waiting for you to import them by hand. If you use manual import, leave it off.

## Health Check

Purgarr records the result of every check, and counts itself unhealthy when a check fails (for example, Sonarr can't be reached) or hasn't run for two of its intervals.

* **Web UI:** a green or red status bar above the logs shows the result of each check.
* **HTTP:** `GET /health` returns the status as JSON, with HTTP 200 when healthy and 503 when not.
* **Command line:** `docker exec purgarr python healthcheck.py` prints the status and exits with 0 when healthy, 1 when not.
* **Docker:** the image includes a `HEALTHCHECK`, so `docker ps` shows `healthy` or `unhealthy`.

## Environment Variables

The minimum setup assumes Purgarr is running on the same host as your Arr stack. If this is not the case, the below table shows the additional options Purgarr can be configured with.

| Environment Variable        | Type   | Description                                                                                                                                              | Default         | Required |
|-----------------------------|--------|----------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------|----------|
| WEB_HOST                    | string | DNS name for where to access the running webUI                                                                                                           | localhost       | No       |
| WEB_PORT                    | int    | The port to run the webUI on                                                                                                                             | 9891            | No       |
| LOG_LEVEL                   | string | Minimum level of logs to print (Options: `info`, `warn`, `error`)                                                                                        | info            | No       |
| LOG_LINES                   | int    | Number of (most recent) log lines to show in the webUI                                                                                                   | 100             | No       |
| LOG_REFRESH_INTERVAL        | int    | How often new log entried are fetched and displayed in the webUI (seconds)                                                                               | 5 (seconds)     | No       |
| LOG_OUTPUT                  | string | Log output type (**Accepted values:** `all`, `stdout`, `web`)                                                                                            | all             | No       |
| PURGE_STALLED               | string | Enabled/Disable purge of stalled torrents.                                                                                                               | True            | No       |
| PURGE_STALLED_INTERVAL      | int    | Time in seconds between stalled torrent purges                                                                                                           | 300 (seconds)   | No       |
| BLOCK_STALLED_TORRENTS      | bool   | Block stalled torrents in Sonarr/Radarr                                                                                                                  | True            | No       |
| PURGE_IMPORTED              | bool   | Enable/Disable purge of imported torrents                                                                                                                | True            | No       |
| PURGE_IMPORTED_INTERVAL     | int    | Time in seconds between imported torrent purges                                                                                                          | 600 (seconds)   | No       |
| DELETE_FILES                | bool   | Delete files from torrent clients download folder                                                                                                        | True            | No       |
| IGNORE_OTHER_CATEGORIES     | bool   | Only purge stalled downloads whose category matches `SONARR_LABELS` or `RADARR_LABELS`; downloads in any other category are left alone                    | False           | No       |
| RETRY_SEARCH                | bool   | Trigger Sonarr/Radarr to search for another release                                                                                                      | True            | No       |
| DOWNLOAD_CLIENT             | string | Download client (Options: `qbittorrent`, `rdtclient`, `deluge`, `transmission`, `sabnzbd`). `TORRENT_CLIENT` also works                                 | `qbittorrent`   | No       |
| TORRENT_AGE                 | int    | Grace period in minutes before a download is included in a stalled purge check                                                                           | 5 (minutes)     | No       |
| PURGE_FAILED_IMPORTS        | bool   | Remove and blocklist downloads Sonarr/Radarr couldn't import (see [Removing Failed Imports](#removing-failed-imports))                                     | False           | No       |
| REQUEST_TIMEOUT             | int    | Seconds to wait for a download client, Sonarr or Radarr to respond                                                                                       | 30 (seconds)    | No       |
| QBIT_URL                    | string | IP address or hostname to QBittorent webUI                                                                                                               | N/A             | qBittorrent |
| QBIT_USER                   | string | QBittorrent username                                                                                                                                     | admin           | No       |
| QBIT_PASSWORD               | string | QBittorrent password                                                                                                                                     | N/A             | qBittorrent |
| QBIT_TOKEN_REFRESH_INTERVAL | int    | Time between auth token refresh for qBittorrent                                                                                                          | 600 (seconds)   | No       |
| DELUGE_URL                  | string | IP address or hostname of the Deluge Web UI (only used when `TORRENT_CLIENT=deluge`)                                                                     | localhost:8112  | No       |
| DELUGE_PASSWORD             | string | Deluge Web UI password                                                                                                                                   | deluge          | No       |
| TRANSMISSION_URL            | string | IP address or hostname of Transmission                                                                                                                   | localhost:9091  | No       |
| TRANSMISSION_USER           | string | Transmission username, if authentication is turned on                                                                                                    | N/A             | No       |
| TRANSMISSION_PASSWORD       | string | Transmission password, if authentication is turned on                                                                                                   | N/A             | No       |
| SABNZBD_URL                 | string | IP address or hostname of SABnzbd                                                                                                                        | localhost:8080  | No       |
| SABNZBD_API_KEY             | string | SABnzbd API key                                                                                                                                          | N/A             | SABnzbd  |
| SONARR_API_KEY              | string | API key for Sonarr                                                                                                                                       | N/A             | Yes      |
| SONARR_LABELS               | string | The label(s) used by Sonarr to link a torrent to a show or episode (use a `,` to separate multiple labels)                                               | tv-sonarr       | No       |
| SONARR_IMPORTED_LABEL       | string | The label used by Sonarr to tag a torrent as having been imported to the library. (Set the Post-Import Category in the advance torrent client settings). | sonarr-imported | No       |
| SONARR_URL                  | string | Sonarr URL                                                                                                                                               | N/A             | Yes      |
| RADARR_API_KEY              | string | API Key for Radarr                                                                                                                                       | N/A             | Yes      |
| RADARR_LABELS               | string | The label(s) used by Radarr to link a torrent to a movie (use a `,` to separate multiple labels)                                                         | radarr          | No       |
| RADARR_URL                  | string | Radarr URL                                                                                                                                               | N/A             | Yes      |
| RADARR_IMPORTED_LABEL       | string | The label used by Radarr to tag a torrent as having been imported to the library. (Set the Post-Import Category in the advance torrent client settings). | radarr-imported | Yes      |
