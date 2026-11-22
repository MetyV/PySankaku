#!/usr/bin/env python3
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlencode, urlparse

import aiofiles
import aiohttp
from aiohttp import ClientTimeout
from fake_useragent import UserAgent

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

ua = UserAgent()


class Sankaku(Endpoints):
    '''
    Maybe rabotaet with idol. I'll check it potom.

    Everything goes through `_req` (REST) or `graphql` (GraphQL) now, so the
    auth/header/retry dance lives in one place instead of twenty.
    '''

    def __init__(
        self,
        idol: bool = False,
        stack: bool = False,
        default_user_agent: str | None = None,
    ):
        super().__init__(idol)
        self._headers = {"User-Agent": default_user_agent or ua.random}
        self.helper = hlp(stack)

    async def __aenter__(self):
        await self.helper._session_init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.helper._session_close()

    # ══════════════════════════════════════════════════════════════════════
    #  plumbing
    # ══════════════════════════════════════════════════════════════════════

    def headers(self, headers: dict | None = None, token: str | None = None, api: bool = False) -> dict:
        '''
        ya leniviy, tak chto on self doing this auth shit

        api=True adds the headers the web-app sends to the v2 API
        (Accept: application/vnd.sankaku.api+json;v=2 and friends).
        Without them half of the endpoints answer 406.
        '''
        headers = headers.copy() if headers else self._headers.copy()
        if api:
            for k, v in self.API_HEADERS.items():
                headers.setdefault(k, v)
            headers.setdefault('Origin', self.BASE_URL)
            headers.setdefault('Referer', f'{self.BASE_URL}/')
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _q(self, **kw) -> str:
        '''
        Drops the None's and builds a query string.
        ':' and '+' stay raw, because tags are written like `id_range:1..2`
        and joined with '+'.
        '''
        return urlencode({k: v for k, v in kw.items() if v is not None}, safe=':+')

    async def _req(
        self,
        url: str,
        method: str = 'GET',
        headers: dict | None = None,
        token: str | None = None,
        params: dict | None = None,
        json: dict | None = None,
        data: aiohttp.FormData | None = None,
        timeout: ClientTimeout | None = None,
        retries: int = 2,
        proxy: str | None = None,
        ssl: bool = True,
        api: bool = True,
    ) -> Any | None:
        '''One request. One place to fix when sankaku changes its mind.'''
        if params:
            q = self._q(**params)
            if q:
                url = f'{url}?{q}'

        return await self.helper.getJson(
            url,
            self.headers(headers, token, api),
            method,
            json=json,
            data=data,
            timeout=timeout,
            retries=retries,
            proxy=proxy,
            ssl=ssl,
        )

    async def graphql(
        self,
        query: str,
        variables: dict | None = None,
        operationName: str | None = None,
        timeout: ClientTimeout | None = None,
        headers: dict | None = None,
        token: str | None = None,
        retries: int = 2,
        proxy: str | None = None,
        ssl: bool = True,
    ) -> dict | None:
        '''
        POST /graphql — the web-app does most of its reading through here
        (series, messages, wiki, ...). Returns the `data` part.
        '''
        payload: dict = {"query": query}
        if variables is not None:
            payload["variables"] = variables
        if operationName is not None:
            payload["operationName"] = operationName

        r = await self._req(
            self.GRAPHQL_URL,
            'POST',
            headers,
            token,
            json=payload,
            timeout=timeout,
            retries=retries,
            proxy=proxy,
            ssl=ssl,
        )

        if not r:
            logging.error('GraphQL request failed')
            return

        if r.get('errors'):
            logging.error(f"GraphQL errors: {r['errors']}")
            return

        return r.get('data')

    # ══════════════════════════════════════════════════════════════════════
    #  auth
    # ══════════════════════════════════════════════════════════════════════

    async def getRefreshToken(self, login: str, password: str, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> str | None:
        def err():
            logging.error('Refresh token retrieval failed')

        logging.info('Retrieving refresh token...')

        data = await self._req(self.LOGIN_REFRESH_TOKEN, 'POST', headers, json={
                "login":login,
                "password":password,
                "mfaParams":{"login":login}
                }, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl, api=False)

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

        data = await self._req(self.TOKEN_EXCHANGE, 'POST', headers, json={
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

        data = await self._req(self.REGISTER_API_URL, 'POST', headers, json=json, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl, api=False)
        if data is None:
            logging.error('Registration failed')
            return
        logging.info('Registration successful')
        return RegisterData.model_validate(data)

    async def resendVerif(self, headers: dict, timeout: ClientTimeout | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> dict | None:
        data = await self._req(self.API_REQUEST_RESEND_VERIFICATION, 'POST', headers, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)
        if data is None:
            logging.error('Failed to resend verification code')
            return
        logging.info('Verification code resent successfully')
        return data

    # ══════════════════════════════════════════════════════════════════════
    #  account
    # ══════════════════════════════════════════════════════════════════════

    async def getAccountInfo(self, headers: dict, id: str = 'me', timeout: ClientTimeout | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> AccountData | None:
        data = await self._req(self.u(self.P_USERS, id), 'GET', headers, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

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
        data = await self._req(self.u(self.P_USERS, id), 'PUT', headers, json=payload, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

        if data is None:
            logging.error('Failed to update account info')
            return

        user = data.get('user')
        if not user:
            logging.error('No user data in response after update')
            return

        logging.info('Account info updated successfully')
        return AccountData.model_validate(user)

    async def getUser(self, id: str, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> dict | None:
        '''
        Same endpoint as getAccountInfo but returns the raw dict —
        sometimes you only want a level or an avatar, not the whole model.
        '''
        return await self._req(self.u(self.P_USERS, id), 'GET', headers, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

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
        model = AvatarModel(post_id=postID, left=left, right=right, top=top, bottom=bottom)

        return await self._req(self.u(self.P_USERS, userID, 'avatar'), 'PUT', headers, json=model.model_dump(), timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

    async def getAchievements(self, user: str = 'me', kind: str = 'favorites', timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> dict | None:
        '''
        GET /user-achievements/{user}/{kind}
        kind: favorites (seen so far) — other kinds are the same shape.
        '''
        return await self._req(self.u(self.P_ACHIEVEMENTS, user, kind), 'GET', headers, params={'lang': 'en'}, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

    async def getPrivileges(self, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> dict | None:
        '''GET /privileges — the whole reputation/privilege table for the token.'''
        return await self._req(self.API_PRIVILEGES_URL, 'GET', headers, params={'lang': 'en'}, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

    async def getAgeVerificationState(self, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> dict | None:
        '''GET /age-verification/filter-state — is the account/region filtered or not.'''
        return await self._req(self.API_AGE_VERIFICATION_URL, 'GET', headers, params={'lang': 'en'}, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

    async def getUnreadMessagesCount(self, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> int | None:
        '''GraphQL { totalUnreadMessages } — cheapest possible "do I have mail".'''
        data = await self.graphql('query { totalUnreadMessages }', timeout=timeout, headers=headers, retries=retries, proxy=proxy, ssl=ssl)
        if not data:
            return
        return data.get('totalUnreadMessages')

    # ══════════════════════════════════════════════════════════════════════
    #  posts
    # ══════════════════════════════════════════════════════════════════════

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

        data = await self._req(self.u(self.P_POSTS, id, 'fu'), 'GET', headers, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)
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

    async def getPostData(self, id, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> PostData | None:
        def err():
            logging.error(f'Failed to retrieve post {id} data.')

        data = await self._req(self.V2API_POSTS_URL, 'GET', headers, params={
            'page': 1,
            'limit': 1,
            'default_threshold': 0,
            'tags': f'id_range:{id}',
        }, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)
        if data is None:
            return err()
        if not data:
            return err()
        return PostData.model_validate(data[0]) # not tested

    async def getPostTags(self, id, timeout: ClientTimeout | None = None, headers: dict | None = None, page: int = 1, limit: int = 200, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> PostTagsData | None:
        def err():
            logging.error(f'Failed to retrieve post {id} tags.')

        data = await self._req(self.u(self.P_POSTS, id, 'tags'), 'GET', headers, params={'page': page, 'limit': limit}, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)
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

        method = 'PUT' if vote > 0 else 'DELETE'

        data = await self._req(self.u(self.P_POSTS, id, 'vote'), method, headers, json={'score': vote}, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)
        if data is None:
            return err()
        return data

    async def favor(self, headers: dict, id: str, isbook: bool, fav: bool = True, timeout: ClientTimeout | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> dict | None:
        base = self.P_POOLS if isbook else self.P_POSTS

        data = await self._req(self.u(base, id, 'favorite'), 'POST' if fav else 'DELETE', headers, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

        if data is None:
            logging.error(f'Failed to fav {id}')
            return
        logging.info(f'Set favor {fav} for {id}')
        return data

    async def destroyPost(self, id: str, headers: dict | None = None, timeout: ClientTimeout | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> suc | None:
        '''DELETE /posts/{id} — only your own posts (or a moderator's).'''
        r = await self._req(self.u(self.P_POSTS, id), 'DELETE', headers, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

        if not r:
            return None

        return suc.model_validate(r)

    def _add_param(
        self,
        parts: list,
        key: str,
        value: Any,
        fmt: str = "{}:{}",
    ):
        match value:
            case datetime():
                value = value.strftime("%Y-%m-%dT%H:%M")
            case tuple():
                value = "..".join(
                    v.strftime("%Y-%m-%dT%H:%M") if isinstance(v, datetime) else str(v)
                    for v in value
                )
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
        date_start: datetime | None = None,
        date_end: datetime | None = None,
        duration: tuple[int, int] | None = None,
        retries: int = 2,
        proxy: str | None = None,
        ssl: bool = True,
    ) -> SearchData | None:
        ttags = []
        self._add_param(ttags, 'threshold', threshold)
        self._add_param(ttags, 'file_type', file_type)
        self._add_param(ttags, 'fav', fav_by)
        self._add_param(ttags, 'voted', voted_by)
        self._add_param(ttags, 'user', posted_by)
        self._add_param(ttags, 'order', order)
        self._add_param(ttags, 'rating', rating)
        self._add_param(ttags, "duration", duration)
        if tags:
            ttags.extend(tags)

        if date_start and date_end:
            self._add_param(ttags, "date", (date_start, date_end))
        elif date_start or date_end:
            self._add_param(ttags, "date", date_start or date_end)

        data = await self._req(self.u(self.P_POSTS_KEYSET), 'GET', headers, params={
            'default_threshold': threshold,
            'limit': 40,
            'page': page,
            'tags': "+".join(ttags),
            'hide_posts_in_books': hide_posts_in_books,
            'next': nextH,
        }, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)
        if data is None:
            return

        return SearchData.model_validate(data)

    async def searchPostsPage(
        self,
        timeout: ClientTimeout | None = None,
        headers: dict | None = None,
        tags: str | None = None,
        page: int = 1,
        limit: int = 20,
        threshold: int = 0,
        retries: int = 2,
        proxy: str | None = None,
        ssl: bool = True,
    ) -> list | None:
        '''
        The plain GET /v2/posts the web-app uses for the front page
        (keyset search is the other one). Returns the raw list.
        '''
        return await self._req(self.V2API_POSTS_URL, 'GET', headers, params={
            'lang': 'en',
            'page': page,
            'limit': limit,
            'default_threshold': threshold,
            'tags': tags,
        }, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

    # ══════════════════════════════════════════════════════════════════════
    #  media
    # ══════════════════════════════════════════════════════════════════════

    async def _ebaniyFile(self, File: Path | str, headers: dict, timeout: ClientTimeout | None = None, post: bool = False, cdata: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> TaggingData | fPostData | None:
        File = self.helper.resolve_path(File)
        if not File.exists():
            logging.error(f'File {File} does not exist')
            return

        mime = self.helper.get_mime(File)
        mimet = mime.split('/')
        if mimet[0] == "octet-stream":
            logging.info(f"Skipping folder")
            return
        configs = {
            'image': {
                'path': self.P_TAGGING_IMAGE,
                'field': 'art[image_input]'
            },
            'video': {
                'path': self.P_TAGGING_VIDEO,
                'field': 'art[video_input]'
            }
        }
        if mimet[0] not in configs:
            logging.error(f'Unsupported file type: {mime}')
            return

        config = configs['video'] if mimet[1] == 'gif' else configs[mimet[0]]
        url = self.API_POSTS_URL if post else self.u(config['path'])
        fieldName = 'post[file]' if post else config['field']

        async with aiofiles.open(File, "rb") as f:
            content = await f.read()

        data = aiohttp.FormData()
        data.add_field(fieldName, content, filename=File.name, content_type=mime)

        if cdata:
            for key, value in cdata.items():
                if not value:
                    continue
                data.add_field(key, str(value))

        resp = await self._req(
            url,
            'POST',
            headers,
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

        if len(tagss) < 20:
            logging.error(f"Not enough tags: got {len(tagss)} of 20\ntags={tagss}")
            return

        resp = await self._ebaniyFile(File, headers, timeout=timeout, post=True, cdata=data, retries=retries, proxy=proxy, ssl=ssl)

        if resp is None:
            logging.error('Failed to post')
            return

        return fPostData.model_validate(resp)

    # ══════════════════════════════════════════════════════════════════════
    #  pools (books) / collections
    # ══════════════════════════════════════════════════════════════════════

    async def getBookData(self, id, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> BookData | None:
        def err():
            logging.error(f'Failed to retrieve book {id} data.')

        data = await self._req(self.u(self.P_POOLS, id), 'GET', headers, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)
        if data is None:
            return err()
        return BookData.model_validate(data)

    async def getOrCreateCollection(self, data: str | CollectionCreating, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> CollectionData | None:
        typee = 'retrieve' if isinstance(data, str) else 'create'

        method = 'GET'
        js = None
        url = self.API_COLLECTIONS_URL
        if typee == 'retrieve':
            url = self.u(self.P_COLLECTIONS, data)
        else:
            js = data.model_dump() # type: ignore . typehint is shitty shit
            method = 'POST'

        res = await self._req(url, method, headers, json=js, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

        if res is None:
            logging.error(f'Failed to {typee} collection.')
            return

        dat = CollectionData.model_validate(res)

        if typee == 'create':
            logging.info(f'Created collection {dat.id}')

        return dat

    async def destroyCollection(self, id: str, headers: dict | None = None, timeout: ClientTimeout | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> suc | None:
        r = await self._req(self.u(self.P_COLLECTIONS, id, 'destroy'), 'DELETE', headers, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

        if not r:
            return None

        return suc.model_validate(r)

    async def addItemToCollection(self, colID: str, data: collectionAddItem, headers: dict | None = None, timeout: ClientTimeout | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> collectionRemAddResponse | None:
        r = await self._req(self.u(self.P_COLLECTIONS_V2, colID, 'items'), 'PUT', headers, json=data.model_dump(), timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

        if not r:
            return None

        return collectionRemAddResponse.model_validate(r)

    async def removeItemFromCollection(self, colID: str, data: collectionAddItem, headers: dict | None = None, timeout: ClientTimeout | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> collectionRemAddResponse | None:
        '''Same URL as add, same body, other verb.'''
        r = await self._req(self.u(self.P_COLLECTIONS_V2, colID, 'items'), 'DELETE', headers, json=data.model_dump(), timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

        if not r:
            return None

        return collectionRemAddResponse.model_validate(r)

    # ══════════════════════════════════════════════════════════════════════
    #  tags
    # ══════════════════════════════════════════════════════════════════════

    async def getTag(self, id: str, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> dict | None:
        return await self._req(self.u(self.P_TAGS, id), 'GET', headers, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

    async def searchTags(self, name: str = '', page: int = 1, limit: int = 20, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> dict | None:
        '''
        GET /tags?search[name_matches]=... — used by the tag autocomplete.
        ⚠ not confirmed in the HAR yet, shape follows the other v2 list calls.
        '''
        return await self._req(self.API_TAGS_URL, 'GET', headers, params={
            'lang': 'en',
            'page': page,
            'limit': limit,
            'search[name_matches]': name,
        }, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

    # ══════════════════════════════════════════════════════════════════════
    #  comments  (was "TODO" in README)
    # ══════════════════════════════════════════════════════════════════════

    async def getComments(self, postID: str, page: int = 1, limit: int = 20, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> dict | None:
        '''
        GET /comments?tags=post:{id}
        ⚠ not confirmed in the HAR yet (the tab was never opened in that capture).
        '''
        return await self._req(self.API_COMMENTS_URL, 'GET', headers, params={
            'lang': 'en',
            'page': page,
            'limit': limit,
            'tags': f'post:{postID}',
        }, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

    async def addComment(self, postID: str, body: str, anonymous: bool = False, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> dict | None:
        '''POST /comments — ⚠ not confirmed in the HAR.'''
        return await self._req(self.API_COMMENTS_URL, 'POST', headers, json={"comment": {
            "post_id": postID,
            "body": body,
            "anonymous": anonymous,
        }}, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

    async def editComment(self, id: str, body: str, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> dict | None:
        '''PUT /comments/{id} — ⚠ not confirmed in the HAR.'''
        return await self._req(self.u(self.P_COMMENTS, id), 'PUT', headers, json={"comment": {"body": body}}, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

    async def deleteComment(self, id: str, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> dict | None:
        '''DELETE /comments/{id} — ⚠ not confirmed in the HAR.'''
        return await self._req(self.u(self.P_COMMENTS, id), 'DELETE', headers, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

    # ══════════════════════════════════════════════════════════════════════
    #  companions / series / video generations  (all from the HAR)
    # ══════════════════════════════════════════════════════════════════════

    async def getCompanions(self, tags: str | None = None, page: int = 1, limit: int = 40, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> dict | None:
        '''
        GET /companions?tags=user:Mety+order:date
        tags also accepts fav:{user} / voted:{user}.
        '''
        return await self._req(self.API_COMPANIONS_URL, 'GET', headers, params={
            'lang': 'en',
            'page': page,
            'limit': limit,
            'tags': tags,
        }, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

    async def getCompanion(self, id: str, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> dict | None:
        '''GET /companions/{id} — same list shape, one item.'''
        return await self._req(self.u(self.P_COMPANIONS, id), 'GET', headers, params={'lang': 'en'}, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

    async def getVideoGenerations(self, page: int = 1, limit: int = 100, isFilterContent: bool = False, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> dict | None:
        '''GET /video-generations/history — the "my AI videos" tab.'''
        return await self._req(self.API_VIDEO_HISTORY_URL, 'GET', headers, params={
            'lang': 'en',
            'page': page,
            'limit': limit,
            'isFilterContent': str(isFilterContent).lower(),
        }, timeout=timeout, retries=retries, proxy=proxy, ssl=ssl)

    SERIES_QUERY = '''
  query Query(
    $first: Int
    $after: Cursor
    $filter: SeriesFilter
    $order: SeriesOrder
  ) {
    seriesConnection(
      first: $first
      after: $after
      filter: $filter
      order: $order
    ) {
      totalCount
      pageInfo {
        hasNextPage
        hasPreviousPage
        startCursor
        endCursor
      }
      edges {
        node {
          id
          name
          nameEn
          nameJa
          description
          isFavorite
          favCount
          voteCount
          totalScore
          isPremium
          isCompleted
          createdAt
          updatedAt
          poolCount
          activePoolCount
          readPoolPercent
          rating
          status
          score
          author {
            id
            name
            level
            avatar {
              url
            }
          }
          coverPool {
            coverPost {
              previewUrl
              sampleUrl
            }
          }
          pools {
            id
            sequence
          }
          tags {
            id
            name
            tagType
            nameEn
            nameJa
          }
        }
      }
    }
  }
'''

    async def getSeries(self, first: int = 10, after: str | None = None, filter: dict | None = None, order: dict | None = None, timeout: ClientTimeout | None = None, headers: dict | None = None, retries: int = 2, proxy: str | None = None, ssl: bool = True) -> dict | None:
        '''
        Series live only in GraphQL. Returns the `seriesConnection` node
        (totalCount + pageInfo + edges[].node).
        '''
        variables = {"first": first, "filter": filter if filter is not None else {}}
        if after:
            variables["after"] = after
        if order:
            variables["order"] = order

        data = await self.graphql(self.SERIES_QUERY, variables, 'Query', timeout=timeout, headers=headers, retries=retries, proxy=proxy, ssl=ssl)
        if not data:
            return
        return data.get('seriesConnection')


class Miscs:
    # step, to, percent consumption per step
    SOFTCAP_TABLE = [
        (500, 500, 0),
        (50, 1000, 1),
        (100, 1500, 2),
        (100, 2100, 5),
        (100, 2400, 10),
        (100, 3800, 1),
        (200, 4000, 1),
        (1000, 7000, 1),
    ]

    # reputation needed per level (was a dead local in __init__ before)
    REPUTATION_REQUIREMENTS = [
        (0, 1, 1000),
        (1, 2, 1500),
        (2, 3, 2500),
        (3, 4, 5000),
        (4, 5, 10000),
        (5, 9, 15000),
        (9, 20, 20000),
        (20, 30, 30000),
        (30, 40, 40000),
        (40, 49, 100000),
        (49, 50, 125000),  # i can't find user with 49lvl
        (50, 54, 150000),
        (54, 55, 400000),
        (55, 57, 500000),
        (57, 58, 1000000),
        (58, 59, 2000000),
        (59, 60, 3000000),
        (60, 64, 6500000),  # same as (49,50)
        (64, 66, 10000000),
    ]

    @staticmethod
    def calcSoftcap(rep: int):
        total = 0
        repf = 0
        perc = 100
        for repc, rept, per in Miscs.SOFTCAP_TABLE:
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

            headers = sankaku.headers(token=token, api=True)

            # YOUR CODE

    asyncio.run(main())
