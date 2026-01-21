from pathlib import Path

from src.consts import DEFAULT_DATA_DIR
from src.storage.cache.base import Cache


class FileCache(Cache):
    def initialize(self, data_location: Path = DEFAULT_DATA_DIR, cache_category: str = "default"):
        self.data_location = data_location / "cache"

    def put(self, key: str, value: str, category: str):
        pass

    def get(self, category: str):
        pass

    def delete(self, category: str):
        pass
