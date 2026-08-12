# in progress, idfc bout ts
import asyncio
from pathlib import Path
from typing import Optional

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

    async def login(self, login: str = '', password: str = '', token: str = '', timeout: int = 10, headers: dict = {}) ->  Optional[tuple[str, bool]]:
        newToken = False
        if token:
            headers = self.sankaku.headers(token)
            t = await self.sankaku.getAccountInfo(headers)
            if t:
                return (token, False)
            else:
                newToken = True

        if not login or not password:
            logging.error('Login requires login and password!!!')
            return
        
        ref = await self.sankaku.getRefreshToken(login, password, timeout, headers)
        if ref is None:
            return
        tok = await self.sankaku.exchangeToken(ref, timeout, headers)
        if tok is None:
            return
        return (tok, newToken)

    async def tagMedia(self, File: Path | str, token: str = '', headers: dict = {}, timeout: int = 60) -> Optional[list[dict]]:
        if token:
            headers = self.sankaku.headers(token)

        if not headers:
            logging.error('I need auth(token or headers) for tagging!!!')
            return

        a = await self.sankaku.tagMedia(File, headers, timeout)

        return a

    async def postMedia(self, File: Path | str,
                        token: str = '', 
                        extraTags: list = [], 
                        headers: dict = {}, 
                        parentID: str = '', 
                        rating: str = 'e', 
                        timeout: int = 60, 
                        tags: list = []) -> Optional[dict]:
        if token and not headers:
            headers = self.sankaku.headers(token)

        if not headers:
            logging.error('I need auth(token or headers) for posting!!!')
            return

        if not tags:
            ttags = await self.tagMedia(File, token=token, headers=headers, timeout=timeout)
            if ttags is None:
                logging.error('Failed to get tags automatically.')
                return 
            tags = [tag.get('name') for tag in ttags]

        if extraTags:
            tags.extend(extraTags)
            
        return await self.sankaku.postMedia(File, tags, headers, parentID, rating, timeout)

    #async def favorPost(self,) # in future

if __name__ == '__main__':
    async def main():
        fp = ILoveShit()

        tk = await fp.login('login/mail', 'password')

        if tk is None:
            return


        await fp.sankaku.helper._session_close()
        await fp.helper._session_close() # IMPORTANT!!! nu... ne sovsem

    asyncio.run(main())