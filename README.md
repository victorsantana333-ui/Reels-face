# Reels-face

Central pessoal de operações criativas para Facebook Reels. Primeira versão funcional: projetos, memória criativa, importação de contexto, planejamento de lotes, fila persistente, calendário e histórico. Interface em português, responsiva e sem serviços de terceiros no frontend.

**Geração de imagens/vídeos, validação visual, publicação na Meta, OAuth e agente de desktop ainda não estão implementados.** O sistema não simula esses resultados nem incorre em custos externos.

## Executar

Requisitos: Python 3.12+, SQLite (incluído no Python). FFmpeg está disponível no ambiente, mas ainda não é usado. Nenhum banco ou serviço adicional é necessário.

```bash
cd /workspace/Reels-face
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Abra a porta 8000 no navegador do seu ambiente de desenvolvimento. O banco é criado automaticamente em `data/reels.sqlite3`, ignorado pelo Git. O único projeto inicial é **Histórias de Passarinhos**, com 9:16 e 45–55 segundos. Seu storyboard e personagens precisam ser importados; não inventamos esse contexto. Outros projetos começam com configurações independentes, editáveis.

Execute apenas **um processo Uvicorn**, sem `--workers`: a fila local pertence ao processo do servidor e continua sem uma aba do navegador aberta. O servidor precisa permanecer ligado. Reinícios preservam os dados; tarefas de preparação são retomadas. Não há scheduler de publicação externa nesta versão.

## Primeiro uso

1. Entre em Projetos e abra Histórias de Passarinhos, ou crie um projeto.
2. Importe TXT, Markdown ou JSON UTF-8 (até 2 MB) na Central de Inteligência. O texto original é preservado, não interpretado como autorização ou código.
3. Registre preferências por projeto ou por tarefa. Preferências globais exigem confirmação explícita. Conteúdo idêntico é deduplicado dentro do projeto.
4. Configure proporção, duração, fuso IANA, legendas, narração e limite financeiro em Editar projeto. Essas preferências são armazenadas; processamento de mídia ainda está pendente.
5. Planeje um lote informando quantidade, data, horários e dias da semana. Por exemplo, 150 tarefas em cinco horários diários produzem um calendário de 30 dias. Horários passados do dia atual são pulados; a distribuição continua nos próximos dias selecionados.
6. A fila prepara um snapshot do contexto do projeto para cada tarefa. Sem provedor, a tarefa fica **aguardando configuração**, com motivo visível. Não fica falsamente aprovada ou publicada.
7. Consulte calendário, tarefas e histórico. Pause, retome, cancele ou reprepare tarefas bloqueadas. Repreparar lê o contexto atual e substitui o snapshot anterior; não dispara geração.

Cada horário corresponde a uma tarefa por dia selecionado. Os dados ficam em UTC no banco; calendário e fila exibem o fuso do projeto. A aba mensal abre no mês atual; use o seletor para consultar outros meses. O limite operacional de 10.000 tarefas por solicitação protege o processo local; operações maiores devem ser divididas. Não há limite artificial de projetos.

Duplicar copia o contexto e preferências permanentes para registros independentes, sem copiar tarefas. Arquivar pausa os lotes ativos; restaurar o projeto não retoma automaticamente os lotes. Excluir exige o nome exato, oculta o projeto e cancela suas tarefas pendentes, preservando dados e histórico no banco. A restauração de projetos excluídos ainda não tem interface.

## Segurança e configuração

Consulte `.env.example`. As variáveis são lidas do processo; o arquivo `.env` **não é carregado automaticamente**.

- `REELS_DATA_DIR`: diretório persistente de dados; padrão `./data` relativo à raiz do projeto.
- `REELS_ACCESS_TOKEN`: chave pessoal para autenticar chamadas de API com Bearer. Se configurada, a interface solicita essa chave e a mantém em `sessionStorage` até encerrar a sessão. Não é token do Facebook.
- Sem chave, o aplicativo aceita apenas hosts locais. Antes de acesso remoto, configure uma chave forte, proxy reverso com HTTPS e limites de requisição/upload. Para bind remoto use a opção `--host` do Uvicorn explicitamente. Não considere esta versão uma implantação pública pronta.
- Acesso individual; autenticação multiusuário, OAuth de provedores e cofre criptografado para credenciais externas são trabalhos futuros. Nenhuma senha ou token de provedor é solicitado ou armazenado nesta versão.
- Sem CORS aberto; mutações de origem diferente são bloqueadas. CSP, escape de HTML, consultas parametrizadas e validação de importações protegem o fluxo básico. Conteúdo importado não é executado e deverá continuar isolado de ferramentas e credenciais em futuros adaptadores de IA.
- Faça backups do SQLite com a API de backup, pois o banco usa WAL. Não copie somente o arquivo principal com o servidor escrevendo.

## Validação

```bash
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m unittest discover -s tests -v
# Requer Chromium em /usr/bin/chromium ou BROWSER_PATH.
.venv/bin/python tests/browser_smoke.py
```

Os testes usam banco temporário e não contatam provedores. O smoke de navegador inicia e encerra seu próprio servidor, testa o fluxo real e salva capturas em `/tmp/reels-face-dashboard.png` e `/tmp/reels-face-mobile.png`. Redes locais e subprocessos precisam ser permitidos pelo executor.

## Estrutura

- `app/main.py`: FastAPI, validação, SQLite, API e consumidor da fila de preparação.
- `app/providers.py`: contratos de geração/publicação e catálogo honesto de integrações.
- `app/static/`: interface HTML/CSS/JavaScript sem build ou CDN.
- `tests/`: testes de regras, persistência, isolamento, fila e navegador.
- `docs/architecture.md`: decisões, limites e evolução.
- `docs/integrations.md`: dependências externas e investigação pendente.

Esta versão atende à operação local de organização e planejamento. Contratos de provedores não equivalem a integrações implementadas. Idempotência local de criação de lote não garante idempotência de publicação em plataformas externas.

## Publicar o aplicativo na internet

A configuração de hospedagem está em `render.yaml`. Consulte [o guia de publicação](docs/deployment.md). O Render oferece HTTPS e o blueprint inclui disco persistente e uma chave pessoal de acesso gerada no servidor. **O plano escolhido e o disco são pagos; confira o preço na sua conta antes de ativar.** A publicação do ambiente Codex é independente da hospedagem do aplicativo.
