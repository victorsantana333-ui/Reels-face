# Arquitetura e evolução

## Primeira versão

Python 3.12 e FastAPI estão disponíveis no ambiente. SQLite oferece transações, persistência e fila suficiente para um operador em um processo, sem provisionar Redis ou Postgres antes de haver provedores reais. A interface usa JavaScript nativo e CSS local, sem build, CDN ou dependências de frontend. FFmpeg está instalado e pode apoiar a futura renderização; ainda não há renderer.

A divisão atual separa domínio/API, contratos externos e interface. Não foi implementada a automação completa; foi entregue um corte funcional de organização criativa e preparação de lotes.

## Dados e isolamento

Projetos possuem configurações próprias. Contextos e preferências fazem referência ao ID de projeto. Uma preferência global tem escopo explícito e projeto nulo; uma correção pontual exige uma tarefa pertencente ao projeto. Duplicação copia contexto e preferências permanentes em novos registros, sem compartilhar IDs. Soft delete preserva dados e cancela tarefas pendentes. O marcador de inicialização evita recriar o projeto inicial após sua exclusão.

Cada tarefa preparada captura configuração, arquivos de contexto e preferências aplicáveis. Contexto é dado não confiável: não pode conceder novas permissões nem substituir políticas de ferramentas em futuras integrações. A conta pessoal pode consultar todos os seus projetos; isso é isolamento criativo, não multitenancy.

## Fila atual

O consumidor local roda numa thread no processo da aplicação. Uma transação `BEGIN IMMEDIATE` seleciona tarefa de lote ativo e projeto não arquivado, monta seu snapshot e grava o impedimento de geração. Falha numa tarefa por ausência de contexto não impede a preparação das outras. Pausa/retomada/cancelamento são transacionais. O estado `preparing` é reservado para recuperação; atualmente a preparação inteira é atômica, sem chamadas externas ou estágio parcialmente persistido.

Uma chave de solicitação única e fingerprint impedem duplicação de lotes em reenvios idênticos. Mesma chave com outros parâmetros é rejeitada. Uma nova chave cria intencionalmente outro lote. Não há deduplicação de vídeos porque não há geração ou publicação. Custos e publicações são zero por ausência de chamadas externas, não por telemetria de um provedor.

Horários são convertidos de IANA para UTC; horários inexistentes por mudança de fuso são rejeitados, horários ambíguos usam a primeira ocorrência (`fold=0`). A agenda é local e representa intenção, não confirmação da Meta. Datas de início no passado são rejeitadas e horários de hoje já passados são pulados.

## Próximas etapas

1. Identificar o serviço Muse AI exato; obter documentação e formato real de exportação. Mapear importações estruturadas sem perder o original.
2. Implementar o primeiro provedor real com estimativa, reserva financeira atômica, teto por lote/projeto, armazenamento de mídia e validação. Se o custo for desconhecido, manter a execução paga bloqueada até um mecanismo de limite verificável.
3. Separar workers de geração/renderização e scheduler com leases, heartbeat, tentativas limitadas por etapa e recuperação. Migrar para Postgres e uma fila apropriada ao volume/concorrência antes de múltiplos servidores. Implementar validações reais via FFprobe/FFmpeg e modelo visual; não inferir qualidade só por receber um arquivo.
4. Implementar OAuth Meta no servidor, estado anti-CSRF, validação de callback, tokens criptografados em repouso, revogação e autorização efetiva por página. Nenhum token no frontend.
5. Construir publicação com outbox persistente, identidade por conteúdo/destino, IDs remotos e reconciliação. Timeout após envio exige reconciliação antes de repetir: não prometer exactly-once se a API não garantir idempotência.
6. Implementar agente desktop separado e explicitamente pareado, com allowlists, autorizações por ação, expiração de sessão, interrupção, limites e auditoria. Não reutilizar esse mecanismo para contornar restrições externas.

Hospedagem permanente, backups, mídia, custos reais, autenticação multiusuário, observabilidade e publicação precisam de validação específica antes de operação automática em produção.

## Evolução: PostgreSQL e hospedagem gratuita

`app/database.py` agora fornece SQLite para desenvolvimento local e PostgreSQL/Supabase quando `DATABASE_URL` está configurada. O schema `reels_face` é separado do `public`, com acesso público revogado. As consultas continuam parametrizadas; a camada adapta somente o SQL fixo da aplicação e explicita colunas de inserção. O PostgreSQL usa sequência para ordenar registros, pool de até quatro conexões, transações e advisory lock nas transições da fila. A conexão remota exige TLS `verify-full` com raízes do sistema ou CA explicitamente configurada. SQLite permanece inalterado e não é migrado implicitamente.

`streamlit_app.py` adiciona uma interface para Community Cloud. Usa as operações de domínio já registradas pela aplicação FastAPI, sem abrir servidor HTTP interno ou usar cliente de testes em produção. A autenticação por chave pessoal é feita antes de construir a conexão e consultar dados. Cada sessão guarda a autenticação, enquanto o pool e o consumidor são compartilhados no processo por cache de recurso. Uma configuração alterada gera outro fingerprint; não há credencial na chave pública do cache.

Na nuvem, ausência de DATABASE_URL bloqueia o workspace em vez de criar silenciosamente um banco efêmero. `REELS_ALLOW_LOCAL_UI=1` é uma opção explícita apenas para desenvolvimento. Os dados de conexão permanecem nos Secrets da hospedagem. O usuário pode iniciar seu trabalho enquanto usa a aplicação, mas suspensão da hospedagem encerra threads; não há garantia de automação 24h, geração real ou postagem agendada.

A API/web original continua funcional. Os mesmos testes de contratos são executados contra ambos os bancos, além de testes da interface Streamlit. A conexão real com Supabase e o deploy no Community Cloud exigem Secrets e autorização da conta; são verificações separadas dos testes locais.
