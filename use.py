# in progress, idfc bout ts
import asyncio
from pathlib import Path
import random
from typing import Literal, Optional

from api import Sankaku
from downloader import Downloader
from helper import Helper as hlp
from helper import logger as logging
from models.collectiondata import CollectionData
from aiohttp import ClientTimeout
from models.postdata import PostData, fPostData
from models.registerdata import RegisterData
from models.taggingdata import TagType, TaggingData, TagData

class ILoveShit:
    def __init__(self, idol: bool = False, stack: bool = False):
        self.sankaku = Sankaku(idol, stack)
        self.helper = hlp(stack)
        self.i = False

    def __nihuyaNet(self, message) -> None:
        logging.error(message)
        return

    async def __aenter__(self):
        await self.sankaku.__aenter__()
        await self.helper.__aenter__()
        self._i = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._i:
            await self.helper.__aexit__(exc_type, exc_val, exc_tb)
            await self.sankaku.__aexit__(exc_type, exc_val, exc_tb)

    async def register(self, login: str, password: str, mail: str, timeout: ClientTimeout | None = None, headers: dict = {}) -> Optional[RegisterData]:
        return await self.sankaku.regAccount(login, password, mail, timeout, headers)

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
        headers = self._chckTK(headers, token)

        res = await self.sankaku.tagMedia(File, headers, timeout)
        if not res or not res.tags:
            return

        return res.tags

    async def postMedia(self, File: Path | str,
                        token: str = '', 
                        extraTags: list = [], 
                        headers: dict | None = None, 
                        parentID: str = '', 
                        rating: rating = 'e', 
                        timeout: ClientTimeout | None = None, 
                        tags: list = []) -> Optional[fPostData]:
        headers = self._chckTK(headers, token)

        if not tags:
            ttags = await self.tagMedia(File, token=token, headers=headers, timeout=timeout)
            if ttags is None:
                self.__nihuyaNet('Failed to get tags automatically.')
                return
            t = self.prepareTags(ttags)
            tags = [tag.name for tag in t]

        if extraTags:
            tags.extend(extraTags)

        res = await self.sankaku.postMedia(File, tags, headers, parentID, rating, timeout)

        if res is None:
            return
            
        return fPostData.model_validate(res)

    CollectionDlMode = Literal['post', 'pool', 'series']
    async def downloadCollection(self, 
                                url: str, 
                                dlMode: CollectionDlMode = 'post',
                                token: str = '', 
                                headers: dict = {}, 
                                quality: Sankaku.QualityType = 0, 
                                path: Path | str = '', 
                                name: Path | str = '', 
                                extension: bool = True, 
                                ssl: bool = True,  
                                json: dict = {},
                                mkdir: bool = True,
                                if_exist: Downloader.IF_EXIST = 'overwrite',
                                chunk_size: int = 1024,
                                suffix: str = '',
                                timeout: ClientTimeout | None = None,
                                ignore_fails: bool = True,
                                custom_indexes: list[int] = []) -> Optional[bool]:
        headers = self._chckTK(headers, token)

        sts = {
            'post': self._gEPosts,
            'pool': self._gEPools,
            'series': self._gESeries
        }

        path = Path(path)

        data = await self._gColDat(url, token, headers, timeout)
        if not data:
            return

        st = sts.get(dlMode)
        if not st:
            return
        
        TIDS = await st(url, token, headers, timeout)
        if not TIDS:
            return
        
        async def ddl(IDS, tpath):
            for i in custom_indexes if custom_indexes else range(len(IDS)):
                a = await self.downloadPost(IDS[i], token, headers, quality, tpath, name, extension, ssl, json, mkdir, if_exist, chunk_size, suffix, f'{i} ', timeout)
                if not a:
                    self.__nihuyaNet(f'Failed to download {i} index with id {IDS[i]}')
                    if not ignore_fails:
                        return
            return True

        if dlMode == 'pool':
            a = []
            for pool, IDS in TIDS:
                a.append(await ddl(IDS, path/Path(pool)))
            return all(a)
        return await ddl(TIDS, path)

    async def _gEPosts(self, url: str, token: str = '', headers: dict | None = None, timeout: ClientTimeout | None = None) -> Optional[list[str]]:
        r = await self._gColDat(url, token, headers, timeout)
        if not r:
            return
        headers, data = r
        if not data.post_ids:
            return
        posts = [p for p in data.post_ids]
        return posts

    async def _gEPools(self, url: str, token: str = '', headers: dict | None = None, timeout: ClientTimeout | None = None) -> Optional[dict]:
        r = await self._gColDat(url, token, headers, timeout)
        if not r:
            return
        headers, data = r
        if not data.pool_ids:
            return
        pools = [p for p in data.pool_ids]
        data={}
        for pool in pools:
            p = await self.sankaku.getBookData(pool, timeout, headers)
            if p and p.posts:
                data[p.name] = [ps.id for ps in p.posts]
        return data

    async def _gESeries(self, url: str, token: str = '', headers: dict | None = None, timeout: ClientTimeout | None = None) -> Optional[list[str]]:
            r = await self._gColDat(url, token, headers, timeout)
            if not r:
                return
            headers, data = r
            if not data.series_ids:
                return
            series = [p for p in data.series_ids]
            # in future maybe
            return
            return posts

    async def _gColDat(self, url: str, token: str = '', headers: dict | None = None, timeout: ClientTimeout | None = None) -> Optional[tuple[dict, CollectionData]]:
        headers = self._chckTK(headers, token)
        id = self.sankaku.getPostID(url)
        data = await self.sankaku.getCollectionData(id, timeout, headers)
        if not data:
            return
        return (headers, data)

    def _chckTK(self, headers: dict | None = None, token: str | None = None) -> dict:
        if not headers:
            headers = self.sankaku.headers(token) if token else self.sankaku._headers.copy()

        return headers

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

    def prepareTags(self, tags: list[TagData]) -> list[TagData]:
        excl = {
            '8yrxk0lnaE6' # "Useless tags", moders dont like this tag
            }

        pt: list[TagData] = [tag for tag in tags if tag.id not in excl]

        return pt

    async def downloadPost(self, 
                           url: str, 
                           token: str = '', 
                           headers: dict = {}, 
                           quality: Sankaku.QualityType = 0, 
                           path: Path | str = '', 
                           name: Path | str = '', 
                           extension: bool = True, 
                           ssl: bool = True,  
                           json: dict = {},
                           mkdir: bool = True,
                           if_exist: Downloader.IF_EXIST = 'overwrite',
                           chunk_size: int = 1024,
                           suffix: str = '',
                           prefix: str = '',
                           timeout: ClientTimeout | None = None) -> Optional[bool]:
        headers = self._chckTK(headers, token)

        postID = self.sankaku.getPostID(url) if url.startswith(('http://', 'https://')) else url

        if not name:
            name = self.helper.get_filename_from_url(url)
        name = Path(name)
        name = Path(prefix + name.stem + suffix)

        pfu = await self.sankaku.getPostFu(postID, timeout, headers, quality)
        if not pfu:
            return

        ext = Path(self.helper.get_filename_from_url(pfu, extension)).suffix[1:] # downloader automatically adds '.'

        async with Downloader() as dlr:
            return await dlr.download(
                pfu,
                path,
                name,
                ext,
                ssl,
                headers,
                json,
                timeout,
                mkdir,
                if_exist,
                chunk_size
            )
    
    #async def getPostData(self, id, headers, )

    #async def favorPost(self,) # in future

if __name__ == '__main__':
    async def main():
        fp = ILoveShit(True)

        # tk = await fp.login('login/email', 'pass')

        # if tk is None:
        #     return
        # tk=tk[0]

        # headers = fp.sankaku.headers(tk)

        # folder = Path("X")
        # extratags = ['']

        # l=[str(file) for file in folder.iterdir() if file.is_file()]
        # err=[]
        
        # for post in l:
        #     ttags = await fp.tagMedia(post, token=tk, headers=headers)
        #     if ttags is None:
        #         fp.__nihuyaNet(f'Failed to get tags. {post}')
        #         err.append(post)
        #         return
        #     tags = [tag.name for tag in ttags]
        #     rating = fp.getMediaRating(ttags, True)
        #     if rating == 's':
        #         rating = 'q' # optional
        #     if not rating:
        #         rating = 'e'
        #     await fp.postMedia(post, tk, extratags, tags=tags, rating=rating)
        #     await asyncio.sleep(random.randrange(0,3))

    asyncio.run(main())