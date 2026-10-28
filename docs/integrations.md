# Integrações: situação verificável

## Muse AI

O usuário identificou o nome Muse AI, mas ainda não informou URL do serviço ou documentação. Existem serviços com nomes semelhantes. Não foi possível identificar com segurança uma API oficial para conversas ou geração. Nenhum endpoint foi criado por suposição.

Funciona agora: importação local de TXT, Markdown e JSON UTF-8, e texto manual. O conteúdo original é mantido por projeto e deduplicado por SHA-256. JSON é validado como JSON, mas ainda não há parser específico de exportação do Muse. PDF, imagens de referência e sincronização de chats não estão disponíveis.

Para integrar: fornecer URL exata do serviço e documentação de API/exportação, confirmar autorização e capacidades de geração, custos, limites e consulta de tarefas. Links de conversa não dão acesso automático ao conteúdo. Credenciais só serão configuradas no servidor após escolher o adaptador; não devem ser enviadas no chat.

## Facebook / Meta

Referências oficiais para a implementação:

- https://developers.facebook.com/docs/video-api/guides/reels-publishing/
- https://developers.facebook.com/docs/pages-api/
- https://developers.facebook.com/docs/facebook-login/
- https://developers.facebook.com/docs/permissions/

A tentativa de consultar a documentação de Reels em 28/10/2026 foi bloqueada pelo proxy do ambiente (CONNECT 403). Portanto requisitos atuais, versões da Graph API, permissões, limites, formatos, OAuth e disponibilidade de agendamento **não foram validados nesta sessão**. Os links são referências para investigação, não evidência de integração concluída. Nenhum endpoint ou versão foi inventado, e não foram feitos pedidos para alterar a rede do usuário.

A implementação futura exige um aplicativo Meta, callback HTTPS, OAuth no backend e verificação das permissões concedidas para cada página. É necessário determinar revisão do app, elegibilidade, Page Access Tokens, expiração/revogação e limites atuais conforme documentação e respostas reais. Login da conta pessoal não prova autorização de publicação em todas as páginas.

Nesta versão o catálogo de integrações é estático e descreve capacidades ausentes. A lista de páginas está vazia porque não há OAuth ou adaptador. Não existe botão falso para conectar, publicar ou agendar na Meta.

## Desktop

Não há agente, pareamento, acesso ao desktop nem comandos remotos implementados. O módulo mostra explicitamente esse estado. A arquitetura futura é descrita em `architecture.md`.
