# Auditoria interna de segurança — 15 de agosto de 2026

## Escopo

Este ciclo avaliou o código Python, dependências diretas, testes, permissões do
armazenamento local, evolução do schema SQLite e custo dos parâmetros Argon2id.
É uma auditoria interna reproduzível, não uma certificação nem uma revisão
criptográfica independente.

## Controles implementados

- A pasta `%LOCALAPPDATA%\KeyCiphra` remove a herança ampla no Windows e concede
  controle total somente ao usuário atual, SYSTEM e Administradores. Em POSIX,
  diretórios recebem modo `0700` e arquivos `0600`.
- O caminho do `icacls.exe` é resolvido pela API do Windows, os argumentos são
  enviados sem shell e o alvo é rejeitado se apontar para uma raiz ou para toda
  a pasta pessoal.
- Migrações de schema são incrementais, executadas somente após autenticar a
  senha mestra e protegidas por savepoint, incluindo DDL e metadados.
- O GitHub Actions executa Ruff, Bandit, pip-audit, `pip check` e toda a suíte de
  testes no Windows e no Ubuntu. Ações de terceiros estão fixadas por SHA.

## Resultado local reproduzível

Comandos:

```powershell
.\hardening.ps1
.\.venv\Scripts\python.exe -m app.security.kdf_benchmark --runs 5
```

Benchmark Argon2id deste computador:

| Parâmetro | Resultado |
|---|---:|
| Iterações medidas | 5 |
| Mínimo | 96,08 ms |
| Mediana | 97,84 ms |
| Máximo | 112,80 ms |
| `time_cost` | 3 |
| Memória | 65.536 KiB |
| Paralelismo | 4 |

O benchmark usa frase e salt fictícios e não acessa credenciais, banco de dados
ou senha mestra. O resultado depende do hardware e deve ser repetido nas
máquinas suportadas.

## Riscos residuais

- Uma conta de administrador, malware no processo, keylogger ou sistema
  operacional comprometido continua fora do modelo de proteção.
- Python não garante apagamento completo e imediato de segredos da memória.
- Perder a senha mestra torna o cofre irrecuperável por projeto.
- Ainda são necessárias revisão humana independente, testes em mais classes de
  hardware e assinatura do instalador antes de uma distribuição ampla.
