"""Visual fixtures only. Intercepts every API request and never writes real data."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
fixture = json.loads((ROOT / 'frontend/tests/fixtures.json').read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--round', default='one')
    args = parser.parse_args()
    output = ROOT / '.impeccable/review'
    output.mkdir(parents=True, exist_ok=True)
    user = {'email':'equipe@example.test','role':'admin','csrf':'test-only','avancosUrl':'https://example.test','semaforoTipos':'Interessado'}
    jobs = [{'id':'job-'+str(i),'action':action,'actor':'equipe@example.test','status':state,
        'created_at':'2026-11-10T08:00:00Z','started_at':'2026-11-10T08:01:00Z','finished_at':None if state=='running' else '2026-11-10T08:03:00Z',
        'heartbeat_at':'2026-11-10T08:02:00Z','error':'Uma conta precisa de reprocessamento.' if state=='partial' else None,
        'result':{'expected':12,'collected':11} if state=='partial' else {'collected':12}}
        for i,(action,state) in enumerate([('campanhas','completed'),('dia-anterior','running'),('custom','partial'),('planilhas','queued')])]
    days=[]
    cumulative=[0,0,0]
    for i in range(1,10):
        sent=150+i*23; opened=50+i*9; replies=2+i%4
        cumulative=[cumulative[0]+sent,cumulative[1]+opened,cumulative[2]+replies]
        days.append({'data':f'2026-11-{i:02d}','totalContacted':sent-20,'emailsSent':sent,'delivered':sent-5,'emailOpens':opened,
            'linkClicks':4+i,'emailReplies':replies,'avancos':i%3,'cumEmailsSent':cumulative[0],'cumEmailOpens':cumulative[1],'cumEmailReplies':cumulative[2]})
    authenticated=[True]
    def route(req):
        path=urlparse(req.request.url).path.replace('/api/','')
        query=parse_qs(urlparse(req.request.url).query)
        status=200
        if path=='auth/me': payload=user if authenticated[0] else {'error':'Entre para continuar.'}; status=200 if authenticated[0] else 401
        elif path=='squads': payload={'squads':fixture['campaigns'],'warnings':['Dados sintéticos, somente para revisão visual.'],'geradoEm':'2026-11-10T08:00:00Z'}
        elif path=='analise-contas': payload={'squads':fixture['summary'],'warnings':[],'geradoEm':'2026-11-10T08:00:00Z'}
        elif path=='analise-cliente': payload={'cliente':query.get('cliente',['Cliente Aurora'])[0],'dias':days,'statusAvanco':'verde','warnings':[]}
        elif path=='status': payload={'worker_online':True,'running':True,'status':'running','action':'dia-anterior','queued':1}
        elif path=='jobs': payload=jobs
        elif path=='config/status': payload={'integrations':[{'name':name,'configured':i<3,'message':'Conexão configurada.' if i<3 else 'Publicação desativada neste ambiente.'} for i,name in enumerate(['Contas e credenciais','Indicadores de avanços','Registro de avanços','Google Sheets'])]}
        elif path=='logs': payload={'cursor':4,'total':4,'reset':False,'lines':[] if int(query.get('since',['0'])[0]) else ['2026-11-10 05:01:00 [job-1] Iniciando coleta do dia anterior','2026-11-10 05:01:03 [job-1] Conta 1 de 12 processada','2026-11-10 05:01:08 [job-1] Conta 2 de 12 processada','2026-11-10 05:01:12 [job-1] Aguardando próxima consulta']}
        elif path=='users': payload=[{'id':i+1,'email':email,'role':'admin' if i==0 else 'viewer','active':i<3} for i,email in enumerate(['gestao@example.test','comercial@example.test','operacao@example.test','consulta@example.test'])]
        elif path=='audit': payload=[{'id':i,'actor':email,'action':action,'createdAt':'2026-11-10T08:00:00Z'} for i,(email,action) in enumerate([('gestao@example.test','auth.login'),('operacao@example.test','job.queued'),('gestao@example.test','user.updated')])]
        elif path=='clientes': payload=[{'id':str(i),'email':r['cliente'],'emailSnovio':r['contas'][0]} for i,r in enumerate(fixture['summary']['Onboarding'])]
        else: payload={'ok':True}
        req.fulfill(json=payload,status=status)
    results=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,channel='chromium')
        for width,screen in [(1440,'desktop'),(390,'mobile')]:
            page=browser.new_page(viewport={'width':width,'height':1000 if width==1440 else 844},reduced_motion='reduce')
            page.route('**/api/**',route)
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            for name,path,selector in [('dashboard','/dados.html','#gridBody tr[data-client]'),('analysis','/analise.html','[data-squad-choice]'),
                ('customer','/analise.html?cliente=Cliente%20Aurora','.chart-canvas'),('operations','/index.html','#jobHistory tbody tr'),
                ('team','/equipe.html','#users tr'),('login','/login.html','#email')]:
                authenticated[0]=name!='login'
                page.goto('http://127.0.0.1:8000'+path)
                page.wait_for_selector(selector)
                page.evaluate('document.fonts.ready')
                page.evaluate("""() => { const el=document.createElement('div'); el.textContent='Prévia visual · dados sintéticos'; el.style.cssText='position:fixed;bottom:8px;left:8px;z-index:9999;padding:5px 9px;background:#fff;border:1px solid #dce3ef;border-radius:4px;font:10px system-ui;color:#52657e';document.body.append(el); }""")
                page.screenshot(path=str(output/(f'{screen}.png' if name=='dashboard' else f'{name}-{screen}.png')),full_page=True)
                size=page.evaluate('({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,bodyHeight:document.body.scrollHeight})')
                results.append({'page':name,'screen':screen,**size,'errors':list(errors)})
                errors.clear()
            page.close()
        browser.close()
    (output/f'checks-{args.round}.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(results,ensure_ascii=True,indent=2))


if __name__=='__main__': main()
