import json
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
import aiohttp
from aiohttp import ClientTimeout, ClientResponse, ClientSession, FormData
from helpermdl.har import Endpoint, HarToEndpoints, Params, RequestData, ResponseData, RequestEntry
'''
ClientTimeout(X(Y))
  X              Y
total          = 1 # aka global request timer
connect        = 1 # wait X seconds for connect
sock_read      = 1 # wait X seconds between chunks
sock_connect   = 1 # like total
'''

import puremagic
from yarl import URL

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(filename)s:%(funcName)s:%(lineno)d | %(message)s',
    datefmt='%H:%M:%S'
)
_logger = logging.getLogger(__name__)
logger = _logger

class Helper:
    session: ClientSession | None
    def __init__(self, stack: bool = False):
        self.session = None
        self.stack = stack

    async def __aenter__(self):
        await self._session_init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._session_close()

    async def _session_close(self):
        if self.session:
            await self.session.close()
        
    async def _session_init(self):
        if self.session:
            await self._session_close()
        self.session = ClientSession()

    def resolve_path(self, path: Path | str) -> Path:
        return Path(path).resolve()
    
    def get_filename_from_url(self, url: str, extension: bool = False) -> str:
        parsed = urlparse(url)
        if extension:
            return parsed.path
        return Path(parsed.path).stem

    def _stack(self, 
                method: str, 
                url: str, 
                headers: dict = {}, 
                json: dict | None = None, 
                data = None):
        
        logging.info("─ REQUEST ─")
        logging.info(f"│ Method: {method}")
        logging.info(f"│ URL: {url}")
        if headers:
            hdrs = headers.copy()
            logging.info(f"│ Headers: {hdrs}")
        if json:
            logging.info(f"│ JSON: {json}")
        
        if data:
            logging.info(f"│ Data: {data}")
        
        logging.info("───────────────────────────────────────")
    
    async def request(self, 
                      url: str, 
                      headers: dict, 
                      method: str = 'GET', 
                      json: dict | None = None, 
                      data: aiohttp.FormData | None = None, 
                      timeout: ClientTimeout | None = None,
                      retries: int = 1, 
                      proxy = None,
                      ssl: bool = True) -> tuple[Optional[ClientResponse], Optional[int]]:
        headers = headers.copy()
        json = json.copy() if json else None

        if self.stack:
            self._stack(method, url, headers, json, data)

        st = None
        def printErr(text):
            logging.error(f'{text}: {st}')
            return (None, None)
        
        if self.session is None:
            await self._session_init()

        assert self.session is not None

        for i in range(1, retries+1):
            try:
                r = await self.session.request(method, url, headers=headers, json=json, data=data, timeout=timeout, allow_redirects=True, proxy=proxy, ssl=ssl)
                st = r.status
                newUrl = r.url
                match st:
                    case 404: return printErr(f'No page')
                    case (301, 302, 303, 307, 308):
                        logging.info(f'Redirect: {st}')
                        if not isinstance(newUrl, URL): # ne rabotaet navernoe, no vsegda dolzhno byt URL
                            return printErr('No redirect url extracted')
                        return await self.request(newUrl, headers, method, json, data, timeout, retries, proxy)
                    case 400:return printErr('Bad request(invalid request)')
                    case 401:return printErr('Unauthorized(token?)')
                    case 403:return printErr('Forbidden(token?)')
                    case 405:return printErr(f'Wrong method({method})')
                    case 409:return printErr('Conflict')
                    case 410:return printErr('RIP resource')
                    case 415:return printErr('Wrong data type')
                    case 422:return printErr('Unprocessable')
                    case 429:return printErr('Riched RP(D/M)')
                    case 500:return printErr('Internal error') # if you see it more than 5 times, it'll be: real error, shitty code/args or near site reboot
                    case 502:return printErr('Bad gateway')
                    case 503:return printErr('Service unavailable')
                    case 504:return printErr('Timeout')
                return (r, st)
            except Exception as e:
                if i < retries:
                    logging.warning(f'Request error: attempt {i+1}/{retries} - {e}')
                else:
                    logging.error(f'Request failed after {retries} attempts: {e}')
                    return (None, None)
        return (None, None)
                
    async def getJson(self, 
                      url: str, 
                      headers: dict, 
                      method: str = 'GET', 
                      json: dict = {}, 
                      data: FormData | None = None, 
                      timeout: ClientTimeout | None = None, 
                      retries: int = 1, proxy = None,
                      ssl: bool = True) -> Optional[dict]:
        def printErr():
            logging.error('Json data fetch failed')
            return None
        
        resp, _ = await self.request(url, headers, method, json, data, timeout, retries, proxy, ssl)

        if resp is None:
            return printErr()
        
        js = await resp.json()
        
        if js:
            logging.info('Json data fetched')
            return js
        
        return printErr()
    
    def get_mime(self, file: Path | str) -> str:
        try:
            return puremagic.from_file(file, mime=True)
        except puremagic.PureError:
            return "application/octet-stream"

    def guess_type(self, value: str):
        if value is None:
            return 'str'
        if isinstance(value, dict):
            return 'dict'
        
        if isinstance(value, list):
            return 'list'
        
        if isinstance(value, bool):
            return 'bool'
        
        if isinstance(value, int):
            return 'int'
        
        if isinstance(value, float):
            return 'float'
        if value.lower() in ('none', 'null', ''):
            return 'str'
        if value.lower() in ('true', 'false'):
            return 'bool'
        try:
            int(value)
            return 'int'
        except ValueError:
            pass
        try:
            float(value)
            return 'float'
        except ValueError:
            pass
        return 'str'

    def jsonToPydantic(self, name: str, js: dict, path: Path | None = None, allOptional: bool = False):
        # here's some AI work
        path = path or Path(__file__).parent
        name = name if name.endswith('.py') else f'{name}.py'
        file_path = path / name
        classes = {}
        
        def t(v):
            if v is None: return 'Any'
            if isinstance(v, bool): return 'bool'
            if isinstance(v, int): return 'int'
            if isinstance(v, float): return 'float'
            return 'str'
        
        def gen(cn, d):
            if cn in classes: return cn
            flds = []
            for k, v in d.items():
                if isinstance(v, dict) and v:
                    n = f'{cn}{k.capitalize()}'; gen(n, v); fld = f'{k}: {n}'
                elif isinstance(v, list) and v and isinstance(v[0], dict):
                    n = f'{cn}{k.capitalize()}Item'; gen(n, v[0]); fld = f'{k}: List[{n}]'
                elif isinstance(v, list):
                    fld = f'{k}: {"Optional[" if allOptional else ""}List[{t(v[0]) if v else "Any"}]{"]" if allOptional else ""}'
                else:
                    fld = f'{k}: {"Optional[" if allOptional else ""}{t(v)}{"]" if allOptional else ""}'
                flds.append(f'    {fld} = Field(None)' if allOptional or isinstance(v, (dict,list)) else f'    {fld} = Field(...)')
            classes[cn] = [f'class {cn}(BaseModel):'] + flds
            return cn
        
        root = name.replace('.py', '')
        gen(root, js)
        
        with open(file_path, 'w+', encoding='utf-8') as f:
            lines = ['# Autogenerated', 'from pydantic import BaseModel, Field', 'from typing import Optional, List, Any', '']
            for cn, cls in classes.items():
                lines.extend(cls)
                if cn != root: lines.append('')
            f.write('\n'.join(lines))

    def parse_har_to_endpoints(self, file: Path, domains: list = [], incPayload: bool = True, incResponse: bool = True) -> Optional[str]:
        '''
        domains may contain full url or endpoint(/post) or domain
        '''
        file = self.resolve_path(file)

        if not file.exists():
            return
        
        with open(file, 'r') as f:
            har = json.load(f)

        res = HarToEndpoints(url={})
        c = 0

        for entry in har['log']['entries']:
            req = entry['request']
            furl = req['url']
            method = req['method']

            if domains and not any(domain in furl for domain in domains):
                continue

            parsed = urlparse(furl)
            baseURL = f'{parsed.scheme}://{parsed.netloc}'
            path = parsed.path
            query = f'?{parsed.query}' if parsed.query else ''

            if baseURL not in res.url:
                res.url[baseURL] = {}
            if path not in res.url[baseURL]:
                res.url[baseURL][path] = {}
            if query not in res.url[baseURL][path]:
                res.url[baseURL][path][query] = Endpoint()

            reqHeaders = {}
            for header in req.get('headers', []):
                reqHeaders[header.get('name', '')] = header.get('value', '')

            reqBody = None
            postData = req.get('postData')
            if incPayload and postData:
                if 'text' in postData:
                    try:
                        reqBody = json.loads(postData['text'])
                    except:
                        reqBody = postData['text']
                elif 'params' in postData:
                    reqBody = postData['params']

            resp = entry.get('response', {})
            respStatus = resp.get('status', 0)
            
            respBody = None
            if incResponse:
                content = resp.get('content', {})
                text = content.get('text', '')
                if text:
                    try:
                        respBody = json.loads(text)
                    except:
                        if len(text) > 10000:
                            text = text[:10000] + '... [TRUNCATED]'
                        respBody = text

            respHeaders = {}
            for header in resp.get('headers', []):
                respHeaders[header.get('name', '')] = header.get('value', '')

            c += 1

            # Добавляем запрос с ID
            if method not in res.url[baseURL][path][query].params:
                res.url[baseURL][path][query].params[method] = Params(
                    method=method,
                    requests_count=0,
                    requests={}
                )

            method_data = res.url[baseURL][path][query].params[method]
            method_data.requests_count += 1
            method_data.requests[f'{c}'] = RequestEntry(
                id=f'{c}',
                method=method,
                request=RequestData(
                    headers=reqHeaders if reqHeaders else None,
                    body=reqBody,
                    timestamp=entry.get('startedDateTime')
                ),
                response=ResponseData(
                    status=respStatus,
                    body=respBody,
                    headers=respHeaders if respHeaders else None,
                    timestamp=entry.get('startedDateTime')
                )
            )

        return res.model_dump_json()