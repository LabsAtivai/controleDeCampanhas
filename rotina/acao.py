"""Coleta verificável: persiste acertos e sinaliza explicitamente falhas parciais."""
import os
import json
import time
from datetime import date, datetime, timedelta
import pandas as pd
from core.config import enabled, google_client, master_sheet_id
from core.validation import iso_date
from db import crud
from db.avancos_api import hoje_sp
from rotina import api

class CollectionError(RuntimeError):
    def __init__(self, message, result):
        super().__init__(message)
        self.result = result
        self.partial = result.get('collected', 0) > 0

def extrai_campanhas(ids_selecionados=None):
    print('Iniciando sincronização de campanhas.', flush=True)
    accounts = api.senhas(ids_selecionados)
    all_ids = set(accounts['id'])
    if ids_selecionados is not None:
        if set(ids_selecionados) - all_ids:
            raise ValueError('A seleção contém contas inativas ou desconhecidas.')
        accounts = accounts[accounts['id'].isin(ids_selecionados)]
    if accounts.empty:
        raise CollectionError('Nenhuma conta ativa disponível.', {'expected': 0, 'collected': 0, 'failed': []})
    succeeded, failed = [], []
    for i, row in enumerate(accounts.to_dict('records'), 1):
        print(f"[{i}/{len(accounts)}] Conta {row['Email Snovio']}", flush=True)
        try:
            frame = api.campanhas(api.gera_token(row['Client id'], row['Client Secret']))
            if not frame.empty:
                frame['id'] = pd.to_numeric(frame['id'], errors='raise').astype('int64')
                if frame['id'].duplicated().any():
                    raise ValueError('Campanhas duplicadas na origem.')
            succeeded.append(({'id': row['id'], 'email': row['Email'], 'email_snovio': row['Email Snovio']}, frame))
        except Exception as exc:
            print(f"Falha na conta {row['Email Snovio']}: {type(exc).__name__}", flush=True)
            failed.append(row['id'])
        time.sleep(float(os.getenv('SNOV_REQUEST_INTERVAL', '1')))
    count = crud.sincroniza_campanhas(succeeded, active_ids=all_ids if ids_selecionados is None and not failed else None)
    result = {'expected': len(accounts), 'collected': len(succeeded), 'campaigns': count, 'failed': failed}
    if failed:
        raise CollectionError('Sincronização incompleta; reprocesse as contas com falha.', result)
    if enabled('GOOGLE_SHEETS_ENABLED', True):
        atualiza_aba_campanhas_master()
    return result

def _replace_sheet(worksheet, frame):
    """One updateCells request replaces values and clears the old tail atomically.
    Sheet id stays unchanged, preserving IMPORTRANGE and existing references."""
    values = [list(frame.columns)] + frame.fillna('').astype(object).values.tolist()
    cells = [{'values': [{'userEnteredValue': {'numberValue': float(v)}
        if isinstance(v, (int, float)) and not isinstance(v, bool) else {'stringValue': str(v)}} for v in row]} for row in values]
    height, width = max(worksheet.rows, len(values)), max(worksheet.cols, len(frame.columns))
    requests = []
    if height != worksheet.rows or width != worksheet.cols:
        requests.append({'updateSheetProperties': {'properties': {'sheetId': worksheet.id,
            'gridProperties': {'rowCount': height, 'columnCount': width}}, 'fields': 'gridProperties(rowCount,columnCount)'}})
    requests.append({'updateCells': {'range': {'sheetId': worksheet.id, 'startRowIndex': 0, 'endRowIndex': height,
        'startColumnIndex': 0, 'endColumnIndex': width}, 'rows': cells, 'fields': 'userEnteredValue'}})
    worksheet.client.sheet.batch_update(worksheet.spreadsheet.id, requests)

def atualiza_aba_campanhas_master():
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from db.models import Campanha, ContaSnovio
    from db.session import engine
    columns = ['id', 'campaign', 'list_id', 'status', 'created_at', 'updated_at', 'started_at', 'hash', 'conta']
    with Session(engine) as db:
        rows = db.execute(select(Campanha, ContaSnovio).join(ContaSnovio).where(
            ContaSnovio.status == 'ACTIVE', Campanha.status_snovio != 'Removed')).all()
        data = [{**json.loads(c.source_json or '{}'), 'id': c.id, 'campaign': c.nome, 'list_id': c.list_id, 'status': c.status_snovio,
                 'conta': account.conta_snovio.lower()} for c, account in rows]
    frame = pd.DataFrame(data, columns=columns)
    worksheet = google_client().open_by_key(master_sheet_id()).worksheet_by_title('campanhas')
    _replace_sheet(worksheet, frame)
    print(f'Planilha mestre publicada: {len(frame)} campanhas.', flush=True)
    return {'rows': len(frame)}

def extrai_dia_anterior():
    return extrai_dia_anterior_custom(hoje_sp() - timedelta(days=1))

def extrai_dia_anterior_custom(data=None, contas_filtro=None, credenciais=None):
    if isinstance(data, str):
        data = iso_date(data)
    if not isinstance(data, date) or isinstance(data, datetime):
        raise ValueError('Informe a data da coleta.')
    if data >= hoje_sp():
        raise ValueError('Colete apenas dias fechados, anteriores a hoje em São Paulo.')
    ref = data.isoformat()
    credentials = api.senhas() if credenciais is None else credenciais.copy()
    credentials['Email Snovio'] = credentials['Email Snovio'].str.strip().str.lower()
    campaigns = api.contas_ativas(historico=True)
    if 'account_status' in campaigns:
        campaigns = campaigns[campaigns['account_status'] == 'ACTIVE']
    campaigns = campaigns[campaigns['status'] != 'Removed']
    campaigns['conta'] = campaigns['conta'].astype(str).str.strip().str.lower()
    if contas_filtro:
        campaigns = campaigns[campaigns['conta'].isin({c.strip().lower() for c in contas_filtro})]
    if campaigns.empty:
        raise CollectionError('Nenhuma campanha cadastrada; sincronize campanhas primeiro.', {'expected': 0, 'collected': 0, 'failed': []})
    available = {r['Email Snovio']: r for r in credentials.to_dict('records')}
    tokens, results, failed = {}, [], []
    for i, campaign in enumerate(campaigns.to_dict('records'), 1):
        print(f"[{i}/{len(campaigns)}] {ref}: campanha {campaign['id']}", flush=True)
        account = available.get(campaign['conta'])
        if not account:
            failed.append({'campaign': str(campaign['id']), 'reason': 'Conta sem credencial ativa.'})
            continue
        metrics = None
        for attempt in range(3):
            try:
                cached = tokens.get(account['Client id'])
                if not cached or time.monotonic() - cached[0] > 3000:
                    cached = (time.monotonic(), api.gera_token(account['Client id'], account['Client Secret']))
                    tokens[account['Client id']] = cached
                metrics = api.get_campaign_analytics(cached[1], campaign['id'], ref, ref)
                break
            except Exception as exc:
                if getattr(exc, 'status', None) in {401, 403}:
                    tokens.pop(account['Client id'], None)
                print(f"Tentativa {attempt + 1}: {type(exc).__name__}", flush=True)
                if attempt < 2:
                    time.sleep(2 ** attempt)
        if metrics is None:
            failed.append({'campaign': str(campaign['id']), 'reason': 'Consulta falhou após retentativas.'})
        else:
            results.append({'conta': campaign['conta'], 'campanha': campaign['campaign'],
                            'id_conta': str(campaign['id']), 'data': ref, **metrics})
        time.sleep(float(os.getenv('SNOV_REQUEST_INTERVAL', '1')))
    crud.atualiza_registros(pd.DataFrame(results))
    result = {'date': ref, 'expected': len(campaigns), 'collected': len(results), 'failed': failed}
    if failed:
        raise CollectionError('Coleta incompleta; consulte as campanhas com falha.', result)
    return result

def atualiza_planilhas_controle():
    if not enabled('GOOGLE_SHEETS_ENABLED', True):
        return {'skipped': True, 'reason': 'Publicação Google Sheets desabilitada.'}
    client = google_client()
    master = client.open_by_key(master_sheet_id())
    sheets = master.worksheet_by_title('planilhas').get_as_df()
    failed, collected = [], 0
    for row in sheets.to_dict('records'):
        try:
            sheet = client.open_by_url(row['URL'])
            selected = sheet.worksheet_by_title('Campanhas').get_as_df()
            accounts = selected['Escolha a Campanha da Planilha'].dropna().astype(str).str.split(' - ').str[0].str.strip().str.lower()
            frames = [crud.get_dados_by_id_conta(account) for account in accounts if account]
            frames = [f for f in frames if not f.empty]
            if frames:
                frame = pd.concat(frames, ignore_index=True).drop_duplicates('id').fillna(0)
                frame['conta'] = frame['conta'].str.strip().str.lower()
            else:
                raise ValueError('Sem dados para publicar; publicação anterior preservada.')
            _replace_sheet(sheet.worksheet_by_title('registro'), frame)
            collected += 1
        except Exception as exc:
            print(f'Falha na planilha: {type(exc).__name__}', flush=True)
            failed.append({'sheet': row.get('URL'), 'reason': str(exc)})
    result = {'expected': len(sheets), 'collected': collected, 'failed': failed}
    if failed:
        raise CollectionError('Publicação de planilhas incompleta.', result)
    return result
