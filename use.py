# in progress, idfc bout ts
import asyncio
from pathlib import Path
import random
from typing import Literal, Optional

from api import Sankaku as san
from helper import Helper as hlp
from helper import logger as logging
from models.collectiondata import CollectionData
from aiohttp import ClientTimeout
from models.taggingdata import TaggingData, TagData

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

    async def tagMedia(self, File: Path | str, token: str = '', headers: dict = {}, timeout: ClientTimeout | None = None) -> Optional[list[TagData]]:
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
                        rating: rating = 'e', 
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

    rating = Literal['s', 'q', 'e']
    def getMediaRating(self, tags: list[TagData], forceE: bool = False) -> Optional[rating]:
        r = None
        for tag in tags:
            match tag.id:
                case '1QaEJ4zer9L':
                    r='e'
                case 'elR0EeLpMgK':
                    r='q'
                case 'GelR09GqMgK':
                    r='s'
                
        MASK = {'lb8aJDKR2L1', '36dMpeqQaxj', 'QjXajQGM2P7'}
        if forceE:
            tag_ids = {tag.id for tag in tags}
            r = 'e' if MASK.issubset(tag_ids) else r
            '''
            often q rating is not valid. here tags that often together, but such a "mask" can be wrong in special cases(e.g. only male on media)
            1. (ID: lb8aJDKR2L1)
            2. (ID: 36dMpeqQaxj)
            3. (ID: QjXajQGM2P7)
            '''
        return r
            
    
    #async def getPostData(self, id, headers, )

    #async def favorPost(self,) # in future

if __name__ == '__main__':
    async def main():
        fp = ILoveShit()

        tk = await fp.login('login/email', 'pass')

        if tk is None:
            return
        tk=tk[0]

        headers = fp.sankaku.headers(tk) # mb nado, chto bi vizivat sankaku functions directly(fp.sankaku....)

        folder = Path("X")

        l=[str(file) for file in folder.iterdir() if file.is_file()]
        err=[]
        
        for post in l:
            ttags = await fp.tagMedia(post, token=tk, headers=headers)
            if ttags is None:
                fp.__nihuyaNet(f'Failed to get tags. {post}')
                err.append(post)
                return
            tags = [tag.name for tag in ttags]
            rating = fp.getMediaRating(ttags, True)
            if rating == 's':
                rating = 'q' # optional
            if not rating:
                rating = 'e'
            await fp.postMedia(post, tk, ['extratag'], tags=tags, rating=rating)
            await asyncio.sleep(random.randrange(0,3))

        print(err)

        await fp.sankaku.helper._session_close()
        await fp.helper._session_close() # IMPORTANT!!! nu... ne sovsem

    asyncio.run(main())