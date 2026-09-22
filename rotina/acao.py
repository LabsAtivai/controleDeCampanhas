import pygsheets
import pandas as pd
import json
import httpx
from datetime import timedelta, date, datetime
from rotina import api
from db import crud
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
import time
import threading


# Lock e contador para limitar requisições
rate_lock = threading.Lock()
last_request_time = 0

def extrai_campanhas(ids_selecionados=None):
    """ids_selecionados: conjunto opcional de ids de conta (sistema de credenciais)
    pra rodar só um subconjunto de clientes, em vez de todos os ativos."""
    print("Iniciando etapa de extração de campanhas")
    
    def gera_token(client_id, client_secret):
        global last_request_time
        with rate_lock:
            agora = time.time()
            espera = 1 - (agora - last_request_time)  # garante 1 req/s = 60/min
            if espera > 0:
                time.sleep(espera)
            last_request_time = time.time()

        params = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret
        }
        res = httpx.post('https://api.snov.io/v1/oauth/access_token', data=params)
        resText = res.text.encode('ascii', 'ignore')
        token = json.loads(resText)['access_token']
        return token

    df = api.senhas()
    if ids_selecionados:
        df = df[df['id'].isin(ids_selecionados)]

    def campanhas(token):
        global last_request_time
        with rate_lock:
            agora = time.time()
            espera = 1 - (agora - last_request_time)
            if espera > 0:
                time.sleep(espera)
            last_request_time = time.time()

        headers = {"Authorization": "Bearer " + token}
        res = httpx.get('https://api.snov.io/v1/get-user-campaigns', headers=headers)
        resultado = pd.DataFrame(json.loads(res.text))
        return resultado

    def campanhas_para_cliente(row):
        try:
            token_value = gera_token(row['Client id'], row['Client Secret'])
            campanha_df = campanhas(token_value)
            if not campanha_df.empty:
                campanha_df['id'] = pd.to_numeric(campanha_df['id'], errors='coerce')
                campanha_df = campanha_df.dropna(subset=['id']).drop_duplicates(subset=['id'])
            return campanha_df
        except Exception as e:
            #print(f"Erro para o cliente {row['Email Snovio']}: {e}")
            return pd.DataFrame()

    clientes_com_campanhas = []

    total = len(df)
    i = 0

    for _, row in df.iterrows():
        resultado = campanhas_para_cliente(row)
        i += 1

        # Progresso em linha, sempre aparece nos logs
        print(f"[{i}/{total}] Extraido a conta", flush=True)

        cliente = {"id": row['id'], "email": row['Email'], "email_snovio": row['Email Snovio']}
        clientes_com_campanhas.append((cliente, resultado))

    total_campanhas = crud.sincroniza_campanhas(clientes_com_campanhas)
    print(f"✅ {total_campanhas} campanha(s) sincronizada(s) no banco de dados")

    atualiza_aba_campanhas_master(clientes_com_campanhas)

    print("Etapa de Extração de Campanhas Finalizada")


def atualiza_aba_campanhas_master(clientes_com_campanhas):
    """Reescreve a aba "campanhas" do Sheet mestre. As planilhas de squad puxam
    essa aba via IMPORTRANGE (aba "base") e usam a coluna I (conta) como opções
    do dropdown "Escolha a Campanha da Planilha" — sem isso, cliente novo não
    aparece pra ser escolhido. Client id/Secret não são mais gravados aqui."""
    colunas = ['id', 'campaign', 'list_id', 'status', 'created_at', 'updated_at', 'started_at', 'hash', 'conta']

    frames = []
    for cliente, campanha_df in clientes_com_campanhas:
        if campanha_df.empty:
            continue
        campanha_df = campanha_df.copy()
        campanha_df['conta'] = str(cliente['email_snovio']).strip().lower()
        frames.append(campanha_df.reindex(columns=colunas))

    if not frames:
        print("⚠️ Nenhuma campanha retornada, aba 'campanhas' do Sheet mestre não foi alterada")
        return

    df = pd.concat(frames, ignore_index=True).fillna('')
    gc = pygsheets.authorize()
    aba = gc.open_by_key('1NJzsYoLFu2zHNYS6lsltWou2qn2DFMBv4sqAI0Mer4k').worksheet_by_title("campanhas")
    aba.clear()
    aba.set_dataframe(df, start='A1', fit=True)
    print(f"✅ Aba 'campanhas' do Sheet mestre atualizada ({len(df)} linhas)")
        
def extrai_dia_anterior():
    print("Iniciando processo para extração do Status do Dia Anterior")
    df = api.senhas()
    contas = api.contas_ativas()
    contas = contas.merge(
        df[['Email Snovio', 'Client id', 'Client Secret']],
        left_on='conta', right_on='Email Snovio', how='inner'
    )

    def processa_conta(row):
        try:
            token_acesso = api.gera_token(row['Client id'], row['Client Secret'])
            inicio = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
            final = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
            dados = api.get_campaign_analytics(token_acesso, row['id'], inicio, final)
            return {
                "conta": row['conta'],
                "campanha": row['campaign'],
                "id_conta": row['id'],
                "data": inicio,
                'total_contacted': dados['total_contacted'],
                "emails_sent": dados['emails_sent'],
                "delivered": dados['delivered'],
                "email_opens": dados['email_opens'],
                "link_clicks": dados['link_clicks'],
                "email_replies": dados['email_replies']
            }
        except Exception as e:
            print(f"[ERRO] Conta: {row['conta']} - Erro: {e}")
            return None

    resultados = []
    contas_pendentes = contas.copy()

    tentativa = 1
    max_tentativas = 10

    while tentativa <= max_tentativas and not contas_pendentes.empty:
        print(f"\n=== Tentativa {tentativa}/{max_tentativas} ===")
        resultados_atuais = []
        erros_atuais = []

        total = len(contas_pendentes)
        for i, (_, row) in enumerate(contas_pendentes.iterrows(), start=1):
            conta_nome = row['conta']
            print(f"\n[{i}/{total}] Tentativa {tentativa} - Processando conta: {conta_nome}", flush=True)
            
            resultado = processa_conta(row)
            
            if resultado is not None:
                resultados_atuais.append(resultado)
                print(f"✅ Conta '{conta_nome}' processada com sucesso.", flush=True)
            else:
                erros_atuais.append(row)
                print(f"❌ Erro ao processar conta '{conta_nome}'. Será reprocessada mais tarde.", flush=True)
            
            # Pequena pausa entre as contas para evitar sobrecarga da API
            time.sleep(1)
        
        # Armazena resultados obtidos
        resultados.extend(resultados_atuais)
        
        # Verifica se ainda há erros
        if not erros_atuais:
            print("\n🎉 Todas as contas processadas com sucesso!")
            break
        
        print(f"\n⚠️ {len(erros_atuais)} contas falharam nesta rodada.")
        print("⏳ Aguardando 5 minutos antes da nova tentativa...")
        time.sleep(300)
        
        # Prepara para nova tentativa
        contas_pendentes = pd.DataFrame(erros_atuais)
        tentativa += 1

    df_resultados = pd.DataFrame(resultados)
    
    print("🚀 Iniciando atualização do banco de dados...")
    crud.atualiza_registros(df_resultados)
    print("✅ Processo concluído com sucesso.")
    
def extrai_dia_anterior_custom(data='2026-03-24'):
    print("Iniciando processo para extração do Status do Dia Anterior")

    if isinstance(data, str):
        try:
            data_ref = datetime.strptime(data, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Data deve estar no formato YYYY-MM-DD")
    elif isinstance(data, date):
        data_ref = data
    else:
        raise TypeError("Parâmetro 'data' deve ser str ou date")

    df = api.senhas()
    contas = api.contas_ativas()
    contas = contas.merge(
        df[['Email Snovio', 'Client id', 'Client Secret']],
        left_on='conta', right_on='Email Snovio', how='inner'
    )

    def processa_conta(row):
        try:
            token_acesso = api.gera_token(row['Client id'], row['Client Secret'])
            inicio = data_ref.strftime('%Y-%m-%d')
            final = data_ref.strftime('%Y-%m-%d')
            dados = api.get_campaign_analytics(token_acesso, row['id'], inicio, final)
            return {
                "conta": row['conta'],
                "campanha": row['campaign'],
                "id_conta": row['id'],
                "data": inicio,
                'total_contacted': dados['total_contacted'],
                "emails_sent": dados['emails_sent'],
                "delivered": dados['delivered'],
                "email_opens": dados['email_opens'],
                "link_clicks": dados['link_clicks'],
                "email_replies": dados['email_replies']
            }
        except Exception as e:
            print(f"[ERRO] Conta: {row['conta']} - Erro: {e}")
            return None

    resultados = []
    contas_pendentes = contas.copy()

    tentativa = 1
    max_tentativas = 5

    while tentativa <= max_tentativas and not contas_pendentes.empty:
        print(f"\n=== Tentativa {tentativa}/{max_tentativas} — {len(contas_pendentes)} contas ===")
        resultados_atuais = []
        erros_atuais = []

        total = len(contas_pendentes)
        for i, (_, row) in enumerate(contas_pendentes.iterrows(), start=1):
            print(f"[{i}/{total}] Processando conta: {row['conta']}", flush=True)
            resultado = processa_conta(row)
            if resultado is not None:
                resultados_atuais.append(resultado)
                print(f"✅ {row['conta']}", flush=True)
            else:
                erros_atuais.append(row)
                print(f"❌ {row['conta']} — será reprocessada", flush=True)
            time.sleep(1)

        resultados.extend(resultados_atuais)

        if not erros_atuais:
            print("\n🎉 Todas as contas processadas!")
            break

        print(f"\n⚠️ {len(erros_atuais)} contas falharam. Aguardando 2 min...")
        time.sleep(120)
        contas_pendentes = pd.DataFrame(erros_atuais)
        tentativa += 1

    df_resultados = pd.DataFrame(resultados)
    print("Iniciando Atualização do Banco de Dados")
    crud.atualiza_registros(df_resultados)
    print(f"✅ Concluído para {data_ref}")
def atualiza_planilhas_controle():
    
    print("Atualizar a base de Dados das Planilhas de Controle")
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    gc = pygsheets.authorize()
    sh1 = gc.open_by_key('1NJzsYoLFu2zHNYS6lsltWou2qn2DFMBv4sqAI0Mer4k')
    planilhas = sh1.worksheet_by_title("planilhas")
    lista_planilha = planilhas.get_as_df()
    
    def retorno_lista_campanhas(URL):
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

        gc = pygsheets.authorize()
        sh = gc.open_by_url(URL)
        lista_campanhas = sh.worksheet_by_title("Campanhas")
        df = lista_campanhas.get_as_df()
        return df
    
    def carrega_dados(df,URL):
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

        gc = pygsheets.authorize()
        sh = gc.open_by_url(URL)
        lista_registros = sh.worksheet_by_title("registro")
        lista_registros.set_dataframe(df,start='A1', fit=True)
        
    i=0
    dados = []
    total_planilhas = len(lista_planilha)
    
    for _, row in lista_planilha.iterrows():
        dados = []  # limpa a lista de dados para cada planilha
        df_final = pd.DataFrame()  # reseta o DataFrame final para cada planilha
        i += 1
        print(f"[{i}/{total_planilhas}] Processando Planilha de Controle: {row['URL']}", flush=True)

        listas_campanhas = retorno_lista_campanhas(row['URL'])
        listas_campanhas["id"] = listas_campanhas["Escolha a Campanha da Planilha"].str.split(" - ").str[0]

        total_campanhas = len(listas_campanhas)
        j = 0

        for _, linha in listas_campanhas.iterrows():
            j += 1
            print(f"   [{j}/{total_campanhas}] Processando campanha {linha['id']}", flush=True)

            df_temp = crud.get_dados_by_id_conta(linha['id'])
            if not df_temp.empty:   # evita adicionar DataFrames vazios
                dados.append(df_temp)

        if dados:
            df_final = pd.concat(dados, ignore_index=True)
            df_final = df_final.fillna(0)
            df_final = df_final.drop_duplicates(subset=['id'])
            # Registros antigos vinham com a conta capitalizada (ex: BioCarnes@ativa.ai),
            # os novos vêm minúsculos — o QUERY do Dashboard separa os dois
            df_final['conta'] = df_final['conta'].astype(str).str.strip().str.lower()
        else:
            df_final = pd.DataFrame()

        carrega_dados(df_final, row['URL'])