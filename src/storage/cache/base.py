from abc import ABC, abstractmethod


class Cache(ABC):
    """Abstract base class for file storage manager."""

    @abstractmethod
    def put(self, key: str, value: str, category: str): ...

    @abstractmethod
    def get(self, category: str): ...

    @abstractmethod
    def delete(self, category: str): ...
