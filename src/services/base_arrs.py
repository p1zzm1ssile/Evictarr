import requests
import utils.config as config
from utils.logger import *


class Base:
    def __init__(self, cfg=None):
        # cfg is the settings to use; a test from the web UI passes unsaved ones
        self.cfg = cfg or config
        self.session = requests.Session()

    def get_records(self, url: str, endpoint: str, api_key: str, params: dict):
        params["page"] = 0
        records = []

        while True:
            params["page"] += 1

            response = self.session.get(
                url=f"{url}/{endpoint}",
                headers={"X-Api-Key": api_key},
                params=params,
                timeout=self.cfg.request_timeout,
            )
            response.raise_for_status()
            body = response.json()

            records.append(body["records"])

            # Sonarr/Radarr ignore unknown parameters, so go by the page size they used
            page_size = body.get("pageSize") or params["pageSize"]
            total_pages = (body["totalRecords"] + page_size - 1) // page_size

            if params["page"] >= total_pages:
                break

        return records

    def remove_from_queue(
        self,
        url: str,
        api_key: str,
        title: str,
        release_id: str,
        remove_from_client: bool = False,
        blocklist: bool = True,
    ):
        response = self.session.delete(
            url=f"{url}/queue/bulk",
            headers={
                "X-Api-Key": api_key,
                "Content-Type": "application/json",
            },
            json={"ids": [release_id]},
            params={
                "removeFromClient": f"{remove_from_client}".lower(),
                "blocklist": f"{blocklist}".lower(),
                "skipRedownload": f"{not self.cfg.retry_search}".lower(),
                "changeCategory": "false",
            },
            timeout=self.cfg.request_timeout,
        )

        if response.status_code == 404 or (
            response.content and response.json().get("message") == "NotFound"
        ):
            logger.warning(f"Unable to find queue item: {title}")
            return False

        response.raise_for_status()
        return True

    def block_release(self, url: str, api_key: str, title: str, release_id: str):
        if self.remove_from_queue(url, api_key, title, release_id):
            logger.info(f"Added {title} to blocklist")
            return True

        return False
