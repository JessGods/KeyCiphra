# KeyCiphra

Gerenciador de senhas desktop local e offline, em desenvolvimento. O KeyCiphra
já possui núcleo criptográfico, persistência SQLite e interface PySide6.

## Estado atual

- Chave de 32 bytes derivada da senha mestra por Argon2id.
- Salt aleatório de 16 bytes por cofre.
- AES-256-GCM com nonce aleatório de 12 bytes por operação.
- Dados associados autenticados (AAD) vinculam payload, cofre e credencial.
- Erro genérico para falhas de autenticação, sem revelar sua causa.
- Metadados versionados e verificador de desbloqueio criptografado.
- CRUD de credenciais persistido em SQLite.
- Todos os campos da credencial armazenados em um payload JSON criptografado.
- Sessão invalidável ao bloquear o cofre.
- Bloqueio automático após 5 minutos sem atividade.
- Clipboard temporário limpo ao expirar ou bloquear o cofre.
- Backup SQLite automático a cada 24 horas e backup manual pela interface.
- Validação de integridade e retenção dos 10 backups mais recentes.
- Exportação portátil e restauração autenticada para uso em outro computador.
- Backup de segurança automático antes de substituir o cofre em uma restauração.
- Dados privados armazenados em `%LOCALAPPDATA%\KeyCiphra` no Windows.
- Executável portátil preparado com ícone e metadados próprios do KeyCiphra.
- Testes de persistência após reabertura, CRUD, adulteração e ausência de
  plaintext sensível no arquivo.

## Requisitos

- Python 3.12 ou superior

## Instalação

No PowerShell, a partir da raiz do projeto:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Executar o aplicativo

```powershell
.\.venv\Scripts\python.exe run.py
```

No primeiro início, a tela solicitará a criação e confirmação de uma frase-senha
mestra com pelo menos 12 caracteres. O cofre será criado na pasta privada do
usuário e reutilizado nos próximos inícios. Para confirmar a persistência:

1. crie uma credencial e feche o aplicativo;
2. execute `run.py` novamente;
3. desbloqueie usando a mesma senha mestra.

Não existe recuperação de senha mestra nesta versão.

No Windows, o caminho completo usado em produção é
`%LOCALAPPDATA%\KeyCiphra\data\vault.db`. Versões de desenvolvimento que ainda
guardavam dados na raiz do projeto são migradas por cópia no primeiro início;
os arquivos antigos não são apagados automaticamente.

## Gerar o executável do Windows

Instale as dependências de desenvolvimento e execute o build:

```powershell
python -m pip install -r requirements-dev.txt
.\build.ps1
```

O resultado será `dist\KeyCiphra.exe`, sem janela de terminal e com o ícone do
produto. O build atual é portátil e ainda não constitui um instalador assinado.

## Arquitetura atual

```text
app/
├── database/                    # conexão e schema SQLite
├── models/                      # Credential e VaultMetadata
├── repositories/               # CRUD criptografado
├── security/
│   ├── kdf.py                   # Argon2id e geração de salt
│   ├── session.py               # sessão bloqueável
│   └── auto_lock.py             # temporizador de inatividade
└── services/
    ├── backup_service.py        # snapshots SQLite consistentes
    ├── crypto_service.py        # AES-256-GCM
    └── vault_service.py         # criação e desbloqueio
tests/
├── test_auto_lock.py
├── test_backup_service.py
├── test_crypto_service.py
├── test_kdf.py
├── test_repository.py
└── test_vault_service.py
```

Os parâmetros Argon2id estão centralizados em `KDFParameters`. Os valores de
produção atuais são 3 iterações, 64 MiB de memória e paralelismo 4. Testes usam
parâmetros explicitamente reduzidos para execução rápida; eles não devem ser
usados para cofres reais.

## Persistência

O cofre usado pela aplicação fica em
`%LOCALAPPDATA%\KeyCiphra\data\vault.db` no Windows. Backups ficam em
`%LOCALAPPDATA%\KeyCiphra\backups`. Bancos locais e arquivos SQLite são
ignorados pelo Git. O banco contém:

- salt e parâmetros públicos do Argon2id;
- versão do formato e do schema;
- verificador de desbloqueio AES-GCM;
- IDs e timestamps técnicos das credenciais;
- nonce e ciphertext autenticado de cada credencial.

Título, usuário, senha, URL, categoria e notas não são gravados em plaintext.
Uma nova instância do serviço consegue desbloquear o mesmo arquivo e recuperar
as credenciais, portanto os dados persistem entre execuções.

## Backups

Os snapshots são criados na subpasta `backups` do diretório privado da aplicação
usando a API de backup do SQLite. Antes de publicar um arquivo, o serviço executa
`PRAGMA integrity_check` e confirma a presença dos metadados do cofre. A
publicação usa substituição atômica e nunca gera uma versão descriptografada.

O primeiro desbloqueio cria um backup automático. Depois disso, o intervalo é
de 24 horas. O botão **Backup** permite criar um snapshot manual. Somente os 10
mais recentes são preservados. A pasta inteira é ignorada pelo Git.

O menu **Transferir** exporta uma cópia consistente para um arquivo `.db` e
importa cofres criados pelo KeyCiphra. Na restauração, a senha mestra do arquivo
é exigida e todas as credenciais são autenticadas antes de qualquer alteração.
O cofre em uso é preservado automaticamente na pasta de backups; após a troca,
o aplicativo bloqueia a sessão e solicita a senha do cofre restaurado.

O arquivo exportado pode ser transportado por mídia removível ou armazenamento
em nuvem, mas não deve ser aberto simultaneamente por dois computadores. A
transferência não cria uma versão em plaintext e a senha mestra deve ser
compartilhada por um canal separado — ou, preferencialmente, não compartilhada.

## Modelo de segurança

O objetivo inicial é proteger credenciais quando o arquivo do cofre ou um
backup criptografado é copiado ou alterado por um atacante. A senha mestra e a
chave derivada não são persistidas. Alterações em nonce, ciphertext, tag ou
dados associados são detectadas pelo AES-GCM.

O projeto não promete proteção completa contra um sistema operacional já
comprometido, keyloggers, malware com acesso ao processo, captura de tela,
debuggers privilegiados ou comprometimento de administrador/root.

## Limitações importantes

Python não permite garantir a remoção imediata e completa de segredos da
memória. O projeto reduz o tempo de vida e o número de cópias desses dados, mas
não afirma oferecer limpeza de memória perfeita.

Na versão inicial, perder a senha mestra tornará o cofre irrecuperável. Não
haverá senha padrão, pergunta secreta, chave escondida, backdoor ou recuperação
por e-mail.

Os parâmetros Argon2id precisam ser medidos nos computadores suportados antes
de uma versão distribuível. Eles são armazenados como metadados do cofre para
permitir atualização futura.

## Referências técnicas

- [AES-GCM na documentação do cryptography](https://cryptography.io/en/stable/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.AESGCM)
- [API de baixo nível do argon2-cffi](https://argon2-cffi.readthedocs.io/en/stable/api.html#low-level)
- [Avisos e licença dos ícones Lucide](THIRD_PARTY_NOTICES.md)
- [Documentação do PyInstaller](https://pyinstaller.org/en/stable/)

## Roadmap

1. Núcleo criptográfico (concluído).
2. Cofre, SQLite e Repository Pattern (concluído).
3. Busca local após desbloqueio e gerador de senhas (concluído).
4. Interface PySide6 (MVP concluído).
5. Bloqueio automático, clipboard temporário, backup e transferência de cofre
   (concluído); logs sanitizados ainda pendentes.
6. Caminhos de produção e executável portátil do Windows (concluído); instalador
   assinado ainda pendente.
7. Hardening, análise estática, dependências e revisão de segurança.
