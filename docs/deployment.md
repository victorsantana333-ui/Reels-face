# Publicação gratuita: Streamlit Community Cloud + Supabase

O caminho principal agora é **Streamlit Community Cloud**, com os dados no **Supabase Free**. Não contrate o Render, adicione cartão ou selecione plano pago para seguir este guia. A sessão não criou serviços nem ativou cobrança.

A documentação oficial do Community Cloud informa hospedagem gratuita integrada ao GitHub. Ela foi consultada no repositório oficial `streamlit/docs`, em `content/deploy/community-cloud`, em 28/10/2026. A contratação/aceitação dos termos e o login pertencem ao titular; esta sessão não tem acesso à sua conta Streamlit ou às credenciais reais do banco.

## 1. Acessar a hospedagem

Entre em https://share.streamlit.io/ usando **Continue with GitHub**. Autorize o acesso ao repositório. Se seu repositório for privado, pode ser necessário conceder acesso adicional a ele. A hospedagem pode solicitar confirmação do e-mail.

Escolha **Create app / New app → Deploy an app from GitHub** e preencha:

| Campo | Valor |
|---|---|
| Repository | `victorsantana333-ui/Reels-face` |
| Branch | `main` |
| Main file path | `streamlit_app.py` |
| Python | `3.12` em Advanced settings |

O arquivo de entrada é `streamlit_app.py`, **não** `app/main.py`. A nova interface reutiliza as mesmas operações de backend da interface original e já inclui projetos, contexto, preferências, planejamento de lotes, fila, calendário e histórico. A aplicação FastAPI original continua disponível para desenvolvimento ou outra hospedagem.

## 2. Configurar o banco e a chave com segurança

No Supabase, troque qualquer senha anteriormente compartilhada. Em **Connect → Direct → Session pooler → URI**, copie a conexão. Ela deve usar a porta `5432`, o usuário do seu projeto e o host exibido pelo Supabase. Preencha a nova senha; caracteres especiais na senha devem ser codificados como parte da URL.

Em **Advanced settings → Secrets** do Community Cloud, preencha o formato abaixo com seus dados **somente no painel seguro**, não no chat e não no GitHub:

```toml
REELS_ACCESS_TOKEN = "UMA_NOVA_CHAVE_LONGA_E_ALEATORIA_PARA_ENTRAR_NO_APP"
DATABASE_URL = "postgresql://postgres.PROJECT_REF:NEW_PASSWORD_ENCODED@POOLER_HOST:5432/postgres?sslmode=verify-full&sslrootcert=system"
```

`REELS_ACCESS_TOKEN` é a chave pessoal para entrar no Reels-face, com pelo menos 16 caracteres. **Não é a senha do banco**, não é chave de API do Supabase e não é token do Facebook. `DATABASE_URL` é a URI privada do Postgres, não o endereço público terminado em `.supabase.co` mostrado na página principal.

O driver exige TLS com verificação de certificado e nome do host. Se houver erro de certificado, confira o host e a CA indicada pelo Supabase; não mude para `sslmode=disable` ou `require`. Os arquivos de exemplo não contêm credenciais reais. `.streamlit/secrets.toml` é ignorado pelo Git.

Salve os Secrets e clique em **Deploy**. O serviço fornecerá o endereço terminado em `.streamlit.app`. Nenhum dado do Supabase foi acessado nesta sessão; a conexão real só poderá ser validada após configurar esses Secrets.

## 3. Conferir a instalação

1. Abra o endereço e informe sua chave pessoal. Sem autenticação, nenhum contexto ou projeto é mostrado.
2. O projeto inicial será Histórias de Passarinhos; importe seu contexto na Central de Inteligência.
3. Crie um projeto de teste e depois reinicie o app pelo painel. Verifique que o projeto permanece.
4. Configure um lote para conferir a fila e o calendário. Sem provedores reais, as tarefas serão marcadas como aguardando configuração, com motivo.

O app cria suas tabelas no schema separado `reels_face`, sem usar ou apagar tabelas existentes do schema `public`. Não expõe credenciais ao frontend e não depende de disco pago. A sessão de desenvolvimento usa PostgreSQL descartável para testes; isso não confirma a conexão com sua conta Supabase.

**Os dados antigos do SQLite não são migrados automaticamente.** O banco local permanece intacto. Importe seus contextos no novo banco; migração integral de histórico requer um procedimento específico antes de começar a usar as duas instalações em paralelo.

## Operação e limites

- Você pode usar o app durante sua sessão e preparar uma operação de vários dias. A fila de preparação roda no processo da hospedagem, independente dos cliques de cada etapa.
- O plano gratuito pode suspender o processo, limitar recursos ou pausar por inatividade; os dados continuam no Supabase. Trabalho não concluído fica pendente até o app voltar.
- A fila atual **prepara contexto e planejamento**, não gera imagens/vídeos. Muse AI, renderização, validação visual, OAuth e postagem na Meta continuam não implementados. Não há promessa de geração gratuita por provedores externos.
- Postar no futuro com o app desligado requer agendamento aceito pela Meta ou um scheduler externo, ainda não implementados. Hospedagem gratuita não garante execução nos horários de postagem.
- Respeite os limites dos planos gratuitos de hospedagem e banco. Não use mecanismos artificiais para contornar a suspensão.
- Mantenha apenas uma instância ativa do Reels-face por banco enquanto a recuperação de tarefas não possuir leases distribuídos. Se trocar de interface/hospedagem, encerre a anterior.
- Não são publicados bancos locais, arquivos `.env`, Secrets nem a senha compartilhada no chat.

## Referências oficiais

- https://docs.streamlit.io/deploy/streamlit-community-cloud
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
- https://github.com/streamlit/docs/tree/main/content/deploy/community-cloud
- https://supabase.com/docs/guides/database/connecting-to-postgres

A documentação atual do Hugging Face foi conferida e informa que criar Docker Spaces exige plano pago. Por isso essa alternativa não foi utilizada.

## Render (opcional, não recomendado para este caso)

`render.yaml` foi alterado para `plan: free`, sem disco ou serviço pago, usando `DATABASE_URL`. Ainda assim, o Render pode exigir verificação da conta ou cartão. Como você não quer adicionar cartão, siga o Community Cloud acima. Nada depende de contratação no Render.
