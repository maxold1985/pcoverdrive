#!/usr/bin/env python3
"""Coleta links de páginas públicas do índice PS4, sem baixar jogos.

Uso: py -3 catalogos/dlpsgame_ps4/coletar_links.py
Dependências: apenas biblioteca padrão do Python.
"""
import argparse
import json
import re
import time
from html.parser import HTMLParser
from collections import Counter
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
        self.image_alt = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self.href = dict(attrs).get("href")
            self.parts = []
            self.image_alt = []
        elif tag.lower() == "img" and self.href is not None:
            alt = dict(attrs).get("alt", "")
            if alt:
                self.image_alt.append(alt)

    def handle_data(self, data):
        if self.href is not None:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.href is not None:
            title = " ".join(" ".join(self.parts).split())
            if not title:
                title = " ".join(" ".join(self.image_alt).split())
            self.links.append((self.href, title))
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
    ap = argparse.ArgumentParser(description="Coleta links públicos de páginas PS4")
    ap.add_argument("--html", type=Path, help="Arquivo HTML salvo pelo navegador")
    ap.add_argument("--unicos", action="store_true", help="Opcional: remove URLs repetidas")
    ap.add_argument("--dom-json", type=Path, help="JSON exportado do DOM do Edge com href e titulo")
    args = ap.parse_args()
    records = []  # Preserva cada ocorrência, mesmo quando o URL se repete.
    pages = 0
    stats = Counter()
    rejected = []
    if args.html and args.dom_json:
        ap.error("Use --html ou --dom-json, não ambos")
    page_numbers = [1] if (args.html or args.dom_json) else range(1, MAX_PAGES + 1)
    for page in page_numbers:
        url = BASE if page == 1 else urljoin(BASE, f"page/{page}/")
        if args.dom_json:
            raw = json.loads(args.dom_json.read_text(encoding="utf-8-sig"))
            if not isinstance(raw, list):
                ap.error("--dom-json deve conter uma lista JSON")
            parsed_links = [(x.get("href", ""), x.get("titulo", "")) for x in raw if isinstance(x, dict)]
        elif args.html:
            html = args.html.read_text(encoding="utf-8", errors="replace")
        else:
            try:
                html = fetch(url)
            except (HTTPError, URLError, TimeoutError) as exc:
                print(f"Parando na página {page}: {exc}")
                if page == 1:
                    print("Nenhum arquivo foi sobrescrito. Salve a página no Edge e use --html arquivo.html")
                    return
                break
        if not args.dom_json:
            parser = LinkParser()
            parser.feed(html)
            parsed_links = parser.links
        found = 0
        stats["ancoras_html"] += len(parsed_links)
        for href, title in parsed_links:
            target = normalized(urljoin(url, href))
            reason = None
            if not target:
                reason = "dominio_ou_esquema"
            elif target == normalized(BASE):
                reason = "indice"
            else:
                path = urlsplit(target).path
                if re.fullmatch(r"/(?:list-all-game-ps4/)?page/\\d+/", path):
                    reason = "paginacao"
                elif path in ("/list-all-game-ps2/", "/list-all-game-ps3/", "/list-game-ps5/"):
                    reason = "outras_plataformas"
                elif path.startswith(("/category/", "/tag/", "/author/", "/wp-", "/feed/")):
                    reason = "navegacao"
                elif not title:
                    reason = "titulo_vazio"
                elif len(title) > 220:
                    reason = "titulo_longo"
            if reason:
                stats["rejeitado_" + reason] += 1
                rejected.append({"motivo": reason, "titulo": title, "href": href})
                continue
            records.append({"titulo": title, "url": target})
            found += 1
            stats["aceitos"] += 1
        pages += 1
        print(f"Página {page}: {found} links novos; total {len(records)}")
        if not (args.html or args.dom_json) and page > 1 and found == 0:
            break
        if not (args.html or args.dom_json):
            time.sleep(DELAY_SECONDS)

    diagnostics = {"estatisticas": dict(stats), "rejeitados": rejected}
    (OUTPUT / "diagnostico.json").write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Diagnóstico:", dict(stats))
    if not records:
        print("Nenhum link encontrado; arquivos anteriores preservados.")
        return
    if args.unicos:
        seen = set()
        records = [item for item in records if not (item["url"] in seen or seen.add(item["url"]))]
    ordered = sorted(records, key=lambda item: item["titulo"].casefold())
    (OUTPUT / "jogos.json").write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUTPUT / "links.txt").write_text("".join(item["url"] + "\n" for item in ordered), encoding="utf-8")
    print(f"Salvos {len(ordered)} links em {OUTPUT}. Páginas consultadas: {pages}")


if __name__ == "__main__":
    main()
