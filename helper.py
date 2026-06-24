import json
from pathlib import Path
from urllib.parse import urlparse
import aiohttp
import puremagic
from rich.console import Console

console = Console()


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

    async def resolve_path(self, path: Path | str) -> Path:
        return Path(path).resolve() if isinstance(path, str) else path.resolve()
    
    def get_filename_from_url(self, url: str) -> str:
        parsed = urlparse(url)
        return Path(parsed.path).name
    
    async def request(self, url: str, headers: dict, method: str = 'GET', json: dict | None = None, data: aiohttp.FormData | None = None, timeout: int = 30, retries: int = 1) -> tuple[aiohttp.ClientResponse, int] | None:
        ttimeout = aiohttp.ClientTimeout(total=timeout)
        st = None
        def printErr(text):
            console.print(f'[red]{text}: {st}[/red]')
            return None
        
        if self.session is None:
            await self._session_init()

        assert self.session is not None

        for i in range(1, retries+1):
            try:
                r = await self.session.request(method, url, headers=headers, json=json, data=data, timeout=ttimeout, allow_redirects=True)
                st = r.status
                newUrl = r.url
                match st:
                    case 404: return printErr(f'No page')
                    case (301, 302, 303, 307, 308):
                        console.print(f'[yellow]Redirect: {st}[/yellow]')
                        if not isinstance(newUrl, URL): # ne rabotaet navernoe, no vsegda dolzhno byt URL
                            return printErr('No redirect url extracted')
                        return await self.request(newUrl, headers, method, json, data, timeout, retries)
                    case 400:return printErr('Bad request(invalid request)')
                    case 401:return printErr('Unauthorized(token?)')
                    case 403:return printErr('Forbidden(token?)')
                    case 405:return printErr(f'Wrong method({method})')
                    case 409:return printErr('Conflict')
                    case 410:return printErr('RIP resource')
                    case 415:return printErr('Wrong data type')
                    case 422:return printErr('Unprocessable')
                    case 429:return printErr('Riched RP(D/M)')
                    case 500:return printErr('Internal error')
                    case 502:return printErr('Bad gateway')
                    case 503:return printErr('Service unavailable')
                    case 504:return printErr('Timeout')
                return (r, st)
            except Exception as e:
                console.print(f'[yellow]Request error: {i+1} try[/yellow]' if i<retries else f'[red]Request error: {e}[/red]')
                if i>=retries+1:
                    return None
                
    async def getJson(self, url: str, headers: dict, method: str = 'GET', json: dict | None = None, data: aiohttp.FormData | None = None, timeout: int = 30, retries: int = 1) -> dict | None:
        def printErr():
            console.print(f'[red]Json data fetch failed[/red]')
            return None
        
        req = await self.request(url, headers, method, json, data, timeout, retries)

        if req is None:
            return printErr()
        
        js = await req[0].json()
        
        if js:
            console.print('[green]Json data fetched[/green]')
            return js
        
        return printErr()
    
    def get_mime(self, file: Path | str) -> str:
        try:
            return puremagic.from_file(file, mime=True)
        except puremagic.PureError:
            return "application/octet-stream"
    
class accounts:
    def __init__(self) -> None:
        self.accF = Path('accounts.json')

    async def addAcc(self, login: str | None = None, password: str | None = None, mail: str | None = None):
        if self.accF.exists():
            with open(self.accF, 'r') as f:
                accounts = json.load(f)
            next_id = max((int(key) for key in accounts.keys()), default=0) + 1
        else:
            accounts = {}
            next_id = 1

        accounts[str(next_id)] = {
            'mail': mail,
            'login': login,
            'password': password
        }

        with open(self.accF, 'w') as f:
            json.dump(accounts, f, indent=2, ensure_ascii=False)

    async def getAcc(self, all = False, login: str = '', mail: str = '') -> dict:
        if not self.accF.exists():
            return {}

        with open(self.accF, 'r') as f:
            data = json.load(f)
            data = {str(i): acc for i, acc in enumerate(data, 1)} if isinstance(data, list) else data

            if all:
                return data
            
            for acc_id, acc_data in data.items():
                acc_login = acc_data.get('login', '')
                acc_mail = acc_data.get('mail', '')
                
                if (login and (acc_login == login or acc_mail == login)) or \
                (mail and acc_mail == mail):
                    return {acc_id: acc_data}
        return {}