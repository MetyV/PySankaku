#!/usr/bin/env python3
import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
from aiohttp import ClientResponse, ClientSession, ClientTimeout, FormData

from helpermdl.har import (
    Endpoint,
    HarToEndpoints,
    Params,
    RequestData,
    RequestEntry,
    ResponseData,
)

'''
ClientTimeout(X(Y))
  X              Y
total          = 1 # aka global request timer
connect        = 1 # wait X seconds for connect
sock_read      = 1 # wait X seconds between chunks
sock_connect   = 1 # like total
'''

import logging

import puremagic
from yarl import URL

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

    def _stack(
        self,
        method: str,
        url: str,
        headers: dict | None = None,
        json: dict | None = None,
        data=None,
    ):

        logger.info("─ REQUEST ─")
        logger.info(f"│ Method: {method}")
        logger.info(f"│ URL: {url}")
        if headers:
            hdrs = headers.copy()
            logger.info(f"│ Headers: {hdrs}")
        if json:
            logger.info(f"│ JSON: {json}")

        if data:
            logger.info(f"│ Data: {data}")

        logger.info("───────────────────────────────────────")

    async def request(self,
                      url: str,
                      headers: dict,
                      method: str = 'GET',
                      json: dict | None = None,
                      data: aiohttp.FormData | None = None,
                      timeout: ClientTimeout | None = None,
                      retries: int = 1,
                      proxy = None,
                      ssl: bool = True) -> tuple[ClientResponse | None, int | None]:
        headers = headers.copy()
        json = json.copy() if json else None

        if self.stack:
            self._stack(method, url, headers, json, data)

        st = None
        def printErr(text):
            logger.error(f'{text}: {st}')
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
                    case 404: return printErr('No page')
                    case (301, 302, 303, 307, 308):
                        logger.info(f'Redirect: {st}')
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
                    case 504:
                        if i < retries:
                            await asyncio.sleep(2)
                            continue
                        else:
                            return printErr("Timeout")
                return (r, st)
            except Exception as e:
                if i < retries:
                    logger.warning(f'Request error: attempt {i+1}/{retries} - {e}')
                    await asyncio.sleep(5)
                else:
                    logger.error(f'Request failed after {retries} attempts: {e}')
                    return (None, None)

        return (None, None)

    async def getJson(
        self,
        url: str,
        headers: dict,
        method: str = "GET",
        json: dict | None = None,
        data: FormData | None = None,
        timeout: ClientTimeout | None = None,
        retries: int = 1,
        proxy=None,
        ssl: bool = True,
    ) -> dict | None:
        def printErr():
            logger.error('Json data fetch failed')

        resp, _ = await self.request(url, headers, method, json, data, timeout, retries, proxy, ssl)

        if resp is None:
            return printErr()

        js = await resp.json()

        if js:
            logger.info('Json data fetched')
            return js

        return printErr()

    def get_mime(self, file: Path | str) -> str:
        try:
            return puremagic.from_file(file, mime=True)
        except puremagic.PureError:
            return "application/octet-stream"

    def guess_type(self, value):
        if value is None:
            return "Any"
        if type(value) is str:
            return "bool" if value.lower() in ("true", "false") else "str"
        return type(value).__name__

    def jsonToPydantic(
        self, name: str, js, path: Path | None = None, allOptional: bool = False
    ):
        path = path or Path(__file__).parent
        name = name if name.endswith('.py') else f'{name}.py'
        file_path = path / name
        classes: dict = {}

        KW = frozenset(
            (
                "class",
                "def",
                "if",
                "else",
                "elif",
                "for",
                "while",
                "return",
                "import",
                "from",
                "in",
                "is",
                "not",
                "and",
                "or",
                "None",
                "True",
                "False",
                "lambda",
                "with",
                "as",
                "try",
                "except",
                "finally",
                "raise",
                "yield",
                "assert",
                "del",
                "global",
                "nonlocal",
                "pass",
                "break",
                "continue",
                "async",
                "await",
            )
        )
        IDENT_RE = re.compile(r"[A-Za-z_]\w*\Z")
        NONWORD_RE = re.compile(r"\W")
        MISS = object()
        guess = self.guess_type
        cap = str.capitalize

        def gen(cn: str, d) -> str:
            if cn in classes:
                return cn
            classes[cn] = None

            if isinstance(d, list):
                merged: dict = {}
                for item in d:
                    if not isinstance(item, dict):
                        continue
                    stack = [(merged, item)]
                    while stack:
                        dst, src = stack.pop()
                        for kk, vv in src.items():
                            cur = dst.get(kk, MISS)
                            if cur is MISS:
                                dst[kk] = vv
                            elif type(cur) is dict and type(vv) is dict:
                                stack.append((cur, vv))
                            elif type(cur) is list and type(vv) is list:
                                cur.extend(vv)
                d = merged

            if not isinstance(d, dict) or not d:
                classes[cn] = [f"class {cn}(BaseModel):", "    pass"]
                return cn

            flds = []
            for k, v in d.items():
                container = False

                if isinstance(v, dict):
                    container = True
                    if v:
                        n = f"{cn}{cap(k)}"
                        gen(n, v)
                        ft = n
                    else:
                        ft = "Dict[str, Any]"

                elif isinstance(v, list):
                    container = True
                    if not v:
                        ft = "List[Any]"
                    else:
                        sample, depth = v[0], 1
                        while isinstance(sample, list) and sample:
                            sample = sample[0]
                            depth += 1

                        if isinstance(sample, dict):
                            all_dicts, pending = [], list(v)
                            while pending:
                                x = pending.pop()
                                if isinstance(x, dict):
                                    all_dicts.append(x)
                                elif isinstance(x, list):
                                    pending.extend(x)
                            n = f"{cn}{cap(k)}Item"
                            gen(n, all_dicts)
                            ft = "List[" * depth + n + "]" * depth
                        else:
                            prims, pending = set(), list(v)
                            while pending:
                                x = pending.pop()
                                if isinstance(x, list):
                                    pending.extend(x)
                                elif x is not None:
                                    prims.add(guess(x))
                            elem = prims.pop() if len(prims) == 1 else "Any"
                            ft = "List[" * depth + elem + "]" * depth

                elif v is None:
                    container, ft = True, "Any"
                else:
                    ft = guess(v)

                if IDENT_RE.match(k) and k not in KW:
                    fname, alias = k, ""
                else:
                    fname = NONWORD_RE.sub("_", k) or "_"
                    if fname[0].isdigit():
                        fname = "_" + fname
                    elif fname in KW:
                        fname = fname + "_"
                    alias = f", alias='{k}'"

                if allOptional or container:
                    flds.append(f"    {fname}: Optional[{ft}] = Field(None{alias})")
                else:
                    flds.append(f"    {fname}: {ft} = Field(...{alias})")

            classes[cn] = [f"class {cn}(BaseModel):"] + (flds or ["    pass"])
            return cn

        root = name[:-3]
        root = NONWORD_RE.sub("_", root) or "_"
        if root[0].isdigit() or root in KW:
            root = "_" + root
        gen(root, js)

        with open(file_path, "w+", encoding="utf-8") as f:
            out = [
                "# Autogenerated",
                "from pydantic import BaseModel, Field",
                "from typing import Optional, List, Dict, Any",
                "",
            ]
            for cls in classes.values():
                if cls is not None:
                    out.extend(cls)
                    out.append("")
            f.write("\n".join(out))

    def parse_har_to_endpoints(
        self,
        file: Path,
        domains: list | None = None,
        incPayload: bool = True,
        incResponse: bool = True,
    ) -> dict | None:
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

        return res.model_dump()
