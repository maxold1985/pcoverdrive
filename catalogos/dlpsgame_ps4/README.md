# Índice público de jogos PS4 — DLPSGame

Esta pasta contém um coletor de **links públicos das páginas do catálogo**, não um downloader de jogos.

## Executar no Windows

Na raiz do repositório:

```powershell
py -3 catalogos\dlpsgame_ps4\coletar_links.py
```

O script gera `jogos.json` (título e URL) e `links.txt` (uma URL por linha), ambos na mesma pasta. Usa apenas a biblioteca padrão do Python.

**Limitações:** a estrutura HTML do site pode mudar, a página pode bloquear acessos automatizados e nem todos os links coletados serão necessariamente jogos. O coletor limita-se a 100 páginas, faz uma pausa entre requisições e não segue links para serviços de hospedagem ou downloads. Respeite as regras do site e utilize somente conteúdo que você tenha direito de acessar.

Fonte: https://dlpsgame.com/list-all-game-ps4/
