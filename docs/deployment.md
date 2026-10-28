# Colocar o aplicativo online pelo Render

A configuração `render.yaml` cria um serviço Python com HTTPS gerenciado, disco persistente de 1 GB, health check e chave de acesso gerada no servidor. Não precisa instalar nada no seu computador.

**O plano Starter e o disco são pagos. Confira os preços exibidos pelo Render antes de confirmar.** Não use disco efêmero para dados importantes: os projetos e contextos ficam em SQLite e precisam sobreviver a reinícios e deploys. Não foram contratados serviços nem efetuadas cobranças por este código.

## Ativação na sua conta

1. Acesse https://dashboard.render.com/ e entre usando GitHub.
2. Autorize o Render a acessar `victorsantana333-ui/Reels-face`.
3. Escolha **New → Blueprint**, selecione o repositório e a branch `main`. O Render lerá `render.yaml`.
4. Confira o plano, o disco e o custo. Confirme a criação do serviço somente se estiver de acordo.
5. Aguarde o build e o estado **Live**. O próprio Render informará o endereço HTTPS do aplicativo.
6. Na área **Environment** do serviço, consulte a chave gerada `REELS_ACCESS_TOKEN`. Digite-a na tela de acesso do Reels-face. Não a envie por chat, não a coloque no GitHub nem na URL.

O login pelo GitHub no Muse AI não conecta uma conta de hospedagem ao Codex. A primeira autorização da conta Render e a contratação do serviço exigem ação do titular. Esta sessão não possui credenciais ou ferramenta de deploy para Render.

## Conferência após ativar

- A página inicial deve solicitar sua chave. APIs de dados sem autenticação devem retornar 401.
- `/api/health` deve retornar `status: ok`, `worker_enabled: true` e `worker_error: null`.
- Crie um projeto de teste, reinicie o serviço e confirme que ele continua disponível.
- O disco é montado em `/var/data`; o banco fica em `/var/data/reels-face/reels.sqlite3`.
- O banco vazio de produção cria apenas Histórias de Passarinhos. Seus contextos locais não são enviados automaticamente ao GitHub ou Render; importe os arquivos na nova instalação.
- Mantenha uma única instância e um único worker enquanto usar SQLite e a fila local. Faça backups regulares do banco pela API de backup SQLite.

## Limites da versão publicada

Estar online não habilita geração de mídia, Muse AI, OAuth Meta, publicação de Reels ou agente desktop. Esses recursos ainda não foram implementados. O aplicativo publicado oferece projetos, contexto, preferências, planejamento de lotes, calendário e histórico para uso pessoal. Não é uma plataforma multiusuário.

O script de início confia nos cabeçalhos do proxy para reconhecer HTTPS. Use-o somente atrás do proxy da hospedagem. Não execute a mesma configuração numa máquina diretamente exposta à internet.
