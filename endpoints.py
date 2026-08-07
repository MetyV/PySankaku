BASE_URL = 'https://www.sankakucomplex.com'
BASE_API_URL = 'https://sankakuapi.com'
BASE_LOGIN_URL = 'https://login.sankakucomplex.com'

LOGIN_REFRESH_TOKEN = f'{BASE_LOGIN_URL}/auth/token'
TOKEN_EXCHANGE = f'{BASE_API_URL}/sso/token-exchange'
USERS_API_URL = f'{BASE_LOGIN_URL}/users'
API_REQUEST_RESEND_VERIFICATION = f'{BASE_API_URL}/auth/request-validation'

API_BOOKS_URL = f'{BASE_API_URL}/pools'
API_POSTS_URL = f'{BASE_API_URL}/posts'