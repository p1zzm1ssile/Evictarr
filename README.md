<p align="center"><img src="src/web/logo.png" alt="Evictarr" width="280"></p>

# Evictarr

> ***Stalled, failed or done? Evicted.***

Evictarr is a lightweight companion to your Arr stack that keeps your download client clean, so Sonarr and Radarr can keep grabbing the good stuff.

**Features:**

* Removes downloads once Sonarr or Radarr has imported them.
* Finds stalled downloads, blocklists them in Sonarr/Radarr and searches for a replacement.
* Optionally clears downloads that Sonarr/Radarr couldn't import.
* Optionally rejects downloads containing dangerous or unwanted files (`.arj`, `.lnk`, `.exe`, RARs, ISOs, ROMs and more), blocklists them and searches for a replacement.
* Optionally skips files you don't want, such as samples, while keeping the rest of the download.
* Can be limited to Sonarr's and Radarr's own categories, leaving everything else in your client alone.
* Health status in the web UI, at `/health`, and as a Docker health check.

**Supported download clients:** qBittorrent, RDTClient, Deluge, Transmission and SABnzbd.

## A Thank You, and Why This Fork Exists

Evictarr is built on [**Purgarr**](https://github.com/steveharsant/purgarr), created by **Steve Harsant** ([@steveharsant](https://github.com/steveharsant)). All of the original design and code are his work, and a big thank you to him for building it and sharing it with everyone.

Purgarr hasn't been updated since June 2025, and bug reports and feature requests from its users have gone unanswered since then, so for now it looks to be abandoned. Rather than let it fade away, I've picked it up to keep it working and to add what people were asking for, including qBittorrent 5.2 support, more download clients and a health check.

**This isn't an attempt to take credit for Steve's work.** His full commit history is kept in this repository, his license is unchanged, and every change made here is listed in the [CHANGELOG](CHANGELOG.md). Evictarr only exists to look after the project while Purgarr is inactive. If Steve comes back to it, I'll gladly offer all of these changes back to the original project.

If you're Steve and you'd like anything here done differently, please [open an issue](https://github.com/p1zzm1ssile/Evictarr/issues) and I'll sort it out.

## Getting Started

Evictarr is set up in its web UI. All it needs is a port and a folder for its settings.

### Docker Compose

```yaml
services:
  evictarr:
    image: ghcr.io/p1zzm1ssile/evictarr:latest
    container_name: evictarr
    ports:
      - 9891:9891
    volumes:
      - ./evictarr:/config
    restart: unless-stopped
```

### Commandline

```bash
docker run -d --name evictarr -p 9891:9891 -v /path/to/evictarr:/config ghcr.io/p1zzm1ssile/evictarr:latest
```

### Unraid

Change the template's **Repository** to `ghcr.io/p1zzm1ssile/evictarr:latest` and add a **Path** with container path `/config` and host path `/mnt/user/appdata/evictarr`. Or copy [`unraid/evictarr.xml`](unraid/evictarr.xml) to `/boot/config/plugins/dockerMan/templates-user/` on your server and add Evictarr from **Docker > Add Container**.

### First run

1. Open `http://your-server:9891`.
2. Enter the **setup code** from Evictarr's log. It's printed when Evictarr starts (in Unraid, click the Evictarr icon and choose **Logs**; with Docker, run `docker logs evictarr`). This stops anyone else on your network, or anyone reaching it through a misconfigured proxy, from creating the account before you.
3. Create your login. The password needs at least 8 characters, with an uppercase letter, a lowercase letter, a number and a special character.
4. Go to **Settings**. Tick your download client(s), add Sonarr and Radarr, choose what to purge and block. Use **Test connection** to check each one, and **Save** on each tab.

Coming from Purgarr or an earlier Evictarr? Your existing environment variables are copied into the settings on first start, so nothing needs re-entering. After that, the web UI is where settings live.

## The Web UI

* **Downloads** (the start page): every download in every client, which of Sonarr/Radarr is tracking it and from which indexer, and its files. Each file shows whether it will be blocked or skipped.
  * **Remove by hand:** tick downloads and choose **Remove…**. You choose whether to delete their files, and whether to blocklist them in Sonarr/Radarr so a different release is searched for (blocklisting happens first, while the release is still in their queue).
  * **Run checks now** runs every purge straight away instead of waiting for the next one.
* **Help**: how to get support or report a problem (with a pre-filled GitHub issue), the version, and links to the changelog and this guide.
* **Logs**: everything Evictarr has done. **Issues** shows only errors and warnings, **Actions** shows only what was removed, blocklisted or skipped. **Download all logs** gives you every log file as a zip.
* **Settings**, with a tab for each area and its own **Save** button:
  * **General**: imported, stalled and failed-import purges, intervals, logs, your login.
  * **Blocking**: file types and names to reject or skip.
  * **Sonarr** and **Radarr**: address, API key and categories.
  * **Download clients**: tick every client you use. Evictarr works with all of them at once, and keeps going with the others if one is down.
  * **Indexers**: optionally connect Prowlarr and/or Jackett to see which indexers are working or failing on the Downloads page.

Changes take effect as soon as you save, without a restart.

## Login and Security

> ⚠️ **Keep Evictarr on your home network.** It can see your download clients and holds their passwords and API keys. We don't recommend putting it behind a reverse proxy (Nginx Proxy Manager, SWAG, Traefik, Cloudflare Tunnel and the like) for access from outside your network. To reach it remotely, use a VPN such as WireGuard or Tailscale.

* The password is stored as a scrypt hash in `/config/auth.json`, never in plain text.
* After 5 wrong passwords, that address is locked out for 5 minutes.
* **Skip login on my local network** (Settings > General) lets devices on the networks you list in **My local networks** in without a password. The default is `192.168.0.0/16, 10.0.0.0/8`. Docker's own range (`172.16.0.0/12`) isn't included, because traffic forwarded by Docker can appear to come from there. The bypass never applies to requests that arrive through a reverse proxy.
* Changing a download client's, Sonarr's, Radarr's or an indexer's address needs its password or API key entered again, so a saved key can't be sent somewhere new.
* Saved passwords and API keys are never sent back to the browser.
* `settings.json` and `auth.json` are only readable by the account Evictarr runs as.
* **Forgotten your password?** Delete `auth.json` from the config folder and restart Evictarr. It will ask you to create a login again, with a new setup code in the log. Your settings are kept.
* If `settings.json` is damaged (for example by a hand edit), Evictarr moves it aside as `settings.json.broken-<time>`, logs an error, and starts with defaults, so nothing is silently overwritten.

## Download Clients

Choose the client with `DOWNLOAD_CLIENT` (or the older name, `TORRENT_CLIENT`). The default is `qbittorrent`.

### qBittorrent

Set `QBIT_URL`, and `QBIT_PASSWORD` (and `QBIT_USER` if it isn't `admin`). Works with qBittorrent 4.x and 5.x, including 5.2.

### RDTClient

Set `DOWNLOAD_CLIENT=rdtclient`. RDTClient copies qBittorrent's API, so use the `QBIT_*` settings to point Evictarr at it. If RDTClient's authentication is turned off, any username and password will do.

### Deluge

Set `DOWNLOAD_CLIENT=deluge` and give Evictarr the address and password of the Deluge **Web UI** (port 8112 by default), not the daemon. The Web UI must have a daemon set up in its Connection Manager. If it isn't already connected, Evictarr connects it to the first daemon listed.

Evictarr reads categories from Deluge's **Label** plugin, which is what Sonarr and Radarr use. Deluge labels are always lowercase, so keep `SONARR_LABELS`, `RADARR_LABELS` and the imported labels in lowercase too.

Deluge has no "stalled" state of its own. Evictarr treats a torrent as stalled when it is downloading with no seeds connected and nothing being received, and it is older than `TORRENT_AGE`.

### Transmission

Set `DOWNLOAD_CLIENT=transmission`, `TRANSMISSION_URL`, and `TRANSMISSION_USER` and `TRANSMISSION_PASSWORD` if Transmission has authentication turned on.

Sonarr and Radarr store their category in a label on Transmission 4.0 and newer, and as a subfolder of the download folder on older versions. Evictarr checks both.

Transmission has no "stalled" state of its own either. Evictarr treats a torrent as stalled when it is downloading with no peers sending anything, and it is older than `TORRENT_AGE`.

### SABnzbd

Set `DOWNLOAD_CLIENT=sabnzbd`, `SABNZBD_URL` and `SABNZBD_API_KEY` (from SABnzbd's Config > General page).

Usenet downloads don't stall the way torrents do, and SABnzbd doesn't say when a download was added. Evictarr watches each active download and treats it as stalled when its remaining size hasn't changed for longer than `TORRENT_AGE` minutes. Time with the queue paused doesn't count. Because of this, a download is never purged on the first check after Evictarr starts.

Sonarr's default SABnzbd category is `tv` and Radarr's is `movies`, so set `SONARR_LABELS` and `RADARR_LABELS` to match if you use `IGNORE_OTHER_CATEGORIES`.

Sonarr and Radarr remove completed downloads from SABnzbd themselves, so the imported purge has nothing to do with SABnzbd.

## Removing Failed Imports

Set `PURGE_FAILED_IMPORTS=True` to clear downloads that finished but that Sonarr or Radarr couldn't import, for example "No files found are eligible for import". Evictarr asks Sonarr/Radarr to remove the download from the client, add the release to the blocklist and, if `RETRY_SEARCH` is on, search for another.

This is off by default because it also catches downloads waiting for you to import them by hand. If you use manual import, leave it off.

## Blocking and Skipping Files

Some public torrents carry malware in files like `.arj` or `.lnk`. Even if your torrent client skips those files, Sonarr and Radarr still see the download as finished and never look for another release. Other releases arrive as RARs, disc images or something else you don't want, or come with sample files you'd rather not download.

Set `PURGE_FILES=True` (or `PURGE_EXTENSIONS=True`, which does the same) and Evictarr checks the file list of every download Sonarr and Radarr are tracking every `PURGE_EXTENSIONS_INTERVAL` seconds. It never touches anything else in your client. There are two actions:

**Block: reject the whole download.** When a download contains a file matching `BLOCKED_EXTENSIONS` or `BLOCKED_NAMES`, Evictarr:

1. Adds the release to the Sonarr/Radarr blocklist, so they search for another (if `RETRY_SEARCH` is on).
2. Removes the download from your client.
3. Deletes its files, even if `DELETE_FILES` is off, since they may be malware.

**Skip: just don't download those files.** Files matching `SKIPPED_EXTENSIONS` or `SKIPPED_NAMES` are switched off in your client and the rest of the download carries on, so you can drop sample files without losing the release. If nothing would be left to download, the download is rejected instead. On SABnzbd, skipped files are removed from the job.

**Extensions** are separated by commas, with or without the dot, and can use wildcards (`r[0-9][0-9]` matches `.r00` to `.r99`). You can also use these ready-made groups:

| Group | Extensions |
|-------|------------|
| `@malware` | arj, lnk, exe, bat, cmd, com, scr, pif, vbs, ps1 |
| `@executables` | exe, msi, bat, cmd, com, scr, pif, vbs, ps1, jar, apk, dmg |
| `@archives` | rar, zip, 7z, tar, gz, bz2, xz, arj, .r00 to .r99, .001 to .999 |
| `@disc-images` | iso, img, bin, cue, nrg, mdf, mds |
| `@roms` | rom, nes, sfc, smc, gb, gbc, gba, n64, z64, v64, nds, 3ds, cia, xci, nsp, wbfs, gcm, chd, pbp |

**Names** are wildcard patterns, separated by commas, matched against the file name and ignoring case: `*sample*` matches `Movie-sample.mkv`. A pattern containing `/` is matched against the file's path inside the download instead, so `*/extras/*` matches anything in an `Extras` folder.

Example:

```
PURGE_FILES=True
BLOCKED_EXTENSIONS=@malware,@archives,@disc-images,@roms
SKIPPED_NAMES=*sample*
```

`BLOCKED_EXTENSIONS` defaults to `@malware`. Archives aren't blocked by default because many genuine releases come packed in RARs, so only add `@archives` if you're happy for those to be replaced.

### Samples and languages

Also on the **Blocking** tab, under **Samples and languages**:

* **Don't download sample files**: skips video files named sample or in a `Sample` folder, keeping the rest of the release.
* **My languages**: tick the languages you want.
* **Only keep subtitles and extra audio in my languages**: separate subtitle files (`.srt`, `.ass`, `.sup`…) and extra audio files (`.mka`, `.dts`, `.ac3`…) in other languages aren't downloaded. The language is read from the file name, e.g. `Movie.fr.srt` or `Subs/3_French.srt`. Audio files are only treated as extra tracks when the download also has a video, so music downloads aren't touched.
* **Keep subtitles and audio with no language in the name**: on by default, since many releases don't label their main subtitles.
* **Reject releases tagged with another language**: a release tagged e.g. `GERMAN` after its title (and not also `MULTi` or one of your languages) is blocklisted and a replacement is searched for. Title words don't count, so *The Italian Job* is safe.

Evictarr only sees file names, not what's inside files, so it can't check the audio and subtitle tracks built into a video file. Sonarr's and Radarr's language profiles and custom formats handle those.

Blocking was requested by [binhex](https://github.com/binhex) in [Purgarr #4](https://github.com/steveharsant/purgarr/issues/4).

## Health Check

Evictarr records the result of every check, and counts itself unhealthy when a check fails (for example, Sonarr can't be reached) or hasn't run for two of its intervals.

* **Web UI:** a green or red status bar above the logs shows the result of each check.
* **HTTP:** `GET /health` returns the status as JSON, with HTTP 200 when healthy and 503 when not.
* **Command line:** `docker exec evictarr python healthcheck.py` prints the status and exits with 0 when healthy, 1 when not.
* **Docker:** the image includes a `HEALTHCHECK`, so `docker ps` shows `healthy` or `unhealthy`.

## Contact

Bugs and ideas: [open an issue](https://github.com/p1zzm1ssile/Evictarr/issues). For anything private, email [p1zzm1ssilerepo@gmail.com](mailto:p1zzm1ssilerepo@gmail.com?subject=Evictarr). Both are also on the Help & contact page in the web UI.

## Environment Variables

Everything below can be set in the web UI instead. Environment variables are only read on **first start**, to create the settings, so existing Purgarr setups carry over. These are only read from the environment, every time:

| Environment Variable | Description | Default |
|----------------------|-------------|---------|
| WEB_PORT             | Port for the web UI | 9891 |
| CONFIG_DIR           | Folder for settings, login and logs | /config |
| LOG_OUTPUT           | `all` also logs to the container console, `web` only to the log file | all |

The settings that can come from the environment on first start:

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
| PURGE_FILES                 | bool   | Turn on blocking and skipping files (see [Blocking and Skipping Files](#blocking-and-skipping-files)). `PURGE_EXTENSIONS` also works                       | False           | No       |
| PURGE_EXTENSIONS_INTERVAL   | int    | Time in seconds between file checks                                                                                                                      | 60 (seconds)    | No       |
| BLOCKED_EXTENSIONS          | string | File types that get a download rejected, separated by commas. Groups like `@archives` work                                                               | @malware        | No       |
| BLOCKED_NAMES               | string | File name patterns that get a download rejected, e.g. `*password*`                                                                                       | N/A             | No       |
| SKIPPED_EXTENSIONS          | string | File types to skip (not download), separated by commas. Groups like `@archives` work                                                                     | N/A             | No       |
| SKIPPED_NAMES               | string | File name patterns to skip (not download), e.g. `*sample*`                                                                                               | N/A             | No       |
| REQUEST_TIMEOUT             | int    | Seconds to wait for a download client, Sonarr or Radarr to respond                                                                                       | 30 (seconds)    | No       |
| QBIT_URL                    | string | IP address or hostname to QBittorent webUI                                                                                                               | N/A             | qBittorrent |
| QBIT_USER                   | string | QBittorrent username                                                                                                                                     | admin           | No       |
| QBIT_PASSWORD               | string | QBittorrent password                                                                                                                                     | N/A             | qBittorrent |
| QBIT_TOKEN_REFRESH_INTERVAL | int    | Time between auth token refresh for qBittorrent                                                                                                          | 600 (seconds)   | No       |
| DELUGE_URL                  | string | IP address or hostname of the Deluge Web UI (only used when `TORRENT_CLIENT=deluge`)                                                                     | N/A             | No       |
| DELUGE_PASSWORD             | string | Deluge Web UI password                                                                                                                                   | deluge          | No       |
| TRANSMISSION_URL            | string | IP address or hostname of Transmission                                                                                                                   | N/A             | No       |
| TRANSMISSION_USER           | string | Transmission username, if authentication is turned on                                                                                                    | N/A             | No       |
| TRANSMISSION_PASSWORD       | string | Transmission password, if authentication is turned on                                                                                                   | N/A             | No       |
| SABNZBD_URL                 | string | IP address or hostname of SABnzbd                                                                                                                        | N/A             | No       |
| SABNZBD_API_KEY             | string | SABnzbd API key                                                                                                                                          | N/A             | SABnzbd  |
| SONARR_API_KEY              | string | API key for Sonarr                                                                                                                                       | N/A             | Yes      |
| SONARR_LABELS               | string | The label(s) used by Sonarr to link a torrent to a show or episode (use a `,` to separate multiple labels)                                               | tv-sonarr       | No       |
| SONARR_IMPORTED_LABEL       | string | The label used by Sonarr to tag a torrent as having been imported to the library. (Set the Post-Import Category in the advance torrent client settings). | sonarr-imported | No       |
| SONARR_URL                  | string | Sonarr URL                                                                                                                                               | N/A             | Yes      |
| RADARR_API_KEY              | string | API Key for Radarr                                                                                                                                       | N/A             | Yes      |
| RADARR_LABELS               | string | The label(s) used by Radarr to link a torrent to a movie (use a `,` to separate multiple labels)                                                         | radarr          | No       |
| RADARR_URL                  | string | Radarr URL                                                                                                                                               | N/A             | Yes      |
| RADARR_IMPORTED_LABEL       | string | The label used by Radarr to tag a torrent as having been imported to the library. (Set the Post-Import Category in the advance torrent client settings). | radarr-imported | Yes      |
