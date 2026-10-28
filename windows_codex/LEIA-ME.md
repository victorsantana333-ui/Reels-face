# Codex local + Chrome já conectado

Este pacote configura o **Codex CLI oficial** com o **Playwright MCP oficial** em modo extensão. O modelo pode observar a página e decidir as ações a partir da sua ordem; não exige tarefas JSON nem seletores escritos por você. Não há um modelo rodando na GTX 1050 Ti.

## Instalação no Windows

1. Instale [Node.js LTS 22 ou superior](https://nodejs.org/). Use uma pasta extraída normal para este pacote, não execute dentro do ZIP.
2. No mesmo perfil Chrome onde usa o Muse, instale a [Playwright Extension oficial](https://chromewebstore.google.com/detail/playwright-extension/mmlmfjhmonkocbjadbfplnigmagldckm). A extensão anterior Reels-face não faz esta conexão e pode ser desativada.
3. Execute **1-configurar.cmd**. Ele instala Codex via npm se ainda não existir e adiciona o servidor `reels-face-browser` à configuração do Codex do seu usuário. Outros servidores não são removidos. Uma configuração anterior com esse mesmo nome será substituída. Playwright é fixado na versão 0.0.83.
4. Execute **2-iniciar.cmd**. No primeiro acesso selecione **Sign in with ChatGPT** e entre com sua conta Pro. Complete a configuração do sandbox Windows se o Codex solicitar. Não selecione cobrança por API nem cole senhas neste chat.
5. Quando o Playwright abrir sua tela de conexão, escolha a **aba do Muse que já está aberta**. Pode surgir uma aba de autorização da extensão; a operação usa a aba escolhida, com o login existente.
6. O primeiro pedido só observa a página. Quando o Codex descrever corretamente a aba, escreva sua ordem **na janela do Codex local**.

Exemplo de ordem depois do teste:

> Na aba do Muse conectada, use o contexto da minha série de passarinhos para preparar um vídeo de teste. Acompanhe a geração, baixe o resultado nesta pasta e registre o progresso. Não publique ainda. Se faltar alguma referência, pergunte antes de gerar.

As referências desta conversa não são transferidas automaticamente. Forneça ao agente local o contexto necessário, por exemplo copiando inteligencia-videos.json para a pasta operacao e pedindo que o leia. Não copie senhas ou arquivos de autenticação.

## Parar e retomar

Mantenha Chrome e a janela do Codex abertos durante o trabalho. Ctrl+C interrompe a execução local; use a página da extensão Playwright para desconectar o cliente do navegador. Isso não desfaz ações já enviadas ao Muse/Facebook. O computador não pode entrar em suspensão durante a operação. Para retomar, abra Codex na pasta operacao e use `codex resume`; confira o estado no serviço antes de repetir gerações ou publicações.

## O que foi e não foi validado

A documentação oficial confirma login ChatGPT no Codex e conexão Playwright às abas existentes. O pacote prepara essa conexão, mas não conecta este chat ao seu Windows, não instala um serviço permanente e não integra um botão remoto no Reels-face. A instalação Windows, o consumo do plano e a geração/download no Muse precisam ser verificados no computador do usuário. Não há garantia de compatibilidade do Muse ou de geração ilimitada. Créditos/limites do Muse continuam independentes dos limites do Codex Pro.

O conector permite ações reais no navegador. O conteúdo observado é enviado ao modelo no contexto da tarefa. As instruções de operação limitam o escopo solicitado, mas não constituem isolamento técnico do navegador. Não é preciso conceder controle irrestrito do PC, expor portas de depuração ou compartilhar tokens. Não foi habilitado bypass de sandbox ou de aprovações.

## Fontes oficiais

- [Codex: instalação e login com ChatGPT](https://github.com/openai/codex#using-codex-with-your-chatgpt-plan)
- [Playwright MCP](https://github.com/microsoft/playwright-mcp)
- [Extensão Playwright: abas existentes e seleção de aba](https://github.com/microsoft/playwright/tree/main/packages/extension#readme)
