import asyncio
import json
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import urlparse

import aiohttp

from models.bookdata import BookData
from models.postdata import PostData
from models.accountedit import AccountData
from models.avatar import AvatarModel
from helper import Helper as hlp
from helper import logger as logging
from endpoints import *

class Sankaku:
    '''
    Maybe rabotaet with idol. I'll check it potom.
    '''
    def __init__(self):
        self._headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0'}
        self.helper = hlp()

    async def __aenter__(self):
        await self.helper._session_init()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.helper._session_close()

    async def getRefreshToken(self, login: str, password: str, timeout: int = 10, headers: dict | None = None) -> Optional[str]:
        def err():
            logging.error('Refresh token retrieval failed')
            return

        logging.info('Retrieving refresh token...')

        if headers is None:
            headers = self._headers

        data = await self.helper.getJson(LOGIN_REFRESH_TOKEN, headers, 'POST', {
                "login":login,
                "password":password,
                "mfaParams":{"login":login}
                }, timeout=timeout)
        
        if data is None:
            return err()

        token = data.get('access_token')

        if not token:
            return err()

        logging.info('Refresh token retrieved successfully')
        return token

    async def exchangeToken(self, refToken: str, timeout: int = 10, headers: dict | None = None) -> Optional[str]:
        def err():
            logging.error('Token retrieval failed')
            return

        logging.info('Retrieving token...')

        if headers is None:
            headers = self._headers

        data = await self.helper.getJson(TOKEN_EXCHANGE, headers, 'POST', {
            "access_token":refToken,
            "client_id":"sankaku-web-app",
            "url":BASE_URL
            }, timeout=timeout)
        
        if data is None:
            return err()

        token = data.get('access_token')

        if not token:
            return err()

        logging.info('Token retrieved successfully')
        return token

    def headers(self, token: str) -> dict:
        '''
        ya leniviy, tak chto on self doing this auth shit
        '''
        headers = self._headers.copy()
        headers['Authorization'] = f'Bearer {token}'
        return headers

    def getPostID(self, url: str) -> str:
        parsed = urlparse(url).path
        post_id = parsed.split('/')[-1]
        return post_id

    QualityType = Literal[0, 1, 2, 3]
    async def getPostFu(self, id, timeout: int = 10, headers: dict | None = None, quality: QualityType = 0) -> Optional[dict]:
        '''
        quality: 0 - best possible, 1 - sample, 2 - fallback, 3 - file_url
        '''
        def err():
            logging.error(f'Failed to retrieve post {id} file URL with {quality} quality.')
            return
        
        if headers is None:
            headers = self._headers

        url = f'{API_POSTS_URL}/{id}/fu'
        data = await self.helper.getJson(url, headers, timeout=timeout)
        if data is None:
            return err()
        fdata = data.get('data')
        if not fdata:
            return err()

        furl = None
        match quality:
            case 0:
                furl = fdata.get('file_url') or fdata.get('fallback_url') or fdata.get('sample_url')
            case 1:
                furl = fdata.get('sample_url')
            case 2:
                furl = fdata.get('fallback_url')
            case 3:
                furl = fdata.get('file_url')
        if not furl:
            return err()
        return furl

    async def getBookData(self, id, timeout: int = 10, headers: dict | None = None) -> Optional[BookData]:
        def err():
            logging.error(f'Failed to retrieve book {id} data.')
            return
        
        if headers is None:
            headers = self._headers

        url = f'{API_BOOKS_URL}/{id}'
        data = await self.helper.getJson(url, headers, timeout=timeout)
        if data is None:
            return err()
        return BookData.model_validate(data)

    async def getPostData(self, id, timeout: int = 30, headers: dict | None = None) -> Optional[PostData]:
        def err():
            logging.error(f'Failed to retrieve post {id} data.')
            return
        
        if headers is None:
            headers = self._headers

        url = f'{BASE_API_URL}/v2/posts?&page=1&limit=1&default_threshold=0&tags=id_range:{id}'
        data = await self.helper.getJson(url, headers, timeout=timeout)
        if data is None:
            return err()
        pd = data[0]
        if not pd:
            return err()
        return PostData.model_validate(pd)

    VoteScore = Literal[0, 1, 2, 3, 4, 5]
    async def votePost(self, id, vote: VoteScore = 5, timeout: int = 10, headers: dict | None = None) -> Optional[dict]:
        '''
        0 - remove vote, 1-5 - vote score
        '''
        def err():
            logging.error(f'Failed to vote: {id}.')
            return
        
        if headers is None:
            headers = self._headers

        method = 'PUT' if vote > 0 else 'DELETE'

        url = f'{API_POSTS_URL}/{id}/vote'
        data = await self.helper.getJson(url, headers, method, {'score': vote}, timeout=timeout)
        if data is None:
            return err()
        return data

    async def regAccount(self, login: str, password: str, mail: str, timeout: int = 10, headers: dict | None = None) -> Optional[dict]:
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

        data = await self.helper.getJson(REGISTER_API_URL, headers, 'POST', json, timeout=timeout)
        if data is None:
            logging.error('Registration failed')
            return
        logging.info('Registration successful')
        return data

    async def resendVerif(self, headers: dict, timeout: int = 10) -> Optional[dict]:
        data = await self.helper.getJson(API_REQUEST_RESEND_VERIFICATION, headers, 'POST', timeout=timeout)
        if data is None:
            logging.error('Failed to resend verification code')
            return
        logging.info('Verification code resent successfully')
        return data

    async def getAccountInfo(self, headers: dict, id: str = 'me', timeout: int = 10) -> Optional[AccountData]:
        data = await self.helper.getJson(f'{USERS_API_URL}/{id}', headers, timeout=timeout)
        if data is None:
            logging.error('Failed to get account info')
            return None
        user = data.get('user')
        if not user or not isinstance(user, dict):
            logging.error('Invalid user data in response')
            return None
        logging.info('Account info retrieved successfully')
        return AccountData.model_validate(user)

    async def setAccountInfo(self, headers: dict, id: str, update_data: AccountData, timeout: int = 10) -> Optional[dict]:
        '''
        Returns data like getAccountInfo
        here dohuya vozmojnogo but i'm too lazy to find it
        '''
        payload = {"user": update_data.model_dump(exclude_none=True)}
        data = await self.helper.getJson(
            f'{USERS_API_URL}/{id}',
            headers,
            'PUT',
            payload,
            timeout=timeout
        )

        if data is None:
            logging.error('Failed to update account info')
            return

        user = data.get('user')
        if not user:
            logging.error('No user data in response after update')
            return

        logging.info('Account info updated successfully')
        return user

    async def favor(self, headers: dict, id: str, book: bool, fav: bool = True, timeout: int = 10) -> Optional[dict]:
        url = f'{API_BOOKS_URL if book else API_POSTS_URL}/{id}/favorite'

        data = await self.helper.getJson(url, headers, 'POST' if fav else 'DELETE')

        if data is None:
            logging.error(f'Failed to fav {id}')
            return
        logging.info(f'Favorited {id}')
        return data

    async def _ebaniyFile(self, File: Path | str, headers: dict, timeout: int = 60, post: bool = False, cdata: dict | None = None) -> Optional[dict]:
        File = self.helper.resolve_path(File)
        if not File.exists():
            logging.error(f'File {File} does not exist')
            return
        
        mime = self.helper.get_mime(File)
        mimet = mime.split('/')
        configs = {
            'image': {
                'url': f'{API_POSTS_URL}/tagging_image',
                'field': 'art[image_input]'
            },
            'video': {
                'url': f'{API_POSTS_URL}/tagging_video',
                'field': 'art[video_input]'
            }
        }
        if mimet[0] not in configs:
            logging.error(f'Unsupported file type: {mime}')
            return
        
        config = configs['video'] if mimet[1] == 'gif' else configs[mimet[0]]
        url = API_POSTS_URL if post else config['url']
        fieldName = 'post[file]' if post else config['field']
        
        data = aiohttp.FormData()
        with open(File, 'rb') as f:
            data.add_field(fieldName, f.read(), filename=File.name, content_type=mime)

        if cdata:
            for key, value in cdata.items():
                if value is None or value == '':
                    continue
                if isinstance(value, list):
                    value = str(value)
                data.add_field(key, str(value))

        resp = await self.helper.getJson(url, headers, 'POST', data=data, timeout=timeout)
        return resp
        
    async def tagMedia(self, File: Path | str, headers: dict, timeout: int = 60) -> Optional[list[dict]]:
        resp = await self._ebaniyFile(File, headers=headers, timeout=timeout)
        if resp is None:
            logging.error(f'Failed to tag')
            return
        tags = resp.get('tags')
        if not tags:
            logging.error(f'Failed to extract tags')
            return

        return tags

    async def postMedia(self, File: Path | str, tags: list, headers: dict, parentID: str = '', rating: str = 'e', timeout: int = 60) -> Optional[dict]:
        tagss = json.dumps([{"name": tag} for tag in tags])
        data = {
            "post[parent_id]": parentID,
            "post[rating]": rating, # Chtob ne banili. mojno i 's'
            "post[tags]": tagss,
            "post[upload_url]": "",
            "post[pool_id]": "",
            "post[reupload_post_id]": ""
        }

        resp = await self._ebaniyFile(File, headers, timeout=timeout, post=True, cdata=data)

        if resp is None:
            logging.error(f'Failed to post')
            return
        return resp

    async def changeAvatar(self, 
                           userID: str | int, 
                           postID: str, 
                           token: str, 
                           left: float = 0, 
                           right: float = 0, 
                           top: float = 0, 
                           bottom: float = 0, 
                           timeout: int = 10) -> Optional[dict]:
        url = f'{USERS_API_URL}/{userID}/avatar'
        
        headers = self.headers(token)
        json = AvatarModel(post_id=postID, left=left, right=right, top=top, bottom=bottom)

        return await self.helper.getJson(url, headers, 'PUT', json.model_dump(), timeout=timeout)

    async def getCollectionData(self, id, timeout: int = 30, headers: dict | None = None) -> Optional[dict]:
        url = f'{API_COLLECTIONS_URL}/{id}'

        if headers is None:
            headers = self._headers

        res = await self.helper.getJson(url, headers, timeout=timeout)

        if res is None:
            logging.error(f'Failed to retrieve collection {id} data.')
            return

        return res

    # post search

if __name__ == '__main__':
    async def main():
        ''' EXAMPLE FOR BEGINNING!!! '''
        sankaku = Sankaku()
        token = await sankaku.getRefreshToken('login/mail', 'password')
        if not isinstance(token, str):
            return
        token = await sankaku.exchangeToken(token)
        if not isinstance(token, str):
            return

        headers = sankaku.headers(token)

        # YOUR CODE

        await sankaku.helper._session_close() # IMPORTANT!!! nu... ne sovsem

    asyncio.run(main())