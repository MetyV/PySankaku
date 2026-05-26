from pathlib import Path
from urllib.parse import urlparse

import aiohttp


class Helper:
    def __init__(self, timeout: int = 30):
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def resolve_path(self, path: Path | str) -> Path:
        return Path(path).resolve() if isinstance(path, str) else path.resolve()
    
    def get_filename_from_url(self, url: str) -> str:
        parsed = urlparse(url)
        return Path(parsed.path).name