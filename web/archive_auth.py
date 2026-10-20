"""Autenticacao Archive.org: biblioteca oficial + Windows Credential Manager (keyring)."""
import getpass
import json
import sys

SERVICE = "OverdrivePC.ArchiveOrg"
ACCOUNT = "archive.org"

def dependencies():
    try:
        import internetarchive
        import keyring
    except ImportError as exc:
        raise RuntimeError("Instale dependencias: py -3 -m pip install -r web\\requirements.txt") from exc
    return internetarchive, keyring

def saved_config():
    ia, keyring = dependencies()
    raw = keyring.get_password(SERVICE, ACCOUNT)
    return json.loads(raw) if raw else None

def session():
    ia, _ = dependencies()
    config = saved_config()
    return ia.get_session(config=config) if config else None

def login(email, password):
    """Autentica com o cliente oficial; persiste somente a configuracao de sessao."""
    if sys.platform != "win32":
        raise RuntimeError("O armazenamento seguro esta habilitado somente no Windows.")
    if not email or not password:
        raise ValueError("Informe email e senha.")
    _, keyring = dependencies()
    from internetarchive.config import get_auth_config
    config = get_auth_config(email, password)
    if not config or not config.get("cookies"):
        raise RuntimeError("Archive.org nao retornou cookies de sessao.")
    keyring.set_password(SERVICE, ACCOUNT, json.dumps(config))

def logout():
    _, keyring = dependencies()
    try:
        keyring.delete_password(SERVICE, ACCOUNT)
    except keyring.errors.PasswordDeleteError:
        pass

def main():
    if sys.platform != "win32":
        raise SystemExit("Este utilitario armazena credenciais no gerenciador seguro do sistema.")
    ia, keyring = dependencies()
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command == "login":
        email = input("Email do Archive.org: ").strip()
        password = getpass.getpass("Senha (nao sera salva): ")
        try:
            login(email, password)
            print("Sessao salva no Windows Credential Manager.")
        finally:
            password = None
    elif command == "logout":
        logout()
        print("Sessao removida.")
    elif command == "status":
        config = saved_config()
        print("Sessao configurada." if config else "Sem sessao. Execute: py -3 web\\archive_auth.py login")
    else:
        raise SystemExit("Uso: py -3 web\\archive_auth.py [login|status|logout]")

if __name__ == "__main__":
    main()
