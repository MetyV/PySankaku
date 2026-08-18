BASE_URL = 'https://www.sankakucomplex.com'
BASE_API_URL = 'https://sankakuapi.com'
BASE_LOGIN_URL = 'https://login.sankakucomplex.com'

LOGIN_REFRESH_TOKEN = f'{BASE_LOGIN_URL}/auth/token'
TOKEN_EXCHANGE = f'{BASE_API_URL}/sso/token-exchange'
REGISTER_API_URL = f'{BASE_LOGIN_URL}/users'
USERS_API_URL = f'{BASE_API_URL}/users'
API_REQUEST_RESEND_VERIFICATION = f'{BASE_API_URL}/auth/request-validation'

API_BOOKS_URL = f'{BASE_API_URL}/pools'

API_POSTS_URL = f'{BASE_API_URL}/posts'
V2API_POSTS_URL = f'{BASE_API_URL}/v2/posts'

API_COLLECTIONS_URL = f'{BASE_API_URL}/collections'

""" IDOL """
BASE_IDOL_URL = 'https://www.idolcomplex.com'

'''
register
await fetch("https://login.idol.sankakucomplex.com/users", {
    "credentials": "omit",
    "headers": {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:153.0) Gecko/20100101 Firefox/153.0",
    },
    "body": "{\"user\":{\"name\":\"123123\",\"email\":\"123123\",\"password\":\"123123\",\"password_confirmation\":\"123123\"}}",
    "method": "POST",
});


check refresh token
await fetch("https://i.sankakuapi.com/users/check-refresh-token", {
    "credentials": "include",
    "headers": {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:153.0) Gecko/20100101 Firefox/153.0",
        "Accept": "application/vnd.sankaku.api+json;v=2",
        "Accept-Language": "ru-RU,ru,en-US,en",
        "Content-Type": "application/json",
        "Client-Type": "non-premium",
        "Platform": "web-app",
        "Api-Version": "2",
        "Obfuscate-Type": "tag,wiki,comment",
        "Enable-New-Tag-Type": "true",
        "Expiration-Policy": "reduced",
        "Authorization": "Bearer QQ"
    },
    "referrer": "https://www.idolcomplex.com/",
    "body": "{\"token\":\"123123\"}",
    "method": "POST",
});

token exchange
await fetch("https://i.sankakuapi.com/sso/token-exchange", {
    "credentials": "omit",
    "headers": {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:153.0) Gecko/20100101 Firefox/153.0",
        "Accept": "application/vnd.sankaku.api+json;v=2",
        "Accept-Language": "ru-RU,ru,en-US,en",
        "Content-Type": "application/json",
        "Client-Type": "non-premium",
        "Platform": "web-app",
        "Api-Version": "2",
        "Obfuscate-Type": "tag,wiki,comment",
        "Enable-New-Tag-Type": "true",
        "Expiration-Policy": "reduced",
    },
    "referrer": "https://www.idolcomplex.com/",
    "body": "{\"access_token\":\"{{{!!!NOT BEARER!!!}}}\",\"client_id\":\"idol-web-app\",\"url\":\"https://www.idolcomplex.com\"}",
    "method": "POST",
});


login
await fetch("https://login.idol.sankakucomplex.com/auth/token", {
    "credentials": "omit",
    "headers": {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:153.0) Gecko/20100101 Firefox/153.0",
    },
    "referrer": "https://www.idolcomplex.com/",
    "body": "{\"login\":\"123\",\"password\":\"123\",\"mfaParams\":{\"login\":\"123\"}}",
    "method": "POST",
});

resend verif
await fetch("https://i.sankakuapi.com/auth/request-validation", {
    "credentials": "include",
    "headers": {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:153.0) Gecko/20100101 Firefox/153.0",
        "Accept": "application/vnd.sankaku.api+json;v=2",
        "Api-Version": "2",
        "Obfuscate-Type": "tag,wiki,comment",
        "Enable-New-Tag-Type": "true",
        "Expiration-Policy": "reduced",
        "Authorization": "Bearer ",
    },
    "referrer": "https://www.idolcomplex.com/",
    "body": "{\"email\":\"123\",\"entry_query\":{\"response_type\":\"code\",\"scope\":\"openid\",\"client_id\":\"idol-web-app\",\"redirect_uri\":\"https://www.idolcomplex.com/sso/callback\",\"return_uri\":\"https://www.idolcomplex.com/\",\"lang\":\"en\"}}",
    "method": "POST",
    "mode": "cors"
});

verif
await fetch("https://www.idolcomplex.com/email-verification?code={{{!!!NOT BEARER!!!}}}", {
    "credentials": "include",
    "headers": {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:153.0) Gecko/20100101 Firefox/153.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Sec-GPC": "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1"
    },
    "method": "GET",
});


I THINK... IT'S THE SAME
'''