from pathlib import Path
import random
import shutil
import zipfile
import aiohttp
from downloader import SankakuDL as SDL
import asyncio
from rich.console import Console
from helper import Helper as hlp
from helper import accounts

console = Console()

class Sankaku:
    def __init__(self) -> None:
        self.headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:151.0) Gecko/20100101 Firefox/151.0'}
        self.helper = hlp()

    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.helper._session_close()

    async def Login(self, login: str, password: str, retries: int = 1, timeout: int = 30) -> str | None:
        def err():
            console.print(f'[red]Login failed[/red]')
            console.print(f'[dim]{login} : {password}[/dim]')
            return None
        
        console.print('[bold cyan]Logging in...[/bold cyan]')
        firstData = await self.helper.getJson('https://login.sankakucomplex.com/auth/token', self.headers, 'POST', {
                "login":login,
                "password":password,
                "mfaParams":{"login":login}
                }, timeout=timeout, retries=retries)
        
        if firstData is None:
            return err()
        
        ttoken = firstData.get('access_token')
        if not isinstance(ttoken, str):
            return err()
        
        secData = await self.helper.getJson('https://sankakuapi.com/sso/token-exchange', self.headers, 'POST', {
                                        "access_token":ttoken,
                                        "client_id":"sankaku-web-app",
                                        "url":"https://www.sankakucomplex.com"
                                        }, timeout=timeout, retries=retries)
            
        if secData is None:
            return err()
        
        token = secData.get('access_token')
        if not isinstance(token, str):
            return err()
        
        console.print(f'[green]Login successful: {token[:3]}...{token[-3:]}[/green]')
        return token
    
    async def PostData(self, url: str, token: str, timeout: int = 30, retries: int = 30) -> dict | None:
        tfetch = await self._fetch_data(url, token, 'post')

        if not tfetch:
            return {}
        
        headers, post_id = tfetch

        url = f'https://sankakuapi.com/v2/posts?lang=en&page=1&limit=1&default_threshold=2&tags=id_range:{post_id}'
    
        return await self.helper.getJson(url, headers, 'GET', None, timeout=timeout, retries=retries)
    
    async def _headers(self, token: str | None = None) -> dict:
        headers = self.headers.copy()
        if token:
            headers['Authorization'] = f'Bearer {token}'

        return headers

    async def _fetch_data(self, url: str, token: str, type: str) -> tuple[dict, str] | None:
        console.print(f'[dim]Fetching {type} data...[/dim]')

        headers = await self._headers(token)

        post_id = await self._getPostID(url)
        if not post_id:
            console.print(f'[red]Failed to extract {type} ID[/red]')
            return None
        
        return headers, post_id
    
    async def BookData(self, url: str, token: str, timeout: int = 30, retries: int = 30) -> dict | None:
        tfetch = await self._fetch_data(url, token, 'book')

        if not tfetch:
            return {}
        
        headers, post_id = tfetch

        url = f'https://sankakuapi.com/pools/{post_id}'

        return await self.helper.getJson(url, headers, 'GET', None, timeout=timeout, retries=retries)
    
    async def _getPostID(self, url: str) -> str | None:
        import re
    
        match = re.search(r'(?:id_range:|/posts/|/pools/|/books/)([A-Za-z0-9]+)', url)
        if not match:
            console.print('[red]Failed to get post id[/red]')
            return None
        return match.group(1)
    
    async def _get_fu(self, url: str = '', id: str | None = None, token: str | None = None, timeout: int = 30, retries: int = 1) -> str | None:
        def err():
            console.print('[red]Failed to get file URL[/red]')
            return None
        
        id = id if id else await self._getPostID(url)

        headers = await self._headers(token)
        
        url = f'https://sankakuapi.com/posts/{id}/fu'
        
        data = await self.helper.getJson(url, headers, timeout=timeout, retries=retries)
        if data is None:
            return err()
        furl = data.get('file_url') or data.get('fallback_url') or data.get('sample_url')
        if not furl:
            return err()
        return furl
    
    async def DlPost(self, path: Path | str, url: str = '', mbSize=100, id: str | None = None, token: str | None = None, timeout: int = 30, retries: int = 1) -> bool:
        furl = await self._get_fu(url=url, id=id, token=token, timeout=timeout, retries=retries)
        if furl is None:            
            console.print('[red]Failed to dl[/red]')
            return False

        path = await self.helper.resolve_path(path)

        return (await SDL(mbSize).download(furl, path, timeout, retries = retries))[0]
    
    async def DlBook(self,
                    path: Path | str,
                    url: str = '',
                    pages: int | list[int] | None = None,
                    zip: bool | None = False,
                    id: str | None = None,
                    mbSize=100,
                    token: str | None = None,
                    timeout: int = 30,
                    retries: int = 1,
                    semaphore = 5) -> bool:
        
        def err():
            console.print('[red]Failed to dl[/red]')
            return False
        
        id = id or await self._getPostID(url)

        path = await self.helper.resolve_path(path)

        headers = await self._headers(token)

        if not id:
            return err()

        url = f'https://sankakuapi.com/pools/{id}'

        data = await self.helper.getJson(url, headers, timeout=timeout, retries=retries)
        if data is None:
            return err()
        
        posts = data.get('posts', [])
        if not posts:
            console.print('[red]No posts in book data (maybe token issue)[/red]')
            return err()
        
        if pages is None:
            selected_posts = posts
        elif isinstance(pages, int):
            selected_posts = posts[:pages]
        elif isinstance(pages, list):
            selected_posts = [posts[i-1] for i in pages if 0 < i <= len(posts)]
        else:
            console.print('[red]Invalid pages parameter[/red]')
            return err()
        
        selected_posts = [post.get('id') for post in selected_posts]
        if not selected_posts:
            console.print('[red]No posts[/red]')
            return err()

        tasks = []
        
        async def dl(post_id, i, sema):
            async with sema:
                furl = await self._get_fu(id=post_id, token=token, timeout=timeout, retries=retries)
                if furl:
                    return await SDL(mbSize).download(furl, path, timeout, i, retries)

        sema = asyncio.Semaphore(semaphore)
        for i, post_id in enumerate(selected_posts, start=1):
            tasks.append(dl(post_id, i, sema))

        results = await asyncio.gather(*tasks)
        
        if zip:
            zip_path = path / 'temp' / f'{id}.zip'
            zpc = zip_path.parent
            zpc.mkdir(exist_ok=True, parents=True)
            
            of = []
            
            for status, file_path, page_index in results:
                if page_index is None:
                    console.print(f'[red]Missing page index for file {file_path}. ABORTING!!![/red]')
                    return err()
                if not status or file_path is None:  # 'None' file_path?!! SKIP SKIP SKIP!!!
                    console.print(f'[red]Failed to download page {page_index} (file: {file_path})[/red]')
                    continue
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
            zip_path.rename(final_zip_path)
            shutil.rmtree(zpc, ignore_errors=True)
            
            console.print(f'[green]Book downloaded and zipped to {final_zip_path}[/green]')
        else:
            console.print(f'[green]Book downloaded to {path}[/green]')
        return True
    
    async def close_session(self):
        await self.helper._session_close()

    async def votePost(self, url: str, rating: int | list[int], token: str | list[str], id: str | None = None):
        id = id if id else await self._getPostID(url)
        
        apiurl = f'https://sankakuapi.com/posts/{id}/vote'
        token = [token] if isinstance(token, str) else token
        rating = [rating] if isinstance(rating, int) else rating
        if len(rating) < len(token):
            rating = (rating * (len(token) // len(rating) + 1))[:len(token)]
        r = [
            ({'score': rating[i]}, await self._headers(token[i]))
            for i in range(len(token))
        ]
        tasks = [self.helper.request(apiurl, header, 'PUT', js) for js, header in r]
        await asyncio.gather(*tasks)
        console.print(f'[green]Voted on post {id} with ratings {rating}[/green]')
    
    async def regAcc(self, login: str | None = None, password: str | None = None, mail: str | None = None) -> bool:
        url = 'https://login.sankakucomplex.com/users'
        json={
            "entry_query":"Y2xpZW50X2lkPXNhbmtha3Utd2ViLWFwcCZsYW5nPWVuJnJlZGlyZWN0X3VyaT1odHRwcyUzQSUyRiUyRnNhbmtha3UuYXBwJTJGc3NvJTJGY2FsbGJhY2smcmVzcG9uc2VfdHlwZT1jb2RlJnJvdXRlPXJlZ2lzdHJhdGlvbiZzY29wZT1vcGVuaWQmc3RhdGU9cmV0dXJuX3VyaSUzRGh0dHBzJTNBJTJGJTJGc2Fua2FrdS5hcHAlMkZhdXRoJnRoZW1lPXdoaXRlJnRvX3BheW1lbnRzPWZhbHNl",
            "user":{
                "name":login,
                "password":password,
                "password_confirmation":password,
                "email": mail},
            "lang":"en"
            }

        headers = await self._headers()

        resp = await self.helper.request(url, headers, 'POST', json)
        if resp is not None and resp[1] == 200:
            console.print(f'[green]Reg success: {mail}:{password}[/green]')
            return True
        console.print(f'[red]Reg fail: {mail}:{password}[/red]')
        return False

    async def resendVerification(self, token: str):
        url = 'https://sankakuapi.com/auth/request-validation'
        
        headers = await self._headers(token)

        resp = await self.helper.request(url, headers, 'POST')
        if resp:
            console.print(f'[green]Verification resended[/green]')
            return True
        console.print(f'[red]Verification resend fail[/red]')
        return False

    async def contentFilter(self, token: str | None = None, enable: bool = False, id: str | None = None, login: str | None = None, password: str | None = None) -> bool:
        def err(text):
            console.print(f'[red]Content filter switch error: {text}[/red]')
            return False
        
        token = token if token else await self.Login(login, password) if login and password else None
        if token is None:
            return err('token')
        
        id = id or await self.getAccId(token)
        if id is None:
            return err('id')

        url=f'https://sankakuapi.com/users/{id}'
        json = {
            "user":{
                "filter_content":enable
                }
            }

        headers = await self._headers(token)

        resp = await self.helper.request(url, headers, 'PUT', json)
        if resp and resp[1] == 200:
            console.print('[green]Content filter switched[/green]')
            return True
        return False

    async def getAccId(self, token: str):
        url = 'https://sankakuapi.com/users/me'
        headers = await self._headers(token)

        resp = await self.helper.getJson(url, headers)
        if resp:
            res = resp.get('user', {}).get('id')
            console.print(f'[green]Account ID: {res}[/green]')
            return res
        return None
    
    async def favorPost(self, url: str | None = None, token: str | None = None, fav: bool = True, id: str | None = None, timeout: int = 30, retries: int = 1) -> bool:
        id = id if id else await self._getPostID(url) if url else None
        if not id:
            console.print('[red]Failed to favor[/red]')
            return False
        
        url = f'https://sankakuapi.com/posts/{id}/favorite'
        headers = await self._headers(token)

        r = await self.helper.request(url, headers, 'POST' if fav else 'DELETE', {'post_id': id}, timeout=timeout, retries=retries)
        if r and r[1] == 200:
            console.print(f'[green]Post {id} {"favored" if fav else "unfavored"}[/green]')
            return True
        console.print(f'[red]Failed to favor post {id}[/red]')
        return False
    
    async def TagMedia(self, File: Path | str, token: str, timeout: int = 30, retries: int = 1) -> list[str] | bool:
        File = await self.helper.resolve_path(File)
        if not File.exists():
            console.print(f'[red]File {File} does not exist[/red]')
            return False
        
        mime = self.helper.get_mime(File)
        mimet = mime.split('/')
        configs = {
            'image': {
                'url': 'https://sankakuapi.com/posts/tagging_image',
                'field': 'art[image_input]'
            },
            'video': {
                'url': 'https://sankakuapi.com/posts/tagging_video',
                'field': 'art[video_input]'
            }
        }
        if mimet[0] not in configs:
            console.print(f'[red]Unsupported file type: {mime}[/red]')
            return False
        
        config = configs['video'] if mimet[1] == 'gif' else configs[mimet[0]]
        url = config['url']
        fieldName = config['field']
        
        headers = await self._headers(token)
        data = aiohttp.FormData()
        with open(File, 'rb') as f:
            data.add_field(fieldName, f.read(), filename=File.name, content_type=mime)

        resp = await self.helper.getJson(url, headers, 'POST', data=data, timeout=timeout, retries=retries)

        return resp[1] if resp else False

if __name__ == '__main__':
    async def main():
        sankaku = Sankaku()
        token = await sankaku.Login('login', 'password')
        if token is None:
            return

        await sankaku.helper._session_close() # IMPORTANT!!!

    asyncio.run(main())