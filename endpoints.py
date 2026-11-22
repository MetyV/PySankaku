#!/usr/bin/env python3
'''
Every URL this project talks to, in one place.

Two rules here:
1. Nothing is hardcoded twice. `u()` glues the base and the path, so a path
   lives in exactly one spot.
2. Legacy attribute names (API_POSTS_URL, USERS_API_URL, ...) are kept as
   aliases, because use.py / test_all.py / downloader.py already speak them.
'''


class Endpoints:
    # ── hosts ────────────────────────────────────────────────────────────
    SITE = 'https://www.sankakucomplex.com'
    API = 'https://sankakuapi.com'
    LOGIN = 'https://login.sankakucomplex.com'

    SITE_IDOL = 'https://www.idolcomplex.com'
    API_IDOL = 'https://i.sankakuapi.com'
    LOGIN_IDOL = 'https://login.idol.sankakucomplex.com'

    CLIENT_WEB = 'sankaku-web-app'
    CLIENT_IDOL = 'idol-web-app'

    # ── headers the web-app sends (from the HAR) ─────────────────────────
    # Anything without these gets a 400/406 from the v2 API.
    API_HEADERS = {
        'Accept': 'application/vnd.sankaku.api+json;v=2',
        'Client-Type': 'non-premium',
        'Platform': 'web-app',
        'Api-Version': '2',
        'Obfuscate-Type': 'tag,wiki,comment',
        'Enable-New-Tag-Type': 'true',
        'Expiration-Policy': 'reduced',
    }

    # ── paths (relative to API / LOGIN) ──────────────────────────────────
    P_AUTH = 'auth/token'
    P_TOKEN_EXCHANGE = 'sso/token-exchange'
    P_REGISTER = 'users'
    P_RESEND_VERIFICATION = 'auth/request-validation'
    P_GRAPHQL = 'graphql'

    P_USERS = 'users'
    P_POSTS = 'posts'
    P_POSTS_V2 = 'v2/posts'
    P_POSTS_KEYSET = 'v2/posts/keyset'
    P_TAGGING_IMAGE = 'posts/tagging_image'
    P_TAGGING_VIDEO = 'posts/tagging_video'
    P_POOLS = 'pools'
    P_COLLECTIONS = 'collections'
    P_COLLECTIONS_V2 = 'v2/collections'
    P_TAGS = 'tags'
    P_COMMENTS = 'comments'
    P_MESSAGES = 'messages'
    P_COMPANIONS = 'companions'
    P_SERIES = 'series'
    P_VIDEO_GENERATIONS = 'video-generations'
    P_VIDEO_HISTORY = 'video-generations/history'
    P_ACHIEVEMENTS = 'user-achievements'
    P_PRIVILEGES = 'privileges'
    P_AGE_VERIFICATION = 'age-verification/filter-state'

    def __init__(self, idol: bool = False):
        self.IDOL = idol
        self.BASE_URL = self.SITE = self.SITE_IDOL if idol else type(self).SITE
        self.BASE_API_URL = self.API = self.API_IDOL if idol else type(self).API
        self.BASE_LOGIN_URL = self.LOGIN = self.LOGIN_IDOL if idol else type(self).LOGIN
        self.CLIENT_ID = self.CLIENT_IDOL if idol else self.CLIENT_WEB

        # legacy aliases ─ keep, they are imported from everywhere
        self.LOGIN_REFRESH_TOKEN = self.u(self.P_AUTH, base=self.LOGIN)
        self.TOKEN_EXCHANGE = self.u(self.P_TOKEN_EXCHANGE)
        self.REGISTER_API_URL = self.u(self.P_REGISTER, base=self.LOGIN)
        self.USERS_API_URL = self.u(self.P_USERS)
        self.API_REQUEST_RESEND_VERIFICATION = self.u(self.P_RESEND_VERIFICATION)

        self.API_POSTS_URL = self.u(self.P_POSTS)
        self.V2API_POSTS_URL = self.u(self.P_POSTS_V2)
        self.API_BOOKS_URL = self.u(self.P_POOLS)
        self.API_COLLECTIONS_URL = self.u(self.P_COLLECTIONS)
        self.V2API_COLLECTIONS_URL = self.u(self.P_COLLECTIONS_V2)

        # new in AI: things the old endpoints.py didn't know about
        self.GRAPHQL_URL = self.u(self.P_GRAPHQL)
        self.API_TAGS_URL = self.u(self.P_TAGS)
        self.API_COMMENTS_URL = self.u(self.P_COMMENTS)
        self.API_MESSAGES_URL = self.u(self.P_MESSAGES)
        self.API_COMPANIONS_URL = self.u(self.P_COMPANIONS)
        self.API_SERIES_URL = self.u(self.P_SERIES)
        self.API_VIDEO_HISTORY_URL = self.u(self.P_VIDEO_HISTORY)
        self.API_ACHIEVEMENTS_URL = self.u(self.P_ACHIEVEMENTS)
        self.API_PRIVILEGES_URL = self.u(self.P_PRIVILEGES)
        self.API_AGE_VERIFICATION_URL = self.u(self.P_AGE_VERIFICATION)

    # ── the only place a URL gets built ──────────────────────────────────
    def u(self, *parts: str | int, base: str | None = None) -> str:
        '''
        u('posts', 123, 'fu')  ->  https://sankakuapi.com/posts/123/fu
        u('users')             ->  https://sankakuapi.com/users
        '''
        root = (base or getattr(self, 'API', type(self).API)).rstrip('/')
        tail = '/'.join(str(p).strip('/') for p in parts if p is not None and p != '')
        return f'{root}/{tail}' if tail else root

    url = u  # alias, because "u" is too short for somebody else's eyes
