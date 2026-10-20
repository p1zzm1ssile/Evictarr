import time
import requests
import utils.config as config
from utils.logger import *
from services.base_arrs import Base


class Radarr(Base):
    def get_queue(self):
        return self.get_records(
            url=self.cfg.radarr_url,
            endpoint="queue",
            api_key=self.cfg.radarr_api_key,
            params={"includeUnknownMovieItems": "true", "pageSize": 200},
        )

    def get_history(self):
        return self.get_records(
            url=self.cfg.radarr_url,
            endpoint="history",
            api_key=self.cfg.radarr_api_key,
            params={"eventType": 1, "pageSize": 5000},
        )

    def block_release(self, title, release_id):
        return super().block_release(
            url=self.cfg.radarr_url,
            api_key=self.cfg.radarr_api_key,
            title=title,
            release_id=release_id,
        )

    def remove_failed_import(self, title, release_id):
        return super().remove_from_queue(
            url=self.cfg.radarr_url,
            api_key=self.cfg.radarr_api_key,
            title=title,
            release_id=release_id,
            remove_from_client=True,
            blocklist=True,
        )
