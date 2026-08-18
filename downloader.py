from pathlib import Path
from typing import Literal, Optional
from helper import logger as logging
from aiohttp import ClientTimeout

from helper import Helper as hlp

class Downloader:
    def __init__(self):
        self.helper = hlp()

    async def __aenter__(self):
        await self.helper._session_init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb): # i pray it'll work
        await self.helper._session_close()

    def getName(self, url: str) -> str:
        return self.helper.get_filename_from_url(url)

    async def _getHeads(self, url: str, headers: dict = {}, json: dict = {}, timeout: ClientTimeout | None = None):
        r, s = await self.helper.request(url, headers, 'HEAD', json, timeout=timeout)
        if s and s == 200 and r:
            return r
        return 

    async def getSize(self, url: str, headers: dict = {}, json: dict = {}, timeout: ClientTimeout | None = None) -> Optional[int]:
        r = await self._getHeads(url, headers, json, timeout)

        if not r:
            return

        size = r.headers.get('content-length')
        if size:
            return int(size)
        
        return

    async def getType(self, url: str, headers: dict = {}, json: dict = {}, timeout: ClientTimeout | None = None) -> Optional[str]:
        r = await self._getHeads(url, headers, json, timeout)
        
        if not r:
            return

        type = r.headers.get('content-type')
        return type

    IF_EXIST = Literal['nothing', 'overwrite', 'resume']
    async def download(self, 
                       url: str, 
                       path: Path | str, 
                       name: Path | str,
                       extension: str = '', # for Windows kids who can't live without .exe and proprietary software
                       ssl: bool = True,
                       headers: dict = {}, 
                       json: dict = {}, 
                       timeout: ClientTimeout | None = None, 
                       mkdir: bool = True, 
                       if_exist: IF_EXIST = 'overwrite',
                       chunk_size: int = 1024):
        def ret(type, val, msg = ''):
            if msg:
                getattr(logging, type)(msg)
            return val
        
        path = self.helper.resolve_path(path)

        if not path.exists():
            logging.error('I miss u... folder~')
            if not mkdir:
                return ret('info', False)

            path.mkdir(parents=True, exist_ok=True)
            logging.info('Oh.. you there!')

        name = self.helper.resolve_path(name)

        name = name.with_suffix(f'.{extension}') if extension else name

        fpath = path / name

        size = 0

        mode = 'wb'

        if fpath.exists():
            match if_exist:
                case 'nothing':
                    return ret('info', True, 'File already exist')
                case 'overwrite':
                    logging.info(f'RIP {fpath.name}')
                case 'resume':
                    size = fpath.stat().st_size
                    headers = headers.copy()
                    headers['Range'] = f'bytes={size}-'
                    mode = 'ab'

        r, st = await self.helper.request(url, headers, 'GET', json, timeout=timeout, ssl=ssl)

        if st == 200 and mode == 'ab':
            return ret('info', False, 'Nope. No rangers here! Change exist mode to overwrite.')
        
        if st == 416:
            return ret('info', True, 'Server cannot satisfy this range(maybe already downloaded)')

        if r:
            with open(fpath, mode) as f:
                async for chunk in r.content.iter_chunked(chunk_size):
                    f.write(chunk)

            if st in (200, 206):
                logging.info(f'File downloaded: {fpath}')
                return ret('info', True, f'File downloaded: {fpath}')
            return ret('error', False, 'Failed to download')
        
        return ret('error', False, 'No response(try to renew your link)')