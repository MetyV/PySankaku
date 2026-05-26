from pathlib import Path
import zipfile
import aiohttp
from downloader import SankakuDL as SDL
import asyncio
from rich.console import Console
from helper import Helper as hlp

console = Console()
helper = hlp()

class Sankaku:
    def __init__(self, timeout = 30) -> None:
        self.headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:151.0) Gecko/20100101 Firefox/151.0'}
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def Login(self, login: str, password: str) -> str:
        console.print('[bold cyan]Logging in...[/bold cyan]')
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
                                    token = data.get('access_token')
                                    console.print(f'[green]Login successful: {token[:3]}...{token[-3:]}[/green]')
                                    return token
                elif resp.status == 403:
                    console.print(f'[red]Login failed: HTTP {resp.status}(maybe wrong login or password)[/red]')
        console.print('[red]Login failed[/red]')
        return ''
    
    async def _api_request(self, url: str, headers: dict, method: str = 'GET', json: dict | None = None) -> dict:
        async with aiohttp.ClientSession() as s:
            async with s.request(method, url, headers=headers, json=json, timeout=self.timeout) as resp:
                if resp.status == 200:
                    console.print('[green]API data fetched[/green]')
                    return await resp.json()
                if resp.status == 401:
                    console.print('[red]Token expired or invalid[/red]')
                    return {}
                console.print(f'[yellow]API data fetch failed: HTTP {resp.status}[/yellow]')
        return {}
    
    async def PostData(self, url: str, token: str) -> dict:
        tfetch = await self._fetch_data(url, token, 'post')

        if not tfetch:
            return {}
        
        headers, post_id = tfetch

        url = f'https://sankakuapi.com/v2/posts?lang=en&page=1&limit=1&default_threshold=2&tags=id_range:{post_id}'
    
        return await self._api_request(url, headers, 'GET', None)
    
    async def _fetch_data(self, url: str, token: str, type: str) -> tuple[dict, str] | None:
        console.print(f'[dim]Fetching {type} data...[/dim]')

        headers = self.headers.copy()
        headers['Authorization'] = f'Bearer {token}'

        post_id = await self._getPostID(url)
        if not post_id:
            console.print(f'[red]Failed to extract {type} ID[/red]')
            return None
        
        return headers, post_id
    
    async def BookData(self, url: str, token: str) -> dict:
        tfetch = await self._fetch_data(url, token, 'book')

        if not tfetch:
            return {}
        
        headers, post_id = tfetch

        url = f'https://sankakuapi.com/pools/{post_id}'

        return await self._api_request(url, headers, 'GET', None)
    
    async def _getPostID(self, url: str) -> str:
        import re
    
        match = re.search(r'(?:id_range:|/posts/|/pools/|/books/)([A-Za-z0-9]+)', url)
        return match.group(1) if match else ''
    
    async def _get_fu(self, url: str = '', id: str | None = None, token: str | None = None) -> str:
        id = id if id else await self._getPostID(url)

        headers = self.headers.copy()
        if token:
            headers['Authorization'] = f'Bearer {token}'

        if not id:
            console.print('[red]Failed to extract post ID[/red]')
            return ''
        url = f'https://sankakuapi.com/posts/{id}/fu'
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers, timeout=self.timeout) as resp:
                if resp.status == 200:
                    js: dict = await resp.json()
                    if not js.get('success'):
                        console.print('[red]API returned success=false[/red]')
                        return ''
                    data = js.get('data', {})
                    if not data:
                        console.print('[red]No data in response[/red]')
                    furl = data.get('file_url') or data.get('fallback_url') or data.get('sample_url')
                    if not furl:
                        console.print('[red]No file URL found in response[/red]')
                    return furl
                elif resp.status == 403:
                    console.print(f'[red]Access denied: HTTP {resp.status} (maybe token issue)[/red]')
                else:
                    console.print(f'[yellow]Failed to get file URL: HTTP {resp.status}[/yellow]')
        return ''
    
    async def DlPost(self, path: Path | str, url: str = '', mbSize=100, id: str | None = None, token: str | None = None) -> bool:
        furl = await self._get_fu(url=url, id=id, token=token)
        if not furl:            
            console.print('[red]Failed to get file URL[/red]')
            return False

        return (await SDL(mbSize).download(furl, path, self.timeout))[0]
    
    async def DlBook(self, path: Path | str, url: str = '', pages: int | list[int] | None = None, zip: bool | None = False, id: str | None = None, mbSize=100, token: str | None = None) -> bool:
        id = id or await self._getPostID(url)

        path = await helper.resolve_path(path)

        headers = self.headers.copy()
        if token:
            headers['Authorization'] = f'Bearer {token}'

        if not id:
            console.print('[red]Cannot download: no ID[/red]')
            return False

        url = f'https://sankakuapi.com/pools/{id}'

        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers, timeout=self.timeout) as resp:
                if resp.status == 200:
                    js: dict = await resp.json()
                    posts = js.get('posts', [])
                    if not posts:
                        console.print('[red]No posts in book data (maybe token issue)[/red]')
                        return False
                    
                    if pages is None:
                        selected_posts = posts
                    elif isinstance(pages, int):
                        selected_posts = posts[:pages]
                    elif isinstance(pages, list):
                        selected_posts = [posts[i-1] for i in pages if 0 < i <= len(posts)]
                    else:
                        console.print('[red]Invalid pages parameter[/red]')
                        return False
                    
                    selected_posts = [post.get('id') for post in selected_posts]
                    if not selected_posts:
                        console.print('[red]No posts[/red]')
                        return False

                    tasks = []
                    
                    for i, post_id in enumerate(selected_posts, start=1):
                        furl = await self._get_fu(id=post_id)
                        if furl:
                            tasks.append(SDL(mbSize).download(furl, path, self.timeout, i))

                    results = await asyncio.gather(*tasks)
                    
                    if zip:
                        zip_path = path / 'temp' / f'{id}.zip'
                        zpc = zip_path.parent
                        zpc.mkdir(exist_ok=True, parents=True)
                        
                        of = []
                        
                        for status, file_path, page_index in results:
                            if status and file_path and Path(file_path).exists():
                                file_path = Path(file_path)
                                ext = file_path.suffix
                                new_path = file_path.with_name(f"{page_index:03d}{ext}")
                                file_path.move(new_path)
                                of.append(new_path)

                        of.sort()

                        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_STORED) as zf:
                            for file in of:
                                if file.is_file():
                                    console.print(f'[dim]Adding {file.name} to archive...[/dim]')
                                    zf.write(file, arcname=file.name)
                                    file.unlink()
                                    
                        final_zip_path = path / f'{id}.zip'
                        zip_path.move(final_zip_path)
                        zpc.rmdir()
                        
                        console.print(f'[green]Book downloaded and zipped to {final_zip_path}[/green]')
                    else:
                        console.print(f'[green]Book downloaded to {path}[/green]')
                    return True
                elif resp.status == 403:
                    console.print(f'[red]Access denied: HTTP {resp.status} (maybe token issue)[/red]')
                else:
                    console.print(f'[yellow]Failed to get book data: HTTP {resp.status} (use your token and/or try again)[/yellow]')
        return False
    
if __name__ == '__main__':
    async def main():
        sankaku = Sankaku()
        #asd = Path('/mnt/fa/.tmp/')
        #token = await sankaku.Login('login', 'password')
        #await sankaku.DlBook('/mnt/fa/.tmp/book/sanLike/', 'https://www.sankakucomplex.com/books/1QaEoLLbR9L', 3, True, token=token) # OK
        #await sankaku.DlPost(asd / 'post' / 'sanLike/', url='https://www.sankakucomplex.com/posts/1QaE3ZGG5R9') # OK
        #await sankaku.DlBook('/mnt/fa/.tmp/book/directID/', id='78MYvGDoaew', zip=True, token=token) # OK
        #await sankaku.DlPost('/mnt/fa/.tmp/post/directID/', id='1QaE3ZGG5R9') # OK
        #await sankaku.DlBook(asd / 'book' / 'partial', url='https://www.sankakucomplex.com/books/GelR0z5kagK', pages=[1,3], zip=True) # OK
        #await sankaku.DlPost('/mnt/fa/.tmp/post/directURL/', url='https://sankakuapi.com/posts/1QaE3ZGG5R9/fu?lang=en') # OK
        #await sankaku.DlBook('/mnt/fa/.tmp/book/directURL/', url='https://sankakuapi.com/pools/GelR0z5kagK?lang=en&exceptStatuses[]=deleted', pages=[2], zip=False) # OK
        #await sankaku.DlPost(asd / 'post' / 'segmented', url='https://www.sankakucomplex.com/posts/1QaE3ZGG5R9', mbSize=0) # OK
        #await sankaku.DlBook('/mnt/fa/.tmp/book/segmented/', url='https://sankakuapi.com/pools/GelR0z5kagK?lang=en&exceptStatuses[]=deleted', pages=[2], zip=False, mbSize=0) # OK

    asyncio.run(main())