from pathlib import Path
import aiohttp
from downloader import SankakuDL as SDL
import asyncio
from rich.console import Console

console = Console()

class Sankaku:
    def __init__(self, timeout = 30) -> None:
        self.headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:151.0) Gecko/20100101 Firefox/151.0'}
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def Login(self, login: str, password: str) -> str:
        console.print('bold cyan]Logging in...[/bold cyan]')
        async with aiohttp.ClientSession() as s:
            async with s.post('https://login.sankakucomplex.com/auth/token', json={
                "login":login,
                "password":password,
                "mfaParams":{"login":login}},
                headers=self.headers,
                timeout=self.timeout) as resp:
                
                if resp.status == 200:
                    data = await resp.json()
                    if data:
                        token = data.get('access_token')
                        async with s.post('https://sankakuapi.com/sso/token-exchange',
                                           json={
                                               "access_token":token,
                                               "client_id":"sankaku-web-app",
                                               "url":"https://www.sankakucomplex.com"
                                               }) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if data:
                                    return data.get('access_token')
        console.print('[red]Login failed[/red]')
        return ''
    
    async def PostData(self, url: str, token: str) -> dict:
        console.print('[dim]Fetching post data...[/dim]')

        headers = self.headers.copy()
        headers['Authorization'] = f'Bearer {token}'

        post_id = await self._getPostID(url)
        
        if not post_id:
            console.print('[red]Failed to extract post ID[/red]')

        url = f'https://sankakuapi.com/v2/posts?lang=en&page=1&limit=1&default_threshold=2&tags=id_range:{post_id}'
        
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers, timeout=self.timeout) as resp:
                if resp.status == 200:
                    console.print('[green]Post data fetched[/green]')
                    return await resp.json()
                console.print(f'[yellow]Post data fetch failed: HTTP {resp.status}[/yellow]')
        return {}
    
    async def BookData(self, url: str, token: str) -> dict:
        console.print('[dim]Fetching book data...[/dim]')

        headers = self.headers.copy()
        headers['Authorization'] = f'Bearer {token}'

        post_id = await self._getPostID(url)
        if not post_id:
            console.print('[red]Failed to extract book ID[/red]')
            return {}

        url = f'https://sankakuapi.com/pools/{post_id}'

        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers, timeout=self.timeout) as resp:
                if resp.status == 200:
                    console.print('[green]Book data fetched[/green]')
                    return await resp.json()
                console.print(f'[yellow]Book data fetch failed: HTTP {resp.status}[/yellow]')
        return {}
    
    async def _getPostID(self, url: str) -> str:
        import re
    
        match = re.search(r'(?:id_range:|/posts/|/pools/|/books/)([A-Za-z0-9]+)', url)
        return match.group(1) if match else ''
    
    async def DlPost(self, url: str, path: Path | str, mbSize=100):
        id = await self._getPostID(url)

        if not id:
            console.print('[red]Cannot download: no ID[/red]')
            return False

        url = f'https://sankakuapi.com/posts/{id}/fu'

        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=self.headers, timeout=self.timeout) as resp:
                if resp.status == 200:
                    js: dict = await resp.json()
                    if not js.get('success'):
                        console.print('[red]API returned success=false[/red]')
                        return False
                    data = js.get('data', {})
                    if not data:
                        console.print('[red]No data in response[/red]')
                        return False
                    furl = data.get('file_url') or data.get('fallback_url') or data.get('sample_url')
                    if not furl:
                        console.print('[red]No file URL found in response[/red]')
                        return False
                    
                    return await SDL(mbSize).download(furl, path, self.timeout)
                else:
                    print(resp.status)
        return False