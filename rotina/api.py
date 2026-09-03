import httpx
import json
import pandas as pd
import pygsheets

from rotina import credentials_api

def gera_token(client_id,client_secret):
    params = {'grant_type':'client_credentials',
                'client_id': client_id,
                'client_secret': client_secret}
    res = httpx.post('https://api.snov.io/v1/oauth/access_token', data=params)
    resText = res.text.encode('ascii','ignore')
    try:
        token = json.loads(resText)['access_token']
    except:
        token=res.text
        print(res.text)
    return token


def campanhas(token):
        
    headers = {"Authorization": "Bearer "+token}
    res = httpx.get('https://api.snov.io/v1/get-user-campaigns', headers=headers)
    resultado = pd.DataFrame(json.loads(res.text))
    
    return resultado

def senhas():
    """Contas ativas via sistema de credenciais (não lê mais o Google Sheets).
    Mantém as mesmas colunas que o resto do código já espera (Email, Client id,
    Client Secret, Email Snovio) — só troca a fonte. 'id' também vem disponível,
    é o id da conta no sistema de credenciais (usado pra cruzar com contas_snovio).
    """
    clientes = credentials_api.get_active_clients()
    df = pd.DataFrame(clientes)
    df = df.rename(columns={
        "email": "Email",
        "client_id": "Client id",
        "client_secret": "Client Secret",
        "email_snovio": "Email Snovio",
    })
    return df

def contas_ativas():
    """Campanhas ativas via MySQL (contas_snovio/campanhas) — não lê mais o
    Google Sheets. Ver db/crud.py::get_campanhas_ativas."""
    from db import crud
    return crud.get_campanhas_ativas()

def user_lists(token,id):
    params = {'access_token':token,
            'campaignId':int(id)
    }
    res = httpx.get('https://api.snov.io/v1/emails-sent', params=params,timeout=30)

    return pd.DataFrame(json.loads(res.text))


def get_campaign_analytics(token,id,inicio,final):
   campaign_ids = [id]
   #sender_email_ids = [21, 22]
   #sender_linkedin_ids = [31, 32, 33]
   #owner_emails = ['owner1@email.loc', 'owner2@email.loc']

   params = {
       'access_token': token,
       'campaign_id': ','.join(map(str, campaign_ids)),
       #'sender_email': ','.join(map(str, sender_email_ids)),
       #'sender_linkedin': ','.join(map(str, sender_linkedin_ids)),
       #'campaign_owner': ','.join(owner_emails),
       'date_from': inicio,
       'date_to': final,
   }

   res = httpx.get('https://api.snov.io/v2/statistics/campaign-analytics', params=params, timeout=30)
   return json.loads(res.text)