from pathlib import Path
from typing import Optional

from aiohttp import ClientTimeout

from helper import Helper as hlp

class Downloader:
    def __init__(self):
        self.helper = hlp()

    def getName(self, url: str):
        return url.split('/')[-1].split('?')[0]

    async def _getHeads(self, url: str, headers: dict = {}, json: dict = {}, timeout: int = 20):
        r, s = await self.helper.request(url, headers, 'HEAD', json, timeout=timeout)
        if s and s == 200 and r:
            return r
        return 

    async def getSize(self, url: str, headers: dict = {}, json: dict = {}, timeout: int = 20) -> Optional[int]:
        r = await self._getHeads(url, headers, json, timeout)

        if not r:
            return

        size = r.headers.get('content-length')
        if size:
            return int(size)
        
        return

    async def getType(self, url: str, headers: dict = {}, json: dict = {}, timeout: int = 20) -> Optional[str]:
        r = await self._getHeads(url, headers, json, timeout)
        
        if not r:
            return

        type = r.headers.get('content-type')
        return type

    async def download(self, 
                       url: str, 
                       path: Path | str, 
                       name: Path | str = '',
                       extension: bool = True, # cause linux(macos 50/50) dgaf bout this shit, but 'True' for pussies(win users)
                       stream: bool = True,
                       ssl: bool = True,
                       headers: dict = {}, 
                       json: dict = {}, 
                       timeout: ClientTimeout | None = None, 
                       mkdir: bool = True, 
                       overwrite: bool = False):
        

'''
sankaku method

async with session.get(url) as resp:
    if resp.status == 200:
        filename = url.split('/')[-1].split('?')[0]
        data = await resp.read()
        with open(filename, 'wb') as f:
            f.write(data)


    "headers": {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:153.0) Gecko/20100101 Firefox/153.0",
    },
    "method": "GET"
});
'''