# Reels-face — extensão para a aba atual

1. Baixe o ZIP da extensão em Automação do Desktop e extraia.
2. No Chrome abra `chrome://extensions`, ative **Modo do desenvolvedor**, clique **Carregar sem compactação** e selecione a pasta que contém `manifest.json`.
3. Na aba já conectada ao Muse, clique no ícone de extensões → Reels-face → **Usar esta aba**.
4. Para testar, cole um texto no painel, clique **Escolher campo para preencher** e depois clique no campo do Muse. O texto é preenchido; o envio permanece manual.
5. Alternativamente carregue a tarefa JSON de teste exportada pelo Reels-face. Revise e inicie: ela só verifica a aba.

Não é necessário Python, outro navegador, senha ou acesso de depuração remota. As permissões são apenas activeTab e scripting. Não há servidor remoto, leitura de cookies, envio de histórico ou código remoto. O acesso começa com o clique na extensão. Recarregar/navegar encerra a execução; reative o painel quando necessário. A interface do site pode mudar e exigir novos seletores. Não opera iframes ou campos dentro de shadow DOM.

Primeira versão supervisionada: não é Codex autônomo, não tem adaptador Muse e não gera vídeos sozinha. A extensão não executa arquivos baixados. Download aciona o controle do próprio site, usa o destino configurado no Chrome e não confirma conclusão. Upload deve ser feito manualmente pelo seletor de arquivos do site. Publicação pede revisão local da mídia, conta, legenda e horário; o clique não prova sucesso. Não há repetição automática. PARAR cancela etapas futuras; não desfaz cliques ou tarefas já enviadas ao serviço. Botões do site podem abrir novas abas conforme o comportamento do próprio site; a extensão não cria abas nem passa a controlá-las.

Formato de tarefa (incompatível com o antigo executor Python):
```json
{"version":1,"target":"current_tab","origin":"https://example.com","steps":[{"action":"check"}]}
```
Ações: check; wait com seconds (1–60); fill com selector CSS e text; click, download ou publish com selector CSS. Até 100 etapas. Fill e cliques pedem confirmação individual. Não inclua senhas. Nenhuma tarefa é obtida automaticamente da nuvem. Instalação no Chrome Windows e comportamento no Muse precisam ser validados na máquina do usuário.
