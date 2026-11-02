# Eldervale Launcher

> Para hospedar tudo no GitHub (Pages + Releases + build automático), siga o guia **GITHUB.md**.

Launcher de um único jogo (Eldervale), inspirado no launcher oficial do Minecraft:

- o jogador baixa o launcher e clica em **JOGAR**;
- o launcher baixa e instala o jogo sozinho;
- quando você publica uma atualização, o launcher mostra as notas da versão;
- o jogador pode escolher **qualquer versão antiga** no seletor ao lado do botão;
- o próprio launcher se atualiza sozinho (quando empacotado em `.exe`).

## Como funciona (igual ao Minecraft)

| Minecraft                          | Eldervale                                   |
| ---------------------------------- | ------------------------------------------- |
| `version_manifest.json`            | `docs/version_manifest.json`              |
| JSON de cada versão (url + sha1)   | cada entrada do manifesto (url + sha256)    |
| Pasta `.minecraft/versions/<id>`   | `~/.eldervale/versions/<id>` (`%APPDATA%\.eldervale` no Windows) |
| Perfil "Última versão"             | opção "★ Última versão" do seletor          |
| Notícias do launcher               | `docs/news.json`                          |

O launcher só **lê arquivos estáticos** por HTTPS. Você não precisa de servidor com programação:
qualquer hospedagem de arquivos serve (GitHub Pages, Cloudflare R2, S3, Netlify, VPS com nginx, etc.).

## Estrutura do projeto

```
launcher.py                    ponto de entrada
eldervale_launcher/
    config.py                  URLs, versão do launcher, pastas, preferências
    versions.py                manifesto, download, instalação, execução
    selfupdate.py              auto-atualização do launcher
    ui.py                      interface (customtkinter)
assets/cover.jpg               capa do jogo (fundo da tela principal)
tools/publish.py               publica uma build do jogo e atualiza o manifesto
docs/                        arquivos que vão para a sua hospedagem
    version_manifest.json      (gerado pelo publish.py)
    downloads/                 (gerado pelo publish.py)
    launcher.json              versão atual do launcher
    news.json                  notícias
```

## 1) Configuração inicial (uma vez)

1. Instale as dependências: `pip install -r requirements.txt`
2. Escolha onde vai hospedar os arquivos e abra `eldervale_launcher/config.py`.
   Troque `BASE_URL` pelo seu endereço, por exemplo `https://meusite.com/eldervale`.
3. Teste rodando `python launcher.py`.

## 2) Lançar o launcher pela primeira vez

Gere o executável **na plataforma de destino** (o `.exe` é gerado no Windows, o de Linux no Linux, etc.):

```
pyinstaller --noconfirm --onefile --windowed --name EldervaleLauncher ^
  --collect-all customtkinter --add-data "assets;assets" launcher.py
```

No Linux/macOS troque `;` por `:` em `--add-data "assets:assets"` e `^` por `\`.
O resultado fica em `dist/EldervaleLauncher.exe`. Esse é o arquivo que o jogador baixa (do seu site, itch.io, etc.).

## 3) Publicar uma versão do JOGO

Exporte o jogo para uma pasta (por exemplo `build/win`) e rode:

```
python tools/publish.py --version 1.0.0 --platform windows ^
  --build-dir build/win --exe Eldervale.exe ^
  --base-url https://meusite.com/eldervale ^
  --changelog "- Lançamento inicial"
```

O que o comando faz: cria `docs/downloads/eldervale-1.0.0-windows.zip`, calcula o SHA-256 e
adiciona a versão em `docs/version_manifest.json` (marcando-a como a última).

Depois **envie a pasta `docs/` inteira** para a hospedagem (o endereço precisa ficar igual ao `BASE_URL`).

Pronto: quem abrir o launcher já vê a versão e baixa com um clique.

### Lançar uma atualização (ex.: 1.1.0)

Rode o mesmo comando com `--version 1.1.0` e novas notas em `--changelog`, e reenvie a pasta `docs/`.

- Quem abrir o launcher vê a janela **"Eldervale 1.1.0 chegou!"** com as notas e o botão **Atualizar agora**.
- As notas também ficam na aba **Notas de atualização**.
- As versões antigas continuam no manifesto: o jogador escolhe qualquer uma no seletor.

Para várias plataformas, rode o `publish.py` uma vez por plataforma com a **mesma** `--version`
(`--platform windows`, `--platform linux`, `--platform macos`). Todas entram na mesma versão.

### Outras opções do publish.py

- `--type beta` (ou `snapshot`): versão de teste. Só aparece para quem ativar "Mostrar versões beta" nas configurações, e não vira a "última".
- `--no-latest`: publica sem marcar como a última versão (útil para republicar uma versão antiga).
- `--changelog @notas.txt`: lê as notas de um arquivo.
- Para **remover** uma versão, apague a entrada em `version_manifest.json` (e o `.zip`). Quem já instalou continua conseguindo jogar.

### Regras importantes

- O executável do jogo tem que estar no zip no caminho informado em `--exe`.
- O jogo deve gravar os saves na pasta indicada pela variável de ambiente `ELDERVALE_DATA_DIR`.
  Assim os saves são compartilhados entre todas as versões instaladas. O launcher também define `ELDERVALE_VERSION`.
- Nunca reutilize um número de versão com conteúdo diferente: publique sempre um número novo.

## 4) Atualizar o LAUNCHER

O launcher verifica `launcher.json` ao abrir. Se a versão lá for maior que a do programa, ele baixa o novo
executável, confere o SHA-256, troca o arquivo e reinicia sozinho.

1. Em `eldervale_launcher/config.py`, aumente `LAUNCHER_VERSION` (ex.: `"1.0.1"`).
2. Gere o novo executável com o PyInstaller (passo 2).
3. Calcule o hash: `certutil -hashfile dist\EldervaleLauncher.exe SHA256` (Windows) ou `sha256sum EldervaleLauncher` (Linux/macOS).
4. Envie o executável para `docs/downloads/`.
5. Edite `docs/launcher.json`: coloque a nova `version`, o `changelog`, e a `url` e o `sha256` de cada plataforma.
6. Envie o `launcher.json` por último, depois que o executável já estiver no ar.

Observações:
- A auto-atualização só funciona no executável (`.exe`); rodando com `python launcher.py` ele só avisa que há versão nova.
- Se o jogador estiver sem internet, o launcher continua funcionando com as versões já instaladas.
- Para o launcher mostrar aviso de atualização, o número em `launcher.json` precisa ser **maior** que o do programa instalado.

## 5) Notícias

Edite `docs/news.json` (lista com `title`, `date`, `text` e, opcionalmente, `url`) e reenvie. Aparece na aba **Novidades**.

## Checklist rápido de lançamento

1. `config.py`: `BASE_URL` correto.
2. Build do launcher com PyInstaller e divulgação do `.exe`.
3. `publish.py` para cada plataforma do jogo.
4. Enviar a pasta `docs/` para a hospedagem.
5. Abrir o launcher, instalar e jogar para conferir.
