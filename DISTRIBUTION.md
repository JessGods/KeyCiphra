# Distribuição do KeyCiphra no Windows

## Gerar o instalador

O instalador é criado por usuário, sem elevação administrativa, em
`%LOCALAPPDATA%\Programs\KeyCiphra`. Cofres, backups, preferências e logs ficam
em `%LOCALAPPDATA%\KeyCiphra`, fora da pasta do programa. Por isso, atualizar ou
desinstalar o aplicativo não remove os dados privados.

```powershell
winget install --id JRSoftware.InnoSetup -e --source winget
.\build-installer.ps1
```

O resultado é `dist\KeyCiphra-Setup-0.9.0.exe`, acompanhado de um arquivo
`.sha256`. Uma versão mais nova usa o mesmo `AppId` e substitui apenas os
arquivos do programa. O instalador pede para fechar o KeyCiphra antes da troca;
ele nunca deve ser executado com um cofre desbloqueado.

O teste isolado instala em uma pasta temporária, abre o executável, desinstala e
confirma que a área de dados não foi removida:

```powershell
.\test-installer.ps1
```

## Assinatura Authenticode

O certificado de assinatura nunca deve ser armazenado no repositório. Instale
o Windows SDK (que fornece `signtool.exe`) e defina uma destas opções somente na
sessão protegida que gera a versão:

```powershell
$env:KEYCIPHRA_SIGN_CERTIFICATE_PATH = "C:\caminho-protegido\certificado.pfx"
$env:KEYCIPHRA_SIGN_CERTIFICATE_PASSWORD = "senha-do-certificado"
.\build-installer.ps1 -Sign
```

Ou utilize um certificado já presente no repositório de certificados do
Windows:

```powershell
$env:KEYCIPHRA_SIGN_CERTIFICATE_THUMBPRINT = "THUMBPRINT"
.\build-installer.ps1 -Sign
```

O script assina e verifica primeiro o executável e depois o instalador, usando
SHA-256 e carimbo de tempo. Sem um certificado de uma autoridade confiável, o
Windows continuará exibindo **Editor desconhecido**; isso é esperado e não deve
ser contornado com um certificado ou chave incluídos no programa.

## Processo de atualização

1. bloqueie e feche o KeyCiphra;
2. gere os testes, o executável e o instalador;
3. assine os dois artefatos quando o certificado estiver disponível;
4. publique o instalador final e seu SHA-256;
5. execute o novo instalador, que reconhece a instalação pelo `AppId` estável;
6. abra o aplicativo e confirme a versão e os cofres existentes.

O gerador abaixo prepara o manifesto de um futuro canal público HTTPS:

```powershell
.\.venv\Scripts\python.exe packaging\create_release_manifest.py `
  dist\KeyCiphra-Setup-0.9.0.exe `
  --version 0.9.0 `
  --base-url https://downloads.exemplo/keyciphra/v0.9.0/ `
  --output dist\release-manifest.json
```

O repositório GitHub atual é privado. O aplicativo não inclui token do GitHub e
não consulta releases privadas, porque um token embutido poderia ser extraído
do executável. A verificação automática só deve ser habilitada depois que
existir um manifesto público HTTPS cuja origem seja controlada e cuja versão
aponte para um instalador Authenticode assinado.
