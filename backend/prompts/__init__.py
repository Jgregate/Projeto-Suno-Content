"""Prompts versionados em arquivos .md.

Formato de cada arquivo: prompt de sistema, uma linha `---USER---`, e o
template da mensagem do usuário. Variáveis usam `$nome` (string.Template),
para não conflitar com chaves de JSON.
"""

import hashlib
from functools import lru_cache
from pathlib import Path
from string import Template

from backend.config import PROMPTS_DIR

USER_MARKER = "---USER---"


@lru_cache
def load_prompt(name: str, directory: Path = PROMPTS_DIR) -> tuple[Template, Template]:
    """Devolve (sistema, usuário) do arquivo <directory>/<name>.md."""
    raw = (directory / f"{name}.md").read_text(encoding="utf-8")
    if USER_MARKER in raw:
        system, user = raw.split(USER_MARKER, 1)
    else:
        system, user = raw, ""
    return Template(system.strip()), Template(user.strip())


def load_text(name: str, directory: Path = PROMPTS_DIR) -> str:
    """Arquivo de prompt sem template (ex.: regras de nível)."""
    return (directory / f"{name}.md").read_text(encoding="utf-8").strip()


def render(name: str, directory: Path = PROMPTS_DIR, **values: str) -> tuple[str, str]:
    """Preenche o prompt; variável faltando levanta KeyError (falha cedo)."""
    system, user = load_prompt(name, directory)
    return system.substitute(values), user.substitute(values)


def prompts_hash(directory: Path = PROMPTS_DIR) -> str:
    """Hash (12 hex) do conteúdo de todos os .md, em ordem de nome. Muda se qualquer prompt mudar."""
    digest = hashlib.sha256()
    for path in sorted(directory.glob("*.md")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]
