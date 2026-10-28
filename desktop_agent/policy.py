from urllib.parse import urlsplit

ACTIONS={'open','fill','click','download','upload','publish','wait'}

def origin(url):
    if not isinstance(url,str): raise ValueError("Endereço inválido.")
    p=urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password:
        raise ValueError('Use um endereço HTTPS sem credenciais.')
    if p.hostname in {'localhost','127.0.0.1','::1'}:
        raise ValueError('Endereços locais não são permitidos.')
    return f'https://{p.hostname.lower()}' + (f':{p.port}' if p.port and p.port!=443 else '')

def validate(job):
    if not isinstance(job,dict) or job.get('version')!=1: raise ValueError('Formato de tarefa inválido.')
    sites=job.get('allowed_sites',[])
    if not isinstance(sites,list) or not 1<=len(sites)<=20: raise ValueError('Autorize de 1 a 20 sites.')
    allowed={origin(s) for s in sites}
    steps=job.get('steps',[])
    if not isinstance(steps,list) or not 1<=len(steps)<=100: raise ValueError('Use de 1 a 100 etapas.')
    if not isinstance(steps[0],dict) or steps[0].get('action')!='open': raise ValueError('A primeira etapa deve abrir um site.')
    for s in steps:
        if not isinstance(s,dict) or s.get('action') not in ACTIONS: raise ValueError('Ação desconhecida.')
        if s['action']=='open':
            if origin(s.get('url')) not in allowed: raise ValueError('Site não autorizado.')
        elif s['action']=='wait':
            if not isinstance(s.get('seconds'),int) or not 1<=s['seconds']<=60: raise ValueError('Espera deve ser de 1 a 60 segundos.')
        else:
            if not isinstance(s.get('selector'),str) or not 1<=len(s['selector'])<=500: raise ValueError('Seletor necessário.')
        if s['action']=='fill' and (not isinstance(s.get('text'),str) or len(s['text'])>30000): raise ValueError('Texto inválido.')
    return allowed
