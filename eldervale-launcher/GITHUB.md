# Guia: publicar o Eldervale Launcher usando só o GitHub

Neste guia, `USUARIO` é o seu nome de usuário do GitHub e `eldervale` é o nome do repositório.
Troque pelos seus nomes em todos os comandos.

## Como as peças se encaixam

| O quê | Onde fica | Endereço |
| --- | --- | --- |
| Código do launcher | branch `main` do repositório | — |
| `version_manifest.json`, `news.json`, `launcher.json` | pasta `docs/` (servida pelo GitHub Pages) | `https://USUARIO.github.io/eldervale/` |
| Zips do jogo (um por versão e plataforma) | GitHub **Releases** (tag `v1.0.0`, `v1.1.0`…) | `https://github.com/USUARIO/eldervale/releases/download/v1.0.0/…` |
| Executáveis do launcher | GitHub **Releases** (tag `launcher-v1.0.0`…) | `https://github.com/USUARIO/eldervale/releases/download/launcher-v1.0.0/…` |

Regra de ouro: **arquivos pequenos (JSON) vão no repositório; arquivos grandes (zips, .exe) vão nas Releases.**
Nunca faça commit de zips do jogo no repositório.

Atenção: para o Pages grátis e para o launcher baixar sem login, o repositório precisa ser **público**.
Isso significa que qualquer pessoa com o link consegue baixar o jogo. Se o jogo for pago ou fechado,
não use este caminho (hospede em outro lugar, como Cloudflare R2 ou S3, e use o mesmo `publish.py`
com `--download-base-url` apontando para lá). Se o código-fonte do jogo for privado, crie um repositório
público separado só para a distribuição.

Limite importante: cada arquivo de uma Release pode ter no máximo 2 GiB
([fonte](https://fast.io/resources/github-release-file-size-limit.md)). Jogo maior que isso precisa de outra hospedagem.

---

## Parte 1 — Preparação (uma vez só)

1. Crie uma conta em https://github.com
2. Instale o **Git**: https://git-scm.com/downloads
3. (Opcional, mas facilita) instale o **GitHub CLI**: https://cli.github.com e rode `gh auth login`.
   Sem ele, tudo também dá para fazer pelo site.
4. Tenha o Python 3.10+ instalado.

## Parte 2 — Criar o repositório

1. Entre em https://github.com/new
2. Nome: `eldervale`. Marque **Public**. **Não** marque "Add a README".
3. Clique em **Create repository**.
4. Extraia o zip do projeto, abra um terminal dentro da pasta `eldervale-launcher` e rode:

```
git init -b main
git add .
git commit -m "Primeira versão do launcher"
git remote add origin https://github.com/USUARIO/eldervale.git
git push -u origin main
```

(O GitHub pode pedir login no navegador na primeira vez.)

## Parte 3 — Ligar o GitHub Pages (hospeda os JSON)

1. No repositório: **Settings → Pages**.
2. Em **Build and deployment → Source** escolha **Deploy from a branch**.
3. Em **Branch** escolha `main` e a pasta **`/docs`**. Clique em **Save**.
4. Espere 1–2 minutos. Seu site fica em `https://USUARIO.github.io/eldervale/`.
5. Teste: abra `https://USUARIO.github.io/eldervale/news.json` no navegador. Se aparecer o JSON, funcionou.

Depois disso, qualquer mudança nos arquivos de `docs/` leva alguns minutos para aparecer
(o Pages usa cache). Não é instantâneo.

## Parte 4 — Apontar o launcher para o seu GitHub

Abra `eldervale_launcher/config.py` e troque:

```python
BASE_URL = os.environ.get("ELDERVALE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
```

por:

```python
BASE_URL = os.environ.get("ELDERVALE_BASE_URL", "https://USUARIO.github.io/eldervale").rstrip("/")
```

Salve e envie:

```
git add .
git commit -m "BASE_URL do GitHub Pages"
git push
```

## Parte 5 — Liberar o GitHub Actions a escrever no repositório

O build automático do launcher cria Releases e atualiza o `docs/launcher.json`. Para isso:

**Settings → Actions → General → Workflow permissions → Read and write permissions → Save.**

## Parte 6 — Lançar o launcher (primeira vez)

O arquivo `.github/workflows/build-launcher.yml` gera o launcher para Windows, Linux e macOS sozinho
quando você cria uma tag que começa com `launcher-v`:

```
git tag launcher-v1.0.0
git push origin launcher-v1.0.0
```

1. Abra a aba **Actions** do repositório e acompanhe o job "Build do launcher" (leva uns 5–10 minutos).
2. Quando ficar verde, a aba **Releases** terá "Launcher 1.0.0" com 3 arquivos
   (`EldervaleLauncher-windows.exe`, `-linux`, `-macos`).
3. O próprio workflow atualiza `docs/launcher.json` com a versão, os links e os hashes SHA-256.
   Rode `git pull` no seu computador para trazer esse arquivo.
4. O número da versão vem da tag (`launcher-v1.0.0` → `1.0.0`). Você **não** precisa editar o `LAUNCHER_VERSION` na mão.

Link para divulgar para os jogadores (sempre baixa o launcher mais recente):

```
https://github.com/USUARIO/eldervale/releases/latest
```

ou direto no arquivo do Windows:

```
https://github.com/USUARIO/eldervale/releases/latest/download/EldervaleLauncher-windows.exe
```

Isso funciona porque as Releases do **jogo** são criadas com "latest" desligado (Parte 7).

## Parte 7 — Publicar uma versão do jogo (ex.: 1.0.0)

Faça sempre nesta ordem: **zip → Release → manifesto**.

**1. Exporte o jogo** da sua engine para uma pasta, por exemplo `build\win`, com `Eldervale.exe` dentro.

**2. Gere o zip e atualize o manifesto** (tudo em uma linha só):

```
python tools/publish.py --version 1.0.0 --platform windows --build-dir build/win --exe Eldervale.exe --out docs --zip-dir release_files --download-base-url https://github.com/USUARIO/eldervale/releases/download/v1.0.0 --changelog "- Lançamento inicial"
```

Isso cria `release_files/eldervale-1.0.0-windows.zip` (não vai para o Git) e adiciona a versão em
`docs/version_manifest.json`.

**3. Crie a Release com o zip** (o zip tem que estar no ar antes do manifesto).

Pelo site:
- **Releases → Draft a new release**
- Em **Choose a tag** digite `v1.0.0` e clique em **Create new tag**
- Título: `Eldervale 1.0.0`
- Arraste o `.zip` de `release_files/` para a área de anexos
- **Desmarque** "Set as the latest release"
- **Publish release**

Ou pelo terminal (com o GitHub CLI):

```
gh release create v1.0.0 release_files/eldervale-1.0.0-windows.zip --title "Eldervale 1.0.0" --notes "Lançamento inicial" --latest=false
```

A tag da Release (`v1.0.0`) tem que ser **igual** à usada em `--download-base-url`.

**3b. Teste o link:** cole no navegador
`https://github.com/USUARIO/eldervale/releases/download/v1.0.0/eldervale-1.0.0-windows.zip`.
Se o download começar, está certo.

**4. Publique o manifesto:**

```
git add docs/version_manifest.json
git commit -m "Jogo 1.0.0"
git push
```

Em alguns minutos o launcher passa a mostrar a versão e o botão "BAIXAR E JOGAR".

Se o jogo tiver mais de uma plataforma, rode o passo 2 para cada uma (`--platform windows`,
`--platform linux`, `--platform macos`) com a **mesma** `--version`, e anexe todos os zips na mesma Release.

## Parte 8 — Lançar uma atualização do jogo (ex.: 1.1.0)

Repita a Parte 7 trocando só o número e as notas:

```
python tools/publish.py --version 1.1.0 --platform windows --build-dir build/win --exe Eldervale.exe --out docs --zip-dir release_files --download-base-url https://github.com/USUARIO/eldervale/releases/download/v1.1.0 --changelog "- Nova região: Vale das Brumas\n- Correções de bugs"
gh release create v1.1.0 release_files/eldervale-1.1.0-windows.zip --title "Eldervale 1.1.0" --notes "Nova região" --latest=false
git add docs/version_manifest.json
git commit -m "Jogo 1.1.0"
git push
```

O que acontece para os jogadores:
- Ao abrir o launcher, aparece a janela **"Eldervale 1.1.0 chegou!"** com as notas e o botão **Atualizar agora**.
- A versão 1.0.0 continua no seletor para quem quiser voltar.
- As notas ficam guardadas na aba **Notas de atualização**.

Nunca reaproveite um número de versão com arquivo diferente. Para corrigir um problema, publique `1.1.1`.

## Parte 9 — Atualizar o launcher (ex.: 1.0.1)

1. Mude o código do launcher e envie: `git add .`, `git commit -m "..."`, `git push`.
2. Crie a tag:

```
git tag launcher-v1.0.1
git push origin launcher-v1.0.1
```

3. O Actions builda os 3 sistemas, cria a Release `launcher-v1.0.1` e atualiza o `docs/launcher.json`.
4. Rode `git pull` para trazer o `launcher.json` novo antes do próximo `git push`.
5. Quem tem o launcher 1.0.0 recebe a atualização na próxima vez que abrir (depois que o cache do Pages
   atualizar): ele baixa, confere o hash, troca o arquivo e reinicia sozinho.

## Parte 10 — Outras tarefas

- **Notícias:** edite `docs/news.json`, depois `git add`, `git commit`, `git push`.
- **Versão beta:** use `--type beta` no `publish.py`. Só aparece para quem ligar "Mostrar versões beta" nas configurações e não vira a "última".
- **Esconder uma versão:** apague a entrada dela em `docs/version_manifest.json` e faça push. Quem já instalou continua jogando. Se quiser, apague também a Release.
- **Voltar o "★ Última versão" para outra versão:** edite `"latest": {"release": "1.0.0"}` no manifesto.
- **Testar antes de publicar de verdade:** rode `python -m http.server 8000` dentro da pasta `docs` e abra o launcher com a variável `ELDERVALE_BASE_URL=http://127.0.0.1:8000`.

## Problemas comuns

| Sintoma | O que verificar |
| --- | --- |
| Launcher abre e diz "SEM VERSÃO" | `BASE_URL` errado, Pages ainda não ativado, ou o JSON demorou para atualizar. Abra `https://USUARIO.github.io/eldervale/version_manifest.json` no navegador. |
| Erro 404 ao baixar o jogo | A tag da Release não bate com a do `--download-base-url`, ou a Release ainda está como rascunho. |
| "Arquivo corrompido (hash)" | O zip da Release não é o mesmo que o `publish.py` gerou. Gere de novo e substitua. |
| Windows mostra "O Windows protegeu seu PC" | Normal: o `.exe` não tem assinatura digital paga. Clique em "Mais informações → Executar assim mesmo". |
| macOS bloqueia o launcher | O binário não é assinado nem notarizado pela Apple. Hoje o suporte a macOS é o menos polido. |
| Linux: "Permissão negada" | `chmod +x EldervaleLauncher-linux` |
| Actions falha ao dar `push` ou criar Release | Parte 5 (permissões de escrita) não foi feita. |
| Mudei um JSON e nada mudou | Espere alguns minutos pelo cache do Pages. |

## Resumo rápido

**Novo jogo/versão:** `publish.py` → criar Release com o zip → `git push` do manifesto.
**Novo launcher:** `git push` do código → `git tag launcher-vX.Y.Z` → `git push origin launcher-vX.Y.Z` → `git pull`.
**Notícia:** editar `docs/news.json` → `git push`.

Obs.: o workflow do Actions foi escrito mas ainda não foi executado de ponta a ponta. Se algum passo falhar
na primeira vez, abra a aba Actions, copie o erro do passo que ficou vermelho e ajuste.
