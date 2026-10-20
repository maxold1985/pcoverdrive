#!/usr/bin/env python3
"""Enriquece jogos.json com URLs de capas das paginas publicas, sem baixar imagens."""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import time
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "jogos.json"

class ImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
        self.inside_content = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("article", "main"):
            self.inside_content += 1
        if tag != "img":
            return
        src = next((attrs.get(key) for key in ("data-src", "data-lazy-src", "src") if attrs.get(key)), "")
        if src:
            self.images.append((src, self.inside_content > 0, attrs))

    def handle_endtag(self, tag):
        if tag in ("article", "main"):
            self.inside_content = max(0, self.inside_content - 1)

def cover_url(page, html):
    parser = ImageParser()
    parser.feed(html)
    candidates = []
    for index, (src, inside, attrs) in enumerate(parser.images):
        url = urljoin(page, src)
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            continue
        path = parsed.path.lower()
        if not path.endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        if any(word in path for word in ("logo", "banner", "scroll-top", "avatar", "icon")):
            continue
        try:
            width = int(attrs.get("width") or 0)
            height = int(attrs.get("height") or 0)
        except ValueError:
            width = height = 0
        ratio = width / height if height else 0
        score = (4 if inside else 0) + (3 if 0.55 <= ratio <= 0.85 else 0)
        score += (2 if index > 1 else -5)
        if "blogspot.com" in parsed.hostname:
            score += 1
        candidates.append((score, -index, url))
    if not candidates:
        return ""
    candidates.sort(reverse=True)
    return candidates[0][2]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, default=20, help="Numero maximo de paginas por execucao; 0 para todas")
    ap.add_argument("--intervalo", type=float, default=2.0, help="Segundos entre requisicoes")
    args = ap.parse_args()
    if args.limite < 0 or args.intervalo < 0:
        ap.error("Valores negativos nao sao permitidos")
    records = json.loads(CATALOG.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        ap.error("Catalogo invalido")
    count = success = 0
    cache = {x["url"]: x["imagem"] for x in records if isinstance(x, dict) and x.get("imagem") and x.get("url")}
    for index, record in enumerate(records):
        if not isinstance(record, dict) or not record.get("url") or record.get("imagem"):
            continue
        if record["url"] in cache:
            record["imagem"] = cache[record["url"]]
            continue
        if args.limite and count >= args.limite:
            break
        url = record["url"]
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in ("dlpsgame.com", "www.dlpsgame.com"):
            continue
        count += 1
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; PCOverdriveCoverIndexer/1.0)"})
            with urlopen(req, timeout=20) as response:
                html = response.read(4 * 1024 * 1024).decode("utf-8", errors="replace")
            image = cover_url(url, html)
            if image:
                record["imagem"] = image
                cache[url] = image
                success += 1
                print(f"[{count}] OK {record.get('titulo', '')}: {image}")
            else:
                print(f"[{count}] Sem imagem: {url}")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            print(f"[{count}] Falha {url}: {exc}")
            if isinstance(exc, HTTPError) and exc.code in (403, 429):
                print("Site bloqueou as requisicoes. Interrompendo para evitar novas tentativas.")
                break
        finally:
            temp = CATALOG.with_suffix(".tmp")
            temp.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temp.replace(CATALOG)
        if args.intervalo and (not args.limite or count < args.limite):
            time.sleep(args.intervalo)
    print(f"Paginas consultadas: {count}; capas novas: {success}; total com imagem: {sum(bool(x.get('imagem')) for x in records if isinstance(x, dict))}")

if __name__ == "__main__":
    main()
