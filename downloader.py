# maybe shit
from pathlib import Path
from urllib.parse import urlparse
import aiofiles
import aiohttp
import asyncio
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

console = Console()

class SankakuDL:
    def __init__(self, mbSize=100):
        self.active_tasks = {}
        self.psize = mbSize

    async def download(self, url: str, path: str | Path, timeout: aiohttp.ClientTimeout):
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:151.0) Gecko/20100101 Firefox/151.0'}
        self.timeout = timeout

        console.print(f'\n[bold cyan]Starting download[/bold cyan]')
        console.print(f'[dim]URL: {url}[/dim]')

        file = Path(self._get_filename_from_url(url))

        if path:
            if isinstance(path, str):
                path = Path(path).resolve()
            else:
                path = path.resolve()
            file = path / file
            
        async with aiohttp.ClientSession() as s:
            async with s.head(url, headers=headers, timeout=self.timeout) as resp:
                size = int(resp.headers.get('Content-Length', 0)) if resp.status == 200 else 0

        if not size:
            console.print('[bold red]Failed to get file size[/bold red]')
            return False
        
        console.print(f'[green]File size: {size / 1024 / 1024:.2f} MB[/green]')
        console.print(f'[dim]Target: {file}[/dim]')

        tasks = []
        seg=False
        progress = Progress(
            TextColumn('[bold blue]{task.description}'),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        )

        with progress:
            if file.is_file() or size < self.psize * 1024 * 1024:
                file_size = file.stat().st_size if file.exists() else 0
                if file_size == size:
                    console.print('[yellow]File already exists, skipping[/yellow]')
                    return True
                task_id = progress.add_task(f'[cyan]Downloading {file.name}', total=size - file_size)
                tasks.append(asyncio.create_task(
                                self._download_seg(url, file_size, size, headers, file, task_id, progress)
                            ))
                
            else:
                seg=True
                seg_count = 4
                seg_size = size // seg_count

                tfile = file / file.name
                Path.mkdir(tfile.parent, exist_ok=True)

                console.print(f'[cyan]Splitting into {seg_count} segments[/cyan]')
                
                for i in range(seg_count):
                    start = i * seg_size
                    end = (i + 1) * seg_size - 1 if i < seg_count - 1 else size - 1
                    
                    segment_file = tfile.with_suffix(f'.{i+1}')
                    
                    downloaded = segment_file.stat().st_size if segment_file.is_file() else 0
                    downloaded = min(downloaded, end - start + 1)
                    
                    if downloaded < (end - start + 1):
                        task_id = progress.add_task(
                            f'[magenta]Segment {i+1}/4', 
                            total=end - start + 1,
                            completed=downloaded
                        )
                        tasks.append(asyncio.create_task(
                                        self._download_seg(url, start + downloaded, end, headers, segment_file, task_id, progress)
                                    ))
            if not tasks:
                console.print(f'[bold red]No tasks[/bold red]')
                return False
            
            res = await asyncio.gather(*tasks)
            console.print(f'[dim]Results: {res}[/dim]')
            
            if all(res):
                console.print(f'[bold green]{"All segments" if seg else "File"} downloaded{", merging..." if seg else "."}[/bold green]')
                if seg:
                    await self._connect_segs(file, progress)
                    console.print(f'[bold green]Download complete: {file.name}[/bold green]')
                return True
            else:
                console.print('[bold red]Download failed[/bold red]')
        return False
                
    def _get_filename_from_url(self, url: str) -> str:
        parsed = urlparse(url)
        return Path(parsed.path).name
    
    async def _download_seg(self, url: str, start: int, end: int, headers: dict, name: Path, task_id: TaskID, progress: Progress, _max_retries: int = 5):
        headers = headers.copy()
        headers['Range'] = f'bytes={start}-{end}'
        expected_size = end - start + 1

        for attempt in range(1, _max_retries+1):
            try:
                if name.exists() and not name.is_dir() and name.stat().st_size == expected_size:
                    if task_id is not None:
                        progress.update(task_id, completed=expected_size)
                    return True
                
                async with aiohttp.ClientSession() as s:
                    async with s.get(url, headers=headers, timeout=self.timeout) as resp:
                        match resp.status:
                            case 206:
                                async with aiofiles.open(name, 'wb') as f:
                                    downloaded = 0
                                    async for chunk in resp.content.iter_chunked(8192):
                                        await f.write(chunk)
                                        downloaded += len(chunk)
                                        if task_id is not None:
                                            progress.update(task_id, advance=len(chunk), refresh=True)
                                    
                                    if downloaded == expected_size:
                                        return True
                                    else:
                                        console.print(f'[yellow]Size mismatch for {name}[/yellow]')
                                        return False
                            case (404, 403, 410):
                                console.print(f'[red]Fatal error {resp.status} for {name}[/red]')
                                return False
            except asyncio.TimeoutError:
                console.print(f'[yellow]Timeout on attempt {attempt}/{_max_retries}[/yellow]')
            except aiohttp.ClientError as e:
                console.print(f'[yellow]Client error: {e}[/yellow]')
            except Exception as e:
                console.print(f'[red]Unexpected error: {e}[/red]')
                return False
            
                
    async def _connect_segs(self, file: Path, progress: Progress):
        if file.is_file():
            return True
        
        files = sorted([f for f in file.iterdir()], key=lambda x: int(x.suffix[1:]))

        if not files:
            console.print('[yellow]No segments to merge[/yellow]')

        console.print(f'[cyan]Merging {len(files)} segments...[/cyan]')
        
        with progress:
            merge_task = progress.add_task('[blue]Merging segments', total=sum(f.stat().st_size for f in files))
            
            with open(file.parent / 'temp', 'wb') as f:
                for seg_file in files:
                    with open(seg_file, 'rb') as in_file:
                        while chunk := in_file.read(8192):
                            f.write(chunk)
                            progress.update(merge_task, advance=len(chunk))
                    seg_file.unlink()
            progress.update(merge_task, completed=100)
        
        file.rmdir()
        (file.parent / 'temp').rename(file)
        console.print('[green]Segments merged successfully[/green]')