#!/usr/bin/env python3
'''
HTTP plumbing + small utilities.

`Helper` is the only thing that touches aiohttp. Everything above it (api.py,
downloader.py) just asks for json and gets `None` when the world is on fire.

Run me directly to turn a browser HAR into a readable endpoint map:
    python helper.py "www.sankakucomplex.com_Archive.har" -o endpoints.json
'''
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
import puremagic
from aiohttp import ClientResponse, ClientSession, ClientTimeout, FormData
from yarl import URL

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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(filename)s:%(funcName)s:%(lineno)d | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# status -> (message, worth retrying?)
STATUS = {
    400: ('Bad request(invalid request)', False),
    401: ('Unauthorized(token?)', False),
    403: ('Forbidden(token?)', False),
    404: ('No page', False),
    405: ('Wrong method', False),
    406: ('Not acceptable(headers?)', False),
    409: ('Conflict', False),
    410: ('RIP resource', False),
    415: ('Wrong data type', False),
    422: ('Unprocessable', False),
    429: ('Riched RP(D/M)', True),
    500: ('Internal error', True),  # if you see it more than 5 times, it'll be: real error, shitty code/args or near site reboot
    502: ('Bad gateway', True),
    503: ('Service unavailable', True),
    504: ('Timeout', True),
}


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
            self.session = None

    async def _session_init(self):
        if self.session:
            await self._session_close()
        self.session = ClientSession()

    # ── tiny utils ───────────────────────────────────────────────────────

    def resolve_path(self, path: Path | str) -> Path:
        return Path(path).resolve()

    def get_filename_from_url(self, url: str, extension: bool = False) -> str:
        parsed = urlparse(url)
        if extension:
            return parsed.path
        return Path(parsed.path).stem

    def get_mime(self, file: Path | str) -> str:
        try:
            return puremagic.from_file(file, mime=True)
        except (puremagic.PureError, ValueError):
            return "application/octet-stream"

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
            logger.info(f"│ Headers: {headers.copy()}")
        if json:
            logger.info(f"│ JSON: {json}")
        if data:
            logger.info(f"│ Data: {data}")
        logger.info("───────────────────────────────────────")

    # ── the request itself ───────────────────────────────────────────────

    async def request(self,
                      url: str,
                      headers: dict,
                      method: str = 'GET',
                      json: dict | None = None,
                      data: aiohttp.FormData | None = None,
                      timeout: ClientTimeout | None = None,
                      retries: int = 1,
                      proxy=None,
                      ssl: bool = True) -> tuple[ClientResponse | None, int | None]:
        headers = headers.copy()
        json = json.copy() if json else None

        if self.stack:
            self._stack(method, url, headers, json, data)

        if self.session is None:
            await self._session_init()

        assert self.session is not None

        st = None

        def fail(text):
            logger.error(f'{text}: {st}')
            return (None, st)

        for i in range(1, max(1, retries) + 1):
            try:
                r = await self.session.request(
                    method, url,
                    headers=headers, json=json, data=data,
                    timeout=timeout, allow_redirects=True,
                    proxy=proxy, ssl=ssl,
                )
                st = r.status

                if st in (301, 302, 303, 307, 308):
                    logger.info(f'Redirect: {st}')
                    if not isinstance(r.url, URL):  # ne rabotaet navernoe, no vsegda dolzhno byt URL
                        return fail('No redirect url extracted')
                    r.release()
                    return await self.request(r.url, headers, method, json, data, timeout, retries, proxy, ssl)

                if st in STATUS:
                    text, retryable = STATUS[st]
                    if retryable and i < retries:
                        # be a good citizen: honour Retry-After when the site sends one
                        try:
                            wait = int(r.headers.get('Retry-After', 0))
                        except (TypeError, ValueError):
                            wait = 0
                        logger.warning(f'{text}: retry {i}/{retries} in {wait or 2}s')
                        r.release()
                        await asyncio.sleep(wait or 2)
                        continue
                    return fail(text)

                return (r, st)

            except Exception as e:
                if i < retries:
                    logger.warning(f'Request error: attempt {i}/{retries} - {e}')
                    await asyncio.sleep(5)
                else:
                    logger.error(f'Request failed after {retries} attempts: {e}')
                    return (None, st)

        return (None, st)

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
        resp, _ = await self.request(url, headers, method, json, data, timeout, retries, proxy, ssl)

        if resp is None:
            logger.error('Json data fetch failed')
            return None

        try:
            js = await resp.json(content_type=None)
        except Exception as e:
            logger.error(f'Json decode failed: {e}')
            return None
        finally:
            resp.release()

        if js:
            logger.info('Json data fetched')
            return js

        logger.error('Json data fetch failed')
        return None

    async def getRaw(
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
    ) -> tuple[bytes | None, int | None]:
        '''For the endpoints that answer with text/html instead of json.'''
        resp, st = await self.request(url, headers, method, json, data, timeout, retries, proxy, ssl)
        if resp is None:
            return (None, st)
        try:
            return (await resp.read(), st)
        finally:
            resp.release()

    # ── codegen helpers ──────────────────────────────────────────────────

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

    # ── HAR ──────────────────────────────────────────────────────────────

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
            logger.error(f'HAR not found: {file}')
            return

        with open(file, 'r', encoding='utf-8') as f:
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
                    except Exception:
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
                    except Exception:
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

        return res.model_dump()

    @staticmethod
    def har_summary(parsed: dict, withQuery: bool = False) -> list[dict]:
        '''
        Flattens parse_har_to_endpoints() into the thing you actually want to
        read: one row per (method, host, path[, query]) sorted by popularity.

        withQuery=False merges all query strings of a path and only keeps the
        union of the query keys — that's how you see the real parameters
        instead of 40 copies of the same endpoint.
        '''
        rows: dict[tuple, dict] = {}

        for host, paths in parsed.get('url', {}).items():
            for path, queries in paths.items():
                for query, ep in queries.items():
                    for method, p in ep.get('params', {}).items():
                        keys = []
                        if query:
                            keys = [kv.split('=')[0] for kv in query.lstrip('?').split('&') if kv]

                        key = (method, host, path, tuple(sorted(keys)) if withQuery else ())
                        row = rows.setdefault(key, {
                            'method': method,
                            'host': host,
                            'path': path,
                            'query': [],
                            'calls': 0,
                            'statuses': set(),
                            'bodies': [],
                        })
                        row['calls'] += p.get('requests_count', 0)
                        for k in keys:
                            if k not in row['query']:
                                row['query'].append(k)
                        for r in p.get('requests', {}).values():
                            row['statuses'].add(r['response']['status'])
                            body = r['request'].get('body')
                            if body and body not in row['bodies'] and len(row['bodies']) < 3:
                                row['bodies'].append(body)

        out = []
        for row in rows.values():
            row['statuses'] = sorted(row['statuses'])
            out.append(row)
        out.sort(key=lambda r: (r['host'], r['path'], r['method']))
        return out


def _cli(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='HAR -> endpoint map')
    ap.add_argument('har', help='path to .har / .har.txt')
    ap.add_argument('-o', '--out', help='write json here (default: stdout)')
    ap.add_argument('-d', '--domain', action='append', help='only urls containing this (repeatable)')
    ap.add_argument('--no-body', action='store_true', help='drop request/response bodies')
    ap.add_argument('--full', action='store_true', help='keep query strings apart')
    ap.add_argument('--quiet', action='store_true', help='json only, no table')
    a = ap.parse_args(argv)

    parsed = Helper().parse_har_to_endpoints(
        Path(a.har),
        domains=a.domain,
        incPayload=not a.no_body,
        incResponse=not a.no_body,
    )
    if parsed is None:
        return 1

    if a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)
        logger.info(f'wrote {a.out}')

    if not a.quiet:
        for r in Helper.har_summary(parsed, withQuery=a.full):
            q = ('?' + '&'.join(r['query'])) if r['query'] else ''
            print(f"{r['calls']:>4}  {r['method']:<6} {r['host']}{r['path']}{q}")

    return 0


if __name__ == '__main__':
    sys.exit(_cli())
