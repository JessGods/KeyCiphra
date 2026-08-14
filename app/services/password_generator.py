"""Gerador de senhas baseado exclusivamente no módulo ``secrets``."""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass


SYMBOLS = "!@#$%^&*()-_=+[]{};:,.?"


@dataclass(frozen=True, slots=True)
class PasswordOptions:
    """Categorias e comprimento usados na geração."""

    length: int = 20
    uppercase: bool = True
    lowercase: bool = True
    digits: bool = True
    symbols: bool = True


def generate_password(options: PasswordOptions | None = None) -> str:
    """Gera uma senha e garante ao menos um caractere de cada grupo escolhido."""
    selected = options or PasswordOptions()
    groups: list[str] = []
    if selected.uppercase:
        groups.append(string.ascii_uppercase)
    if selected.lowercase:
        groups.append(string.ascii_lowercase)
    if selected.digits:
        groups.append(string.digits)
    if selected.symbols:
        groups.append(SYMBOLS)

    if not groups:
        raise ValueError("Selecione pelo menos uma categoria de caracteres.")
    if selected.length < len(groups):
        raise ValueError("O comprimento é menor que o número de categorias selecionadas.")
    if selected.length > 1_024:
        raise ValueError("O comprimento máximo é 1024 caracteres.")

    password = [secrets.choice(group) for group in groups]
    alphabet = "".join(groups)
    password.extend(secrets.choice(alphabet) for _ in range(selected.length - len(groups)))

    # Fisher–Yates com fonte criptograficamente segura.
    for index in range(len(password) - 1, 0, -1):
        other = secrets.randbelow(index + 1)
        password[index], password[other] = password[other], password[index]
    return "".join(password)
