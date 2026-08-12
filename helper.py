from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
import aiohttp
import puremagic
from yarl import URL

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
_logger = logging.getLogger(__name__)
logger = _logger

class Helper:
    session: aiohttp.ClientSession | None
    def __init__(self):
        self.session = None

    async def _session_close(self):
        if self.session:
            await self.session.close()
        
    async def _session_init(self):
        if self.session:
            await self._session_close()
        self.session = aiohttp.ClientSession()

    def resolve_path(self, path: Path | str) -> Path:
        return Path(path).resolve() if isinstance(path, str) else path.resolve()
    
    def get_filename_from_url(self, url: str) -> str:
        parsed = urlparse(url)
        return Path(parsed.path).name
    
    async def request(self, url: str, headers: dict, method: str = 'GET', json: dict | None = None, data: aiohttp.FormData | None = None, timeout: int = 30, retries: int = 1, proxy = None) -> tuple:
        ttimeout = aiohttp.ClientTimeout(total=timeout)
        st = None
        def printErr(text):
            logging.error(f'{text}: {st}')
            return (None, None)
        
        if self.session is None:
            await self._session_init()

        assert self.session is not None

        for i in range(1, retries+1):
            try:
                r = await self.session.request(method, url, headers=headers, json=json, data=data, timeout=ttimeout, allow_redirects=True, proxy=proxy)
                st = r.status
                newUrl = r.url
                match st:
                    case 404: return printErr(f'No page')
                    case (301, 302, 303, 307, 308):
                        console.print(f'[yellow]Redirect: {st}[/yellow]')
                        if not isinstance(newUrl, URL): # ne rabotaet navernoe, no vsegda dolzhno byt URL
                            return printErr('No redirect url extracted')
                        return await self.request(newUrl, headers, method, json, data, timeout, retries, proxy)
                    case 400:return printErr('Bad request(invalid request)')
                    case 401:return printErr('Unauthorized(token?)')
                    case 403:return printErr('Forbidden(token?)')
                    case 405:return printErr(f'Wrong method({method})')
                    case 409:return printErr('Conflict')
                    case 410:return printErr('RIP resource')
                    case 415:return printErr('Wrong data type')
                    case 422:return printErr('Unprocessable')
                    case 429:return printErr('Riched RP(D/M)')
                    case 500:return printErr('Internal error') # if you see it more than 5 times, it'll be: real error, shitty code/args or near site reboot
                    case 502:return printErr('Bad gateway')
                    case 503:return printErr('Service unavailable')
                    case 504:return printErr('Timeout')
                return (r, st)
            except Exception as e:
                if i < retries:
                    logging.warning(f'Request error: attempt {i+1}/{retries} - {e}')
                else:
                    logging.error(f'Request failed after {retries} attempts: {e}')
                    return (None, None)
                
    async def getJson(self, url: str, headers: dict, method: str = 'GET', json: dict | None = None, data: aiohttp.FormData | None = None, timeout: int = 30, retries: int = 1, proxy = None) -> Optional[dict]:
        def printErr():
            logging.error('Json data fetch failed')
            return None
        
        resp, _ = await self.request(url, headers, method, json, data, timeout, retries, proxy)

        if resp is None:
            return printErr()
        
        js = await resp.json()
        
        if js:
            logging.info('Json data fetched')
            return js
        
        return printErr()
    
    def get_mime(self, file: Path | str) -> str:
        try:
            return puremagic.from_file(file, mime=True)
        except puremagic.PureError:
            return "application/octet-stream"

# nahuy accounts, budet universal HTTP request helper, kotoriy mozhno ispolzovat dlya vsego, vrode