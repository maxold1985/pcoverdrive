# Archive.org no Overdrive PC (Windows)

O downloader usa a biblioteca oficial `internetarchive` para requisições autenticadas e `keyring` para guardar a configuração de sessão no **Windows Credential Manager**, fora do repositório. A senha digitada não é armazenada diretamente pelo Overdrive.

## Configuração

Na raiz do projeto, no Prompt de Comando:

```bat
py -3 -m pip install -r web\requirements.txt
py -3 web\archive_auth.py login
py -3 web\archive_auth.py status
web\iniciar-windows.bat
```

A autenticação é feita no terminal local, não em uma página exposta na rede. Para desconectar:

```bat
py -3 web\archive_auth.py logout
```

O login cria credenciais/cookies de sessão pelo cliente oficial do Internet Archive. Elas podem expirar; nesse caso, execute `login` novamente. A autenticação não garante acesso a arquivos restritos, removidos ou bloqueados. O download permanece sujeito às permissões da sua conta e às regras do Archive.org.

Downloads são salvos em `downloads/<ID do jogo>/`, ou na pasta indicada com `--download-dir`. A interface exibe o progresso. Não há retomada de downloads interrompidos.

**Segurança:** não compartilhe sua senha, cookies, chaves IA-S3 nem arquivos de configuração. O Windows Credential Manager protege os dados em repouso, mas processos executados sob a mesma conta Windows podem ter acesso às credenciais conforme as permissões do sistema.
