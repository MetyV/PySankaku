# in progress, idfc bout ts
import asyncio
from pathlib import Path

from api import Sankaku as san
from helper import Helper as hlp
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)

class ILoveShit:
    def __init__(self):
        self.sankaku = san()
        self.helper = hlp()

    async def login(self, login: str = '', password: str = '', token: str = '', timeout: int = 10, headers: dict = {}) -> str | bool | tuple[str, bool]:
        newToken = False
        if token:
            headers = self.sankaku.headers(token)
            t = await self.sankaku.getAccountInfo(headers)
            if t:
                return token
            else:
                newToken = True

        if not login or not password:
            logging.error('Login requires login and password!!!')
            return False
        
        ref = await self.sankaku.getRefreshToken(login, password, timeout, headers)
        if isinstance(ref, bool):
            return ref
        tok = await self.sankaku.exchangeToken(ref, timeout, headers)
        if isinstance(tok, bool):
            return tok
        return (tok, newToken) if newToken else tok

    async def tagMedia(self, File: Path | str, token: str = '', headers: dict = {}, timeout: int = 60) -> list[dict] | bool:
        if token:
            headers = self.sankaku.headers(token)

        if not headers:
            logging.error('I need auth(token or headers) for tagging!!!')
            return False

        a = await self.sankaku.tagMedia(File, headers, timeout)

        return a

    async def postMedia(self, File: Path | str, token: str = '', extraTags: list = [], headers: dict = {}, parentID: str = '', rating: str = 'e', timeout: int = 60, tags: list = []) -> dict | bool:
        if token and not headers:
            headers = self.sankaku.headers(token)

        if not headers:
            logging.error('I need auth(token or headers) for posting!!!')
            return False

        if not tags:
            ttags = await self.tagMedia(File, token=token, headers=headers, timeout=timeout)
            if isinstance(ttags, bool):
                logging.error('Failed to get tags automatically.')
                return False 
            tags = [tag.get('name') for tag in ttags]

        if extraTags:
            tags.extend(extraTags)
            
        return await self.sankaku.postMedia(File, tags, headers, parentID, rating, timeout)

    #async def favorPost(self,) # in future

if __name__ == '__main__':
    async def main():
        fp = ILoveShit()

        tk = await fp.login('login/mail', 'password')

        if isinstance(tk, bool) or isinstance(tk, tuple):
            return

        await fp.sankaku.helper._session_close()
        await fp.helper._session_close() # IMPORTANT!!! nu... ne sovsem

    asyncio.run(main())