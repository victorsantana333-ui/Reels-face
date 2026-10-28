document.querySelector('#attach').addEventListener('click', async () => {
  const status = document.querySelector('#status');
  try {
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    if (!tab?.id || !tab.url?.startsWith('https://')) throw new Error();
    await chrome.scripting.executeScript({target: {tabId: tab.id}, files: ['panel.js']});
    status.textContent = 'Painel aberto na própria aba. Você pode fechar esta janela.';
  } catch {
    status.textContent = 'Selecione uma página HTTPS comum e tente novamente. Páginas internas do Chrome não permitem este acesso.';
  }
});
