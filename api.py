#!/usr/bin/env python3
import asyncio
import json
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode, urlparse

import aiofiles
import aiohttp
from aiohttp import ClientTimeout

from endpoints import *
from helper import Helper as hlp
from helper import logger as logging
from models.accountdata import AccountData
from models.avatar import AvatarModel
from models.bookdata import BookData
from models.collectiondata import (
    CollectionCreating,
    CollectionData,
    collectionAddItem,
    collectionRemAddResponse,
)
from models.postdata import PostData, PostTagsData, fPostData
from models.registerdata import RegisterData
from models.searchdata import SearchData
from models.suc import suc
from models.taggingdata import TaggingData


class Sankaku(Endpoints):
    '''
    Maybe rabotaet with idol. I'll check it potom.
    '''
    def __init__(self, idol: bool = False, stack: bool = False):
        super().__init__(idol)
        self._headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0'}
        self.helper = hlp(stack)

    async def __aenter__(self):
        await self.helper._session_init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.helper._session_close()

    async def getRefreshToken(self, login: str, password: str, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> str | None:
        def err():
            logging.error('Refresh token retrieval failed')

        logging.info('Retrieving refresh token...')

        if not headers:
            headers = self._headers

        data = await self.helper.getJson(self.LOGIN_REFRESH_TOKEN, headers, 'POST', {
                "login":login,
                "password":password,
                "mfaParams":{"login":login}
                }, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

        if data is None:
            return err()

        token = data.get('access_token')

        if not token:
            return err()

        logging.info('Refresh token retreived')

        return token

    async def exchangeToken(self, refToken: str, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> str | None:
        def err():
            logging.error('Token retrieval failed')

        logging.info('Retrieving token...')

        if not headers:
            headers = self._headers

        data = await self.helper.getJson(self.TOKEN_EXCHANGE, headers, 'POST', {
            "access_token":refToken,
            "client_id":self.CLIENT_ID,
            "url":self.BASE_URL
            }, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

        if data is None:
            return err()

        token = data.get('access_token')

        if not token:
            return err()

        logging.info('Token retrieved')

        return token

    def headers(self, token: str, headers: dict | None = None) -> dict:
        '''
        ya leniviy, tak chto on self doing this auth shit
        '''
        headers = self._headers.copy() if not headers else headers.copy()
        headers['Authorization'] = f'Bearer {token}'
        return headers

    def getPostID(self, url: str) -> str:
        '''
        works with:
        Posts
        Collections
        Books
        ...?
        '''
        parsed = urlparse(url).path
        post_id = parsed.split('/')[-1]
        return post_id

    QualityType = Literal[0, 1, 2, 3]
    async def getPostFu(self, id, timeout: ClientTimeout | None = None, headers: dict | None = None, quality: QualityType = 0, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> str | None:
        '''
        quality: 0 - best possible, 1 - sample, 2 - fallback, 3 - file_url
        '''
        def err():
            logging.error(f'Failed to retrieve post {id} file URL with {quality} quality.')

        if not headers:
            headers = self._headers

        url = f'{self.API_POSTS_URL}/{id}/fu'
        data = await self.helper.getJson(url, headers, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)
        if data is None:
            return err()
        fdata = data.get('data')
        if not fdata:
            return err()

        def w(q):
            furl = None
            match q:
                case 1:
                    furl = fdata.get('sample_url')
                case 2:
                    furl = fdata.get('fallback_url')
                case 3:
                    furl = fdata.get('file_url')
            return furl

        furl = w(quality) if quality else (w(3) or w(2) or w(1))

        if not furl:
            return err()
        logging.info(f'Post {id} file URL retrieved with {quality} quality')
        return furl

    async def getBookData(self, id, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> BookData | None:
        def err():
            logging.error(f'Failed to retrieve book {id} data.')

        if not headers:
            headers = self._headers

        url = f'{self.API_BOOKS_URL}/{id}'
        data = await self.helper.getJson(url, headers, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)
        if data is None:
            return err()
        return BookData.model_validate(data)

    async def getPostData(self, id, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> PostData | None:
        def err():
            logging.error(f'Failed to retrieve post {id} data.')

        if not headers:
            headers = self._headers

        url = f'{self.BASE_API_URL}/v2/posts?&page=1&limit=1&default_threshold=0&tags=id_range:{id}'
        data = await self.helper.getJson(url, headers, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)
        if data is None:
            return err()
        data=data[0]
        return PostData.model_validate(data) # not tested

    async def getPostTags(self, id, timeout: ClientTimeout | None = None, headers: dict | None = None, page: int = 1, limit: int = 200, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> PostTagsData | None:
        def err():
            logging.error(f'Failed to retrieve post {id} tags.')
        if not headers:
                headers = self._headers

        url = f'{self.API_POSTS_URL}/{id}/tags?page={page}&limit={limit}'
        data = await self.helper.getJson(url, headers, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)
        if data is None:
            return err()
        return PostTagsData.model_validate(data)

    VoteScore = Literal[0, 1, 2, 3, 4, 5]
    async def votePost(self, id, vote: VoteScore = 5, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> dict | None:
        '''
        0 - remove vote, 1-5 - vote score
        '''
        def err():
            logging.error(f'Failed to vote: {id}.')

        if not headers:
            headers = self._headers

        method = 'PUT' if vote > 0 else 'DELETE'

        url = f'{self.API_POSTS_URL}/{id}/vote'
        data = await self.helper.getJson(url, headers, method, {'score': vote}, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)
        if data is None:
            return err()
        return data

    async def regAccount(self, login: str, password: str, mail: str, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> RegisterData | None:
        json={
            "entry_query":"Y2xpZW50X2lkPXNhbmtha3Utd2ViLWFwcCZsYW5nPWVuJnJlZGlyZWN0X3VyaT1odHRwcyUzQSUyRiUyRnNhbmtha3UuYXBwJTJGc3NvJTJGY2FsbGJhY2smcmVzcG9uc2VfdHlwZT1jb2RlJnJvdXRlPXJlZ2lzdHJhdGlvbiZzY29wZT1vcGVuaWQmc3RhdGU9cmV0dXJuX3VyaSUzRGh0dHBzJTNBJTJGJTJGc2Fua2FrdS5hcHAlMkZhdXRoJnRoZW1lPXdoaXRlJnRvX3BheW1lbnRzPWZhbHNl",
            "user":{
                "name":login,
                "password":password,
                "password_confirmation":password,
                "email": mail},
            "lang":"en"
            }

        if not headers:
            headers = self._headers

        data = await self.helper.getJson(self.REGISTER_API_URL, headers, 'POST', json, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)
        if data is None:
            logging.error('Registration failed')
            return
        logging.info('Registration successful')
        return RegisterData.model_validate(data)

    async def resendVerif(self, headers: dict, timeout: ClientTimeout | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> dict | None:
        data = await self.helper.getJson(self.API_REQUEST_RESEND_VERIFICATION, headers, 'POST', timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)
        if data is None:
            logging.error('Failed to resend verification code')
            return
        logging.info('Verification code resent successfully')
        return data

    async def getAccountInfo(self, headers: dict, id: str = 'me', timeout: ClientTimeout | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> AccountData | None:
        data = await self.helper.getJson(f'{self.USERS_API_URL}/{id}', headers, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

        if data is None:
            logging.error('Failed to get account info')
            return None

        user = data.get('user')
        if not user or not isinstance(user, dict):
            logging.error('Invalid user data in response')
            return None

        logging.info('Account info retrieved successfully')
        return AccountData.model_validate(user)

    async def setAccountInfo(self, headers: dict, id: str, update_data: AccountData, timeout: ClientTimeout | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> AccountData | None:
        '''
        Returns data like getAccountInfo
        here dohuya vozmojnogo but i'm too lazy to find it
        '''
        payload = {"user": update_data.model_dump(exclude_none=True)}
        data = await self.helper.getJson(
            f'{self.USERS_API_URL}/{id}',
            headers,
            'PUT',
            payload,
            timeout=timeout,
            retries=retries,
            proxy=proxy,
            ssl=ssl
        )

        if data is None:
            logging.error('Failed to update account info')
            return

        user = data.get('user')
        if not user:
            logging.error('No user data in response after update')
            return

        logging.info('Account info updated successfully')
        return AccountData.model_validate(user)

    async def favor(self, headers: dict, id: str, isbook: bool, fav: bool = True, timeout: ClientTimeout | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> dict | None:
        url = f'{self.API_BOOKS_URL if isbook else self.API_POSTS_URL}/{id}/favorite'

        data = await self.helper.getJson(url, headers, 'POST' if fav else 'DELETE', timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

        if data is None:
            logging.error(f'Failed to fav {id}')
            return
        logging.info(f'Set favor {fav} for {id}')
        return data

    async def _ebaniyFile(self, File: Path | str, headers: dict, timeout: ClientTimeout | None = None, post: bool = False, cdata: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> TaggingData | fPostData | None:
        File = self.helper.resolve_path(File)
        if not File.exists():
            logging.error(f'File {File} does not exist')
            return

        mime = self.helper.get_mime(File)
        mimet = mime.split('/')
        configs = {
            'image': {
                'url': f'{self.API_POSTS_URL}/tagging_image',
                'field': 'art[image_input]'
            },
            'video': {
                'url': f'{self.API_POSTS_URL}/tagging_video',
                'field': 'art[video_input]'
            }
        }
        if mimet[0] not in configs:
            logging.error(f'Unsupported file type: {mime}')
            return

        config = configs['video'] if mimet[1] == 'gif' else configs[mimet[0]]
        url = self.API_POSTS_URL if post else config['url']
        fieldName = 'post[file]' if post else config['field']

        data = aiohttp.FormData()
        async with aiofiles.open(File, "rb") as f:
            content = await f.read()

        data = aiohttp.FormData()
        data.add_field(fieldName, content, filename=File.name, content_type=mime)

        if cdata:
            for key, value in cdata.items():
                if not value:
                    continue
                data.add_field(key, str(value))

        resp = await self.helper.getJson(
            url,
            headers,
            "POST",
            data=data,
            timeout=timeout,
            retries=retries,
            proxy=proxy,
            ssl=ssl,
        )

        if resp is None:
            logging.error('API request failed, response is None')
            return None

        if post:
            return fPostData.model_validate(resp)
        else:
            return TaggingData.model_validate(resp)

    async def tagMedia(self, File: Path | str, headers: dict, timeout: ClientTimeout | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> TaggingData | None:
        resp = await self._ebaniyFile(File, headers=headers, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

        if resp is None:
            logging.error('Failed to tag')
            return

        return TaggingData.model_validate(resp)

    async def postMedia(self, File: Path | str, tags: list, headers: dict, parentID: str = '', rating: str = 'e', timeout: ClientTimeout | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> fPostData | None:
        tagss = json.dumps([{"name": tag} for tag in tags])
        data = {
            "post[parent_id]": parentID,
            "post[rating]": rating,
            "post[tags]": tagss,
            "post[upload_url]": "",
            "post[pool_id]": "",
            "post[reupload_post_id]": ""
        }

        resp = await self._ebaniyFile(File, headers, timeout=timeout, post=True, cdata=data, retries=retries, proxy=proxy, ssl=ssl)

        if resp is None:
            logging.error('Failed to post')
            return

        return fPostData.model_validate(resp)

    async def changeAvatar(self,
                           userID: str | int,
                           postID: str,
                           headers: dict,
                           left: float = 0,
                           right: float = 0,
                           top: float = 0,
                           bottom: float = 0,
                           timeout: ClientTimeout | None = None,
                           retries: int = 2,
                           proxy: str | None = None,
                           ssl: bool = True) -> dict | None:
        url = f'{self.USERS_API_URL}/{userID}/avatar'

        json = AvatarModel(post_id=postID, left=left, right=right, top=top, bottom=bottom)

        return await self.helper.getJson(url, headers, 'PUT', json.model_dump(), timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)


    async def getOrCreateCollection(self, data: str | CollectionCreating, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> CollectionData | None:
        typee = 'retrieve' if isinstance(data, str) else 'create'
        url = self.API_COLLECTIONS_URL

        if not headers:
            headers = self._headers

        method = 'GET'
        js={}
        if typee == 'retrieve':
            url+=f'/{data}'
        else:
            js = data.model_dump() # type: ignore . typehint is shitty shit
            method = 'POST'

        res = await self.helper.getJson(url, headers, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl, method=method, json=js)

        if res is None:
            logging.error(f'Failed to {typee} collection.')
            return

        dat = CollectionData.model_validate(res)

        if typee == 'create':
            logging.info(f'Created collection {dat.id}')

        return dat

    def _add_param(self, parts: list, key: str, value: str | int | None, fmt: str = "{}:{}"):
        if value is not None:
            parts.append(fmt.format(key, value))

    async def searchPosts(
        self,
        timeout: ClientTimeout | None = None,
        headers: dict | None = None,
        tags: list | None = None,
        nextH: str | None = None,
        rating: str | None = None,
        order: str | None = None,
        threshold: int = 0,
        page: int = 1,
        file_type: str | None = None,
        voted_by: str | None = None,
        fav_by: str | None = None,
        posted_by: str | None = None,
        hide_posts_in_books: str | None = None,
        date_start: str | None = None,
        date_end: str | None = None,  # in progress
        duration: str | None = None,
        retries: int = 2,
        proxy: str | None = None,
        ssl: bool = True,
    ) -> SearchData | None:
        if not headers:
            headers = self._headers

        ttags = []
        self._add_param(ttags, 'threshold', threshold)
        self._add_param(ttags, 'file_type', file_type)
        self._add_param(ttags, 'fav', fav_by)
        self._add_param(ttags, 'voted', voted_by)
        self._add_param(ttags, 'user', posted_by)
        self._add_param(ttags, 'order', order)
        self._add_param(ttags, 'rating', rating)
        if tags:
            ttags.extend(tags)

        tg = "+".join(ttags) if ttags else ""

        params = {
            'default_threshold': threshold,
            'limit': 40,
            'page': page,
            'tags': tg
        }
        if hide_posts_in_books is not None:
            params['hide_posts_in_books'] = hide_posts_in_books
        if nextH:
            params['next'] = nextH

        params = {k: v for k, v in params.items() if v is not None}

        query = urlencode(params, safe=':+')
        url = f'{self.V2API_POSTS_URL}/keyset?{query}'

        data = await self.helper.getJson(url, headers, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)
        if data is None:
            return

        return SearchData.model_validate(data)

    async def destroyCollection(self, id: str, headers: dict | None = None, timeout: ClientTimeout | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> suc | None:
        url = f'{self.API_COLLECTIONS_URL}/{id}/destroy'

        if not headers:
            headers = self._headers

        r = await self.helper.getJson(url, headers, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl, method='DELETE')

        if not r:
            return None

        return suc.model_validate(r)

    async def addItemToCollection(self, colID: str, data: collectionAddItem, headers: dict | None = None, timeout: ClientTimeout | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> collectionRemAddResponse | None:
        url = f'{self.V2API_COLLECTIONS_URL}/{colID}/items'

        if not headers:
            headers = self._headers

        r = await self.helper.getJson(url, headers, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl, method='PUT', json=data.model_dump())

        if not r:
            return None

        return collectionRemAddResponse.model_validate(r)

class Miscs:
    def calcSoftcap(self, rep: int):
        tbl=[
            (500, 500, 0),
            (50, 1000, 1),
            (100, 1500, 2),
            (100, 2100, 5),
            (100, 2400, 10),
            (100, 3800, 1),
            (200, 4000, 1),
            (1000, 7000, 1)
            ]
        total = 0
        repf = 0
        perc = 100
        for repc, rept, per in tbl:
            while total < rept and rep > 0:
                perc -= per
                take = min(repc, rep)
                total += take
                rep -= take
                repf += take * (perc / 100)
        if rep > 0:
            repf += rep * 0.01
        return repf

if __name__ == '__main__':
    async def main():
        ''' EXAMPLE FOR BEGINNING!!! '''
        async with Sankaku() as sankaku:
            token = await sankaku.getRefreshToken('login/mail', 'password')
            if token is None:
                return
            token = await sankaku.exchangeToken(token)
            if token is None:
                return

            headers = sankaku.headers(token)

            # YOUR CODE

    asyncio.run(main())


'''
10-11 - 20000

'''
