# in progress, idfc bout ts
import asyncio
from pathlib import Path
from typing import Optional

from api import Sankaku as san
from helper import Helper as hlp
from helper import logger as logging
from models.collectiondata import CollectionData
from aiohttp import ClientTimeout
from models.taggingdata import TaggingData

class ILoveShit:
    def __init__(self):
        self.sankaku = san()
        self.helper = hlp()

    def __nihuyaNet(self, message = None) -> None:
        logging.error(message or 'I need token or headers!!!')
        return

    async def login(self, login: str = '', password: str = '', token: str = '', timeout: ClientTimeout | None = None, headers: dict = {}) ->  Optional[tuple[str, bool]]:
        newToken = False
        if token:
            headers = self.sankaku.headers(token)
            t = await self.sankaku.getAccountInfo(headers)
            if t:
                return (token, False)
            else:
                newToken = True

        if not login or not password:
            return self.__nihuyaNet('Login requires login and password!!!')
        
        ref = await self.sankaku.getRefreshToken(login, password, timeout, headers)
        if ref is None:
            return
        tok = await self.sankaku.exchangeToken(ref, timeout, headers)
        if tok is None:
            return
        return (tok, newToken)

    async def tagMedia(self, File: Path | str, token: str = '', headers: dict = {}, timeout: ClientTimeout | None = None) -> Optional[list]:
        if token and not headers:
            headers = self.sankaku.headers(token)

        if not headers:
            return self.__nihuyaNet()

        res = await self.sankaku.tagMedia(File, headers, timeout)
        if not res or not res.tags:
            return

        return res.tags

    async def postMedia(self, File: Path | str,
                        token: str = '', 
                        extraTags: list = [], 
                        headers: dict = {}, 
                        parentID: str = '', 
                        rating: str = 'e', 
                        timeout: ClientTimeout | None = None, 
                        tags: list = []) -> Optional[TaggingData]:
        if token and not headers:
            headers = self.sankaku.headers(token)

        if not headers:
            return self.__nihuyaNet()

        if not tags:
            ttags = await self.tagMedia(File, token=token, headers=headers, timeout=timeout)
            if ttags is None:
                self.__nihuyaNet('Failed to get tags automatically.')
                return
            tags = [tag.name for tag in ttags]

        if extraTags:
            tags.extend(extraTags)

        res = await self.sankaku.postMedia(File, tags, headers, parentID, rating, timeout)

        if res is None:
            return
            
        return res

    async def downloadCollection(self, id: str, token: str = '', headers: dict = {}, timeout: ClientTimeout | None = None) -> None:
        return # sdelayu skoro

    async def getCollectionPostsIDs(self, id: str, token: str = '', headers: dict = {}, timeout: ClientTimeout | None = None) -> Optional[list[str]]:
        data = await self._collectionD(id, token, headers, timeout)

        if not data or not data.post_ids:
            return
        
        posts = [p for p in data.post_ids]
        return posts

    async def _collectionD(self, id: str, token: str = '', headers: dict = {}, timeout: ClientTimeout | None = None) -> Optional[CollectionData]:
        if token and not headers:
            headers = self.sankaku.headers(token)

        if not headers:
            return self.__nihuyaNet()
        
        data = await self.sankaku.getCollectionData(id, timeout, headers)
        return data
    
    #async def getPostData(self, id, headers, )

    #async def favorPost(self,) # in future

if __name__ == '__main__':
    async def main():
        fp = ILoveShit()

        #tk = await fp.login('login/mail', 'password')

        #if tk is None:
        #    return
        #tk=tk[0]

        #headers = fp.sankaku.headers(tk) # mb nado, chto bi vizivat sankaku functions directly(fp.sankaku....)


        # l = [
        #     'path-to-file1'
        #     ]
        # sema = asyncio.Semaphore(2) # chtobi ne nagrujat set i ne lovit timeouts or 429. 2+ isn't stable
        # async def post(q, tk):
        #     async with sema:
        #         await fp.postMedia(q, tk, ['tag1'])

        # await asyncio.gather(*(post(q, tk) for q in l))

        await fp.sankaku.helper._session_close()
        await fp.helper._session_close() # IMPORTANT!!! nu... ne sovsem

    asyncio.run(main())