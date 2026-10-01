import os
from pathlib import Path


class LocalResumeStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    async def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            self.root.chmod(0o700)

    def path(self, key: str) -> Path:
        if not key or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789_." for character in key
        ):
            raise ValueError("Invalid storage key")
        value = (self.root / key).resolve()
        if not value.is_relative_to(self.root):
            raise ValueError("Storage path escaped private root")
        return value

    async def save(self, key: str, content: bytes) -> None:
        target = self.path(key)

        def write() -> None:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)

        write()

    async def read(self, key: str) -> bytes:
        return self.path(key).read_bytes()

    async def delete(self, key: str) -> None:
        path = self.path(key)
        try:
            path.unlink()
        except FileNotFoundError:
            return

    async def exists(self, key: str) -> bool:
        return self.path(key).is_file()
