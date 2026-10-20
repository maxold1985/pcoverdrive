#!/usr/bin/env python3
"""Servidor HTTP local do catálogo Overdrive para Windows (somente biblioteca padrão)."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
import argparse
import json
import os
import re
import threading
import urllib.request
import urllib.error
from urllib.parse import urlparse
from uuid import uuid4

JOBS = {}
LOCK = threading.Lock()
ROOT = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = ROOT / 'downloads'
MAX_JSON = 8192
CUSTOM_FILE = ROOT / 'web' / 'data' / 'custom-games.json'
DLPS_FILE = ROOT / 'catalogos' / 'dlpsgame_ps4' / 'jogos.json'

def permitted_source(game_id, url):
    file = ROOT / 'app' / 'data' / 'releases' / (game_id + '.json')
    if not file.is_file():
        try:
            games = json.loads(CUSTOM_FILE.read_text(encoding='utf-8'))
            return any(g['id'] == game_id and g.get('downloadUrl') == url for g in games)
        except (OSError,ValueError):
            return False
    try:
        releases = json.loads(file.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    def scan(node):
        if isinstance(node, list):
            return any(scan(x) for x in node)
        if isinstance(node, dict):
            return any((k in ('url', 'browserUrl') and v == url) or scan(v) for k, v in node.items())
        return False
    return scan(releases)

def run_download(job_id, url, game_id):
    job = JOBS[job_id]
    target = DOWNLOAD_DIR / game_id
    try:
        target.mkdir(parents=True, exist_ok=True)
        parsed = urlparse(url)
        archive = parsed.hostname in ('archive.org', 'www.archive.org')
        response = None
        if archive:
            try:
                from archive_auth import session as archive_session
                client = archive_session()
            except (ImportError, RuntimeError):
                client = None
            if client is not None:
                response = client.get(url, stream=True, timeout=(20, 60), allow_redirects=True)
                response.raise_for_status()
        if response is None:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36',
                'Accept': '*/*', 'Accept-Encoding': 'identity'
            })
            response = urllib.request.urlopen(req, timeout=60)
        with response:
            final_url = response.url if hasattr(response, 'url') else response.geturl()
            final = urlparse(final_url)
            if final.scheme != 'https' or not final.hostname:
                raise ValueError('Redirecionamento nao permitido')
            filename = Path(parsed.path).name or 'download.bin'
            filename = re.sub(r'[^A-Za-z0-9._-]', '_', unquote(filename))[:150]
            if filename in ('.', '..', ''): filename = 'download.bin'
            dest = target / filename
            part = dest.with_suffix(dest.suffix + '.part')
            if dest.exists() or part.exists():
                raise FileExistsError('Arquivo ja existe')
            job['total'] = int(response.headers.get('Content-Length', 0) or 0)
            job['status'] = 'baixando'
            try:
                with part.open('xb') as out:
                    chunks = response.iter_content(chunk_size=262144) if hasattr(response, 'iter_content') else iter(lambda: response.read(262144), b'')
                    for chunk in chunks:
                        if not chunk: continue
                        out.write(chunk)
                        job['received'] += len(chunk)
                part.rename(dest)
            except Exception:
                part.unlink(missing_ok=True)
                raise
            job['status'] = 'concluido'
            job['file'] = str(dest)
    except Exception as exc:
        job['status'] = 'erro'
        if isinstance(exc, urllib.error.HTTPError):
            job['error'] = f'HTTP {exc.code}: {exc.reason}'
        else:
            job['error'] = str(exc)

ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        route = urlsplit(self.path).path
        if route == '/api/archive-auth/status':
            try:
                from archive_auth import saved_config
                payload = {'authenticated': bool(saved_config())}
            except Exception:
                payload = {'authenticated': False}
            self.send_json(payload)
            return
        if route == "/":
            self.send_response(302)
            self.send_header("Location", "/web/")
            self.end_headers()
            return
        if route.startswith("/api/releases/"):
            game_id = unquote(route.removeprefix("/api/releases/"))
            if not ID.fullmatch(game_id):
                self.send_error(400, "ID invalido")
                return
            target = ROOT / "app" / "data" / "releases" / (game_id + ".json")
            if not target.is_file():
                self.send_error(404, "Sem releases locais")
                return
            try:
                data = target.read_bytes()
            except OSError:
                self.send_error(500)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        if route == '/api/dlpsgame-games':
            try:
                source = json.loads(DLPS_FILE.read_text(encoding='utf-8')) if DLPS_FILE.is_file() else []
                if not isinstance(source, list):
                    raise ValueError('Catalogo invalido')
                items = []
                for index, entry in enumerate(source):
                    if not isinstance(entry, dict):
                        continue
                    title, url = entry.get('titulo'), entry.get('url')
                    if not isinstance(title, str) or not isinstance(url, str):
                        continue
                    parsed = urlparse(url)
                    if parsed.scheme != 'https' or parsed.hostname not in ('dlpsgame.com', 'www.dlpsgame.com'):
                        continue
                    items.append({'id': f'DLPS{index:06d}', 'title': title[:180],
                                  'platform': 'ps4', 'developer': '', 'providers': ['dlpsgame'],
                                  'sourceUrl': url, 'art': {'cover': entry.get('imagem', '') if isinstance(entry.get('imagem', ''), str) and urlparse(entry.get('imagem', '')).scheme == 'https' else ''}})
                self.send_json(items)
            except (OSError, ValueError, TypeError):
                self.send_json({'error': 'Falha ao ler catalogo DLPSGame'}, 500)
            return
        if route == '/api/custom-games':
            try:
                data = CUSTOM_FILE.read_bytes() if CUSTOM_FILE.is_file() else b'[]'
            except OSError:
                self.send_error(500)
                return
            self.send_response(200)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if route.startswith('/api/downloads/'):
            job_id = route.rsplit('/', 1)[-1]
            with LOCK:
                job = JOBS.get(job_id)
            if job is None:
                self.send_error(404)
                return
            data = json.dumps(job).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()

    def send_json(self, value, status=200):
        payload = json.dumps(value).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        if self.headers.get('Origin') not in (None, 'http://127.0.0.1:8877'):
            self.send_error(403)
            return
        if urlsplit(self.path).path in ('/api/archive-auth/login', '/api/archive-auth/logout'):
            # Only requests from this local app are accepted; never log credentials.
            if self.headers.get('Origin') != 'http://127.0.0.1:8877':
                self.send_error(403, 'Origem nao autorizada')
                return
            if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                self.send_error(415, 'JSON obrigatorio')
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= MAX_JSON:
                    raise ValueError('Tamanho invalido')
                data = json.loads(self.rfile.read(size))
                from archive_auth import login, logout
                if urlsplit(self.path).path.endswith('/logout'):
                    logout()
                    self.send_json({'authenticated': False})
                else:
                    email = data.get('email', '')
                    password = data.get('password', '')
                    if not isinstance(email, str) or not isinstance(password, str):
                        raise ValueError('Credenciais invalidas')
                    login(email.strip(), password)
                    self.send_json({'authenticated': True})
            except (ValueError, KeyError, TypeError) as exc:
                self.send_json({'error': str(exc)}, 400)
            except Exception:
                self.send_json({'error': 'Falha na autenticacao. Verifique credenciais, conexao e dependencias Python.'}, 502)
            return
        if urlsplit(self.path).path == '/api/custom-games':
            try:
                size = int(self.headers.get('Content-Length','0'))
                if not 0 < size <= MAX_JSON: raise ValueError('Tamanho invalido')
                data = json.loads(self.rfile.read(size))
                title = data['title'].strip()
                game_id = data['id'].strip()
                platform = data['platform'].lower()
                url = data.get('url','').strip()
                cover = data.get('cover','').strip()
                if not 1 <= len(title) <= 180 or not ID.fullmatch(game_id) or platform not in ('ps4','ps5'): raise ValueError('Dados invalidos')
                if url and urlparse(url).scheme != 'https': raise ValueError('URL precisa ser HTTPS')
                if cover and urlparse(cover).scheme != 'https': raise ValueError('Capa precisa ser HTTPS')
                CUSTOM_FILE.parent.mkdir(parents=True,exist_ok=True)
                games = json.loads(CUSTOM_FILE.read_text(encoding='utf-8')) if CUSTOM_FILE.is_file() else []
                if any(g['id'] == game_id for g in games): raise ValueError('ID ja cadastrado')
                record = {'id':game_id,'title':title,'platform':platform,'art':{'cover':cover},'developer':'','publisher':'','providers':['manual'] if url else [],'downloadUrl':url}
                games.append(record)
                tmp = CUSTOM_FILE.with_suffix('.tmp')
                tmp.write_text(json.dumps(games,ensure_ascii=False,indent=2),encoding='utf-8')
                tmp.replace(CUSTOM_FILE)
                payload = json.dumps(record).encode()
                self.send_response(201)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except (ValueError, KeyError, TypeError, OSError) as exc:
                self.send_error(400,str(exc))
            return
        if urlsplit(self.path).path != '/api/downloads':
            self.send_error(404)
            return
        if self.headers.get('Origin') not in (None, 'http://127.0.0.1:8877'):
            self.send_error(403)
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_JSON: raise ValueError('Invalid body size')
            data = json.loads(self.rfile.read(size))
            game_id, url = data['gameId'], data['url']
            parsed = urlparse(url)
            if not ID.fullmatch(game_id) or parsed.scheme != 'https' or not parsed.hostname or not permitted_source(game_id, url):
                raise ValueError('Fonte nao autorizada ou invalida')
        except (ValueError, KeyError, TypeError):
            self.send_error(400, 'Requisicao invalida')
            return
        job_id = uuid4().hex
        with LOCK:
            JOBS[job_id] = {'id':job_id,'status':'iniciando','received':0,'total':0,'file':None,'error':None}
        threading.Thread(target=run_download, args=(job_id,url,game_id), daemon=True).start()
        payload = json.dumps({'id':job_id}).encode()
        self.send_response(202)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8877)
    parser.add_argument("--download-dir", type=Path, default=ROOT / "downloads", help="Pasta de downloads no Windows")
    args = parser.parse_args()
    global DOWNLOAD_DIR
    DOWNLOAD_DIR = args.download_dir.expanduser().resolve()
    os.chdir(ROOT)
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as httpd:
        print(f"Overdrive PC: http://127.0.0.1:{args.port}/web/", flush=True)
        httpd.serve_forever()

if __name__ == "__main__":
    main()
