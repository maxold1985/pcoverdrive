#!/usr/bin/env python3
"""Coleta links de páginas públicas do índice PS4, sem baixar jogos.

Uso: py -3 catalogos/dlpsgame_ps4/coletar_links.py
Dependências: apenas biblioteca padrão do Python.
"""
import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = "https://dlpsgame.com/list-all-game-ps4/"
OUTPUT = Path(__file__).resolve().parent
MAX_PAGES = 100
DELAY_SECONDS = 1.5


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.href = None
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self.href = dict(attrs).get("href")
            self.parts = []

    def handle_data(self, data):
        if self.href is not None:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.href is not None:
            self.links.append((self.href, " ".join(" ".join(self.parts).split())))
            self.href = None
            self.parts = []


def normalized(url):
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return None
    if parts.hostname not in ("dlpsgame.com", "www.dlpsgame.com"):
        return None
    return urlunsplit(("https", "dlpsgame.com", parts.path.rstrip("/") + "/", "", ""))


def fetch(url):
    request = Request(url, headers={"User-Agent": "PCOverdriveCatalogIndexer/1.0 (public links only)"})
    with urlopen(request, timeout=25) as response:
        return response.read(8 * 1024 * 1024).decode("utf-8", errors="replace")


def main():
    records = {}
    pages = 0
    for page in range(1, MAX_PAGES + 1):
        url = BASE if page == 1 else urljoin(BASE, f"page/{page}/")
        try:
            html = fetch(url)
        except (HTTPError, URLError, TimeoutError) as exc:
            print(f"Parando na página {page}: {exc}")
            break
        parser = LinkParser()
        parser.feed(html)
        found = 0
        for href, title in parser.links:
            target = normalized(urljoin(url, href))
            if not target or target == normalized(BASE):
                continue
            path = urlsplit(target).path
            if re.fullmatch(r"/(?:list-all-game-ps4/)?page/\d+/", path):
                continue
            if path.startswith(("/category/", "/tag/", "/author/", "/wp-", "/feed/")):
                continue
            if not title or len(title) > 220:
                continue
            if target not in records:
                records[target] = {"titulo": title, "url": target}
                found += 1
        pages += 1
        print(f"Página {page}: {found} links novos; total {len(records)}")
        if page > 1 and found == 0:
            break
        time.sleep(DELAY_SECONDS)

    ordered = sorted(records.values(), key=lambda item: item["titulo"].casefold())
    (OUTPUT / "jogos.json").write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUTPUT / "links.txt").write_text("".join(item["url"] + "\n" for item in ordered), encoding="utf-8")
    print(f"Salvos {len(ordered)} links em {OUTPUT}. Páginas consultadas: {pages}")


if __name__ == "__main__":
    main()
