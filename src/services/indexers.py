import requests
import xml.etree.ElementTree as ET
import utils.config as config


class Prowlarr:
    """Reads indexer health from Prowlarr."""

    def __init__(self, cfg=None):
        self.cfg = cfg or config
        self.session = requests.Session()

    def get(self, endpoint: str):
        response = self.session.get(
            f"{self.cfg.prowlarr_url}/api/v1/{endpoint}",
            headers={"X-Api-Key": self.cfg.prowlarr_api_key or ""},
            timeout=self.cfg.request_timeout,
        )
        if response.status_code == 401:
            raise Exception("API key rejected, check the Prowlarr API key")
        response.raise_for_status()
        return response.json()

    def version(self) -> str:
        return self.get("system/status").get("version", "unknown")

    def indexers(self) -> list:
        failing = {s["indexerId"]: s for s in self.get("indexerstatus")}
        results = []
        for i in self.get("indexer"):
            status = failing.get(i["id"])
            results.append(
                {
                    "name": i.get("name", f"Indexer {i['id']}"),
                    "enabled": bool(i.get("enable", True)),
                    "ok": status is None,
                    "problem": (
                        f"failing since {status.get('mostRecentFailure', 'recently')}"
                        + (f", disabled until {status['disabledTill']}" if status.get("disabledTill") else "")
                        if status
                        else ""
                    ),
                }
            )
        return results


class Jackett:
    """Reads the configured indexers from Jackett's Torznab API."""

    def __init__(self, cfg=None):
        self.cfg = cfg or config
        self.session = requests.Session()

    def torznab(self, **params):
        response = self.session.get(
            f"{self.cfg.jackett_url}/api/v2.0/indexers/all/results/torznab/api",
            params={"apikey": self.cfg.jackett_api_key or "", **params},
            timeout=self.cfg.request_timeout,
        )
        # Don't use raise_for_status, its message includes the URL and so the API key
        if response.status_code in (401, 403):
            raise Exception("API key rejected, check the Jackett API key")
        if not response.ok:
            raise Exception(f"Jackett answered HTTP {response.status_code}")
        root = ET.fromstring(response.content)
        if root.tag == "error":
            raise Exception(root.get("description", "Jackett returned an error"))
        return root

    def version(self) -> str:
        self.torznab(t="caps")
        return "connected"

    def indexers(self) -> list:
        root = self.torznab(t="indexers", configured="true")
        return [
            {
                "name": (i.findtext("title") or i.get("id", "unknown")).strip(),
                "enabled": True,
                "ok": True,
                "problem": "",
            }
            for i in root.iter("indexer")
        ]
