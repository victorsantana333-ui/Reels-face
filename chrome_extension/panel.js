(() => {
  // Isolated extension world. No remote code, page messages, stored secrets or network API.
  if (globalThis.reelsFacePanel) return;
  globalThis.reelsFacePanel = true;
  const initialOrigin = location.origin;
  const host = document.createElement('div');
  host.style.cssText = 'position:fixed;right:12px;top:12px;z-index:2147483647;width:350px;max-height:90vh;';
  const root = host.attachShadow({mode:'closed'});
  root.innerHTML = `<style>
  *{box-sizing:border-box}section{font:14px system-ui;background:#fff;color:#172b22;padding:16px;border:2px solid #286144;border-radius:12px;box-shadow:0 4px 24px #0005;max-height:90vh;overflow:auto}
  button,textarea,input{font:inherit;margin:5px 0;width:100%;padding:8px}button{cursor:pointer}textarea{height:100px}p{line-height:1.4}#stop{background:#ac2222;color:white}#log{white-space:pre-wrap}small{display:block}
  </style><section><b>Reels-face · aba atual</b><p id="site"></p>
  <small>Seu login permanece nesta aba. Ações supervisionadas; sem IA autônoma ou integração pronta com Muse.</small>
  <p>Teste: cole um prompt, clique em “Escolher campo” e depois no campo de texto da página. O texto será preenchido sem envio.</p>
  <textarea id="prompt" placeholder="Seu prompt"></textarea><button id="pick">Escolher campo para preencher</button>
  <p>Ou carregue uma tarefa JSON da extensão:</p><input id="file" type="file" accept=".json,application/json"><button id="run" disabled>Revisar e iniciar tarefa</button>
  <div id="approval" hidden><p id="question"></p><button id="yes">Confirmar ação</button><button id="no">Cancelar</button></div>
  <button id="stop">PARAR</button><button id="close">Fechar painel</button><p id="log" role="status">Conectado à aba atual. Nenhuma ação executada.</p></section>`;
  document.documentElement.append(host);
  const $ = s => root.querySelector(s);
  $('#site').textContent = initialOrigin;
  let job=null, running=false, stopped=false, picking=false, resolveApproval=null;
  const log = text => { $('#log').textContent=text; };
  const assertPage = () => { if (stopped || location.origin!==initialOrigin || !host.isConnected) throw Error('Operação interrompida.'); };
  function stop(){stopped=true;picking=false;if(resolveApproval){resolveApproval(false);resolveApproval=null;}log('Parado. Ações já enviadas ao site não são desfeitas.');}
  function approve(text){
    assertPage(); $('#question').textContent=text;$('#approval').hidden=false;
    return new Promise(resolve=>{resolveApproval=resolve;}).then(ok=>{resolveApproval=null;$('#approval').hidden=true;if(!ok)throw Error('Operação cancelada.');assertPage();});
  }
  $('#yes').onclick=()=>resolveApproval?.(true);
  $('#no').onclick=()=>resolveApproval?.(false);
  $('#stop').onclick=stop;
  $('#close').onclick=()=>{stop();document.removeEventListener('click',pick,true);host.remove();globalThis.reelsFacePanel=false;};
  function fill(el,text){
    if (el instanceof HTMLTextAreaElement || (el instanceof HTMLInputElement && ['text','search','url','email',''].includes(el.type))) {
      const proto=el instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto,'value').set.call(el,text);
    } else if(el.isContentEditable){el.textContent=text;}
    else throw Error('Escolha um campo de texto editável; campos de senha não são permitidos.');
    el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));
  }
  function pick(event){
    if(!picking || event.composedPath().includes(host))return;
    event.preventDefault();event.stopImmediatePropagation();picking=false;
    try{assertPage();fill(event.target,$('#prompt').value);log('Texto preenchido. Revise na página; nada foi enviado automaticamente.');}catch(e){log(e.message);}
  }
  document.addEventListener('click',pick,true);
  $('#pick').onclick=()=>{if(running)return;stopped=false;picking=true;log('Clique no campo de texto do Muse. Para cancelar, clique PARAR.');};
  function validate(value){
    if(value?.version!==1 || value?.target!=='current_tab' || value?.origin!==initialOrigin || !Array.isArray(value.steps) || value.steps.length<1 || value.steps.length>100)throw Error('Use uma tarefa current_tab para o endereço desta aba, com 1 a 100 etapas.');
    for(const s of value.steps){
      if(!s || !['check','fill','click','download','publish','wait'].includes(s.action))throw Error('Ação não suportada nesta extensão.');
      if(['fill','click','download','publish'].includes(s.action) && (typeof s.selector!=='string'||!s.selector||s.selector.length>500))throw Error('Seletor inválido.');
      if(s.action==='fill'&&(typeof s.text!=='string'||s.text.length>30000))throw Error('Texto inválido.');
      if(s.action==='wait'&&(!Number.isInteger(s.seconds)||s.seconds<1||s.seconds>60))throw Error('Espera inválida.');
    }
  }
  $('#file').onchange=async()=>{
    if(running)return;job=null;$('#run').disabled=true;
    try{const file=$('#file').files[0];if(!file||file.size>1048576)throw Error('Use um JSON de até 1 MB.');const value=JSON.parse(await file.text());validate(value);job=value;$('#run').disabled=false;log('Tarefa carregada. Nenhuma ação executada.');}catch{log('Arquivo inválido ou destinado a outra aba. Use a tarefa de teste da extensão.');}
  };
  $('#run').onclick=async()=>{
    if(running||!job)return;running=true;stopped=false;picking=false;$('#run').disabled=true;$('#file').disabled=true;$('#pick').disabled=true;
    try{
      validate(job);
      await approve(`Executar ${job.steps.length} etapas em ${initialOrigin}? Ações: ${job.steps.map(s=>s.action).join(', ')}. Cliques serão revisados individualmente.`);
      const deadline=Date.now()+30*60*1000;
      for(const s of job.steps){
        assertPage();if(Date.now()>deadline)throw Error('Limite de 30 minutos atingido.');
        if(s.action==='check'){log('Teste concluído: conectado à aba atual, sem abrir outra aba.');continue;}
        if(s.action==='wait'){const end=Date.now()+s.seconds*1000;while(Date.now()<end){assertPage();await new Promise(r=>setTimeout(r,100));}continue;}
        const matches=document.querySelectorAll(s.selector);
        if(matches.length!==1)throw Error('O seletor precisa identificar exatamente um elemento.');
        const el=matches[0];if(!el.getClientRects().length)throw Error('Elemento não está visível.');
        if(s.action==='fill'){await approve(`Preencher ${s.selector} com este texto?\n${s.text}`);fill(el,s.text);}
        else{
          const note=s.action==='publish'?'Confira na página o vídeo, a conta de destino, a legenda e o horário. Autoriza publicar? O resultado precisa ser conferido no site.':'Confira o botão e a ação na página. O clique pode consumir créditos, baixar arquivos ou alterar dados.';
          await approve(`${note}\nElemento: ${s.selector}\nTexto: ${(el.textContent||'').slice(0,180)}`);
          if(!el.isConnected || document.querySelector(s.selector)!==el)throw Error('A página mudou. Revise a tarefa novamente.');
          // Downloads use the site's own control and Chrome's normal download handling.
          el.click();log('Clique enviado ao site. Resultado ainda não verificado.');
        }
      }
      log('Etapas concluídas nesta aba. Confira o resultado no site; downloads e publicações não são verificados automaticamente.');
    }catch(e){log(e instanceof Error?e.message:'A tarefa foi interrompida.');}
    finally{running=false;$('#run').disabled=!job;$('#file').disabled=false;$('#pick').disabled=false;$('#approval').hidden=true;}
  };
})();
