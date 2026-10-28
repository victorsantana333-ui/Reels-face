# Agente local Windows — primeira versão supervisionada

Instale Python 3.12+ (python.org) e Google Chrome. Baixe o repositório do GitHub como ZIP, extraia e abra `desktop_agent/iniciar-windows.bat`. O instalador cria um ambiente Python local e instala Playwright; não instala executáveis de navegador adicionais.

Na área Automação do Desktop do Reels-face, exporte uma tarefa JSON. No agente, abra a tarefa, escolha uma pasta de downloads e revise os sites e ações. Ele usa um perfil Chrome separado em `%LOCALAPPDATA%/ReelsFaceAgent/chrome-profile`. Faça login manualmente nesse navegador; sua sessão fica nesse computador. Mantenha a VPN ativa se o serviço exigir. Nunca compartilhe o diretório de perfil.

Esta versão **não é um agente de IA autônomo**, não conecta esta conversa ao computador e não implementa um adaptador Muse ou Meta. É um executor supervisionado de etapas explícitas: abrir, preencher, clicar, esperar, baixar mídia, escolher/enviar vídeo e solicitar publicação. Seletores precisam ser definidos e testados na interface real. Não utiliza endpoints internos nem contorna CAPTCHA, login, limites ou permissões. Confira se o serviço permite a automação antes de executar tarefas nele.

Os cliques genéricos pedem confirmação porque um seletor não revela com segurança se ele vai comprar, excluir ou publicar. Publicação pede aprovação do arquivo escolhido, seu hash e do destino visível. O resultado é registrado como **enviado, não verificado**; o usuário confere a página. Não há repetição automática que possa duplicar uma postagem. Downloads ficam na pasta autorizada com nomes aleatórios; arquivos não são executados.

PARAR sinaliza o encerramento; ações de navegador com timeout podem levar até 20 segundos para retornar. Downloads em andamento podem demorar mais; feche o Chrome se necessário. Cada operação tem até 100 etapas e duração verificada de 30 minutos entre etapas. Fechar o agente solicita parada. O histórico `audit.jsonl` contém tipos de ações, horários e índices, sem prompts, senhas ou conteúdo.

Não existe servidor de controle remoto, pareamento com a nuvem, fila remota nem status sincronizado com o Reels-face nesta versão. A transferência de tarefas ocorre por arquivo JSON, com revisão no Windows. O agente não precisa da senha do banco ou da chave Streamlit. A publicação requer login e permissões efetivas na página/plataforma.

O núcleo de validação foi testado no ambiente Linux; a instalação e a execução gráfica em Windows precisam ser confirmadas na máquina do usuário. O primeiro teste deve somente abrir um site autorizado, sem ações de produção ou publicação.
