class Endpoints:
    def __init__(self, idol: bool = False):
        self.BASE_URL = 'https://www.idolcomplex.com' if idol else 'https://www.sankakucomplex.com'
        self.BASE_API_URL = 'https://i.sankakuapi.com' if idol else 'https://sankakuapi.com'
        self.BASE_LOGIN_URL = 'https://login.idol.sankakucomplex.com' if idol else 'https://login.sankakucomplex.com'
        self.CLIENT_ID = 'idol-web-app' if idol else 'sankaku-web-app'

        self.LOGIN_REFRESH_TOKEN = f'{self.BASE_LOGIN_URL}/auth/token'
        self.TOKEN_EXCHANGE = f'{self.BASE_API_URL}/sso/token-exchange'
        self.REGISTER_API_URL = f'{self.BASE_LOGIN_URL}/users'
        self.USERS_API_URL = f'{self.BASE_API_URL}/users'
        self.API_REQUEST_RESEND_VERIFICATION = f'{self.BASE_API_URL}/auth/request-validation'

        self.API_BOOKS_URL = f'{self.BASE_API_URL}/pools'

        self.API_POSTS_URL = f'{self.BASE_API_URL}/posts'
        self.V2API_POSTS_URL = f'{self.BASE_API_URL}/v2/posts'

        self.API_COLLECTIONS_URL = f'{self.BASE_API_URL}/collections'

'''

'''