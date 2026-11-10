from datetime import datetime
import json
from core.time import utcnow

import pandas as pd
from sqlalchemy.orm import Session
from db.models import Dados, ContaSnovio, Campanha, Avanco
from db.session import engine

# Lê o CSV
def atualiza_registros(df):
    from db.upsert import upsert
    from core.validation import iso_date
    if df.empty:
        return 0
    fields = ['total_contacted', 'emails_sent', 'delivered', 'email_opens', 'email_replies']
    with engine.begin() as conn:
        for row in df.to_dict('records'):
            iso_date(row['data'])
            values = {k: int(row[k]) for k in fields}
            if any(v < 0 for v in values.values()):
                raise ValueError('Métrica negativa recebida da origem.')
            values.update(conta=str(row['conta']).strip().lower(), campanha=str(row['campanha']),
                          id_conta=str(row['id_conta']), data=row['data'], links_clicks=int(row['link_clicks']))
            upsert(conn, Dados.__table__, values, ['id_conta', 'data'])
    print(f'{len(df)} registro(s) persistido(s).', flush=True)
    return len(df)


def upsert_conta_snovio(session: Session, cliente: dict) -> None:
    """Upsert de uma conta em contas_snovio (dict no formato de api.get_active_clients:
    id, email, client_id, client_secret, email_snovio, senha — só id/email/email_snovio
    são usados, segredo nunca é gravado)."""
    conta = session.get(ContaSnovio, cliente["id"])
    agora = utcnow()
    if conta:
        conta.email = cliente["email"]
        conta.conta_snovio = cliente["email_snovio"].strip().lower()
        conta.status = "ACTIVE"
        conta.sincronizado_em = agora
    else:
        session.add(ContaSnovio(
            id=cliente["id"],
            email=cliente["email"],
            conta_snovio=cliente["email_snovio"].strip().lower(),
            status="ACTIVE",
            sincronizado_em=agora,
        ))


def upsert_campanhas(session: Session, conta_id: str, campanhas_df: pd.DataFrame) -> None:
    """Upsert em lote das campanhas de uma conta (retorno de GET /v1/get-user-campanhas)."""
    if campanhas_df.empty:
        return
    agora = utcnow()
    for _, row in campanhas_df.iterrows():
        campanha_id = row.get("id")
        if campanha_id is None or pd.isna(campanha_id):
            continue
        campanha_id = int(campanha_id)
        nome = row.get("campaign") or ""
        source = {key: None if pd.isna(row.get(key)) else row.get(key)
                  for key in ['created_at', 'updated_at', 'started_at', 'hash']}
        source_json = json.dumps(source, default=str)
        existente = session.get(Campanha, campanha_id)
        if existente:
            existente.conta_id = conta_id
            existente.nome = nome
            existente.source_json = source_json
            existente.list_id = None if pd.isna(row.get("list_id")) else int(row.get("list_id"))
            existente.status_snovio = row.get("status")
            existente.sincronizado_em = agora
        else:
            session.add(Campanha(
                id=campanha_id,
                conta_id=conta_id,
                nome=nome,
                source_json=source_json,
                list_id=None if pd.isna(row.get("list_id")) else int(row.get("list_id")),
                status_snovio=row.get("status"),
                sincronizado_em=agora,
            ))


def sincroniza_campanhas(clientes_com_campanhas: list, active_ids=None) -> int:
    """Recebe uma lista de (cliente_dict, campanhas_df) — um item por conta
    processada em extrai_campanhas() — e grava tudo em uma única transação.
    cliente_dict precisa ter as chaves id/email/email_snovio (sem segredo).
    Retorna o total de linhas de campanha gravadas."""
    total_campanhas = 0
    with Session(engine) as session:
        for cliente, campanhas_df in clientes_com_campanhas:
            upsert_conta_snovio(session, cliente)
            upsert_campanhas(session, cliente["id"], campanhas_df)
            session.flush()
            seen = [int(v) for v in campanhas_df.get('id', [])]
            missing = session.query(Campanha).filter(Campanha.conta_id == cliente['id'])
            if seen:
                missing = missing.filter(~Campanha.id.in_(seen))
            missing.update({'status_snovio': 'Removed'}, synchronize_session=False)
            total_campanhas += len(campanhas_df)
        if active_ids is not None:
            missing_accounts = session.query(ContaSnovio)
            if active_ids:
                missing_accounts = missing_accounts.filter(~ContaSnovio.id.in_(active_ids))
            missing_accounts.update({'status': 'INACTIVE'}, synchronize_session=False)
        session.commit()
    return total_campanhas


def get_campanhas_ativas(historico=False) -> pd.DataFrame:
    """Substitui api.contas_ativas() — lê de campanhas/contas_snovio (MySQL) em vez
    da aba "campanhas" do Sheet de controle. Mesmas colunas que o resto do código já
    espera: id (campanha), campaign (nome), conta (e-mail Snovio), status."""
    with Session(engine) as session:
        query = (
            session.query(Campanha, ContaSnovio)
            .join(ContaSnovio, Campanha.conta_id == ContaSnovio.id)
        )
        if not historico:
            query = query.filter(Campanha.status_snovio == 'Active', ContaSnovio.status == 'ACTIVE')
        registros = query.all()
        if not registros:
            return pd.DataFrame(columns=["id", "campaign", "conta", "status"])

        data = [
            {
                "id": campanha.id,
                "campaign": campanha.nome,
                "conta": conta.conta_snovio,
                "status": campanha.status_snovio,
                "account_status": conta.status,
            }
            for campanha, conta in registros
        ]
        return pd.DataFrame(data)


def cria_avanco(data: str, conta: str, quantidade: int) -> dict:
    """Registra a quantidade de avanços do dia pra um cliente (substitui digitar
    na aba "Avanços" do Sheet)."""
    with Session(engine) as session:
        registro = Avanco(data=data, conta=conta, quantidade=quantidade, criado_em=utcnow())
        session.add(registro)
        session.commit()
        return {"id": registro.id, "data": registro.data, "conta": registro.conta, "quantidade": registro.quantidade}


def lista_avancos(conta: str = None) -> list:
    with Session(engine) as session:
        query = session.query(Avanco)
        if conta:
            query = query.filter(Avanco.conta == conta)
        registros = query.order_by(Avanco.data.desc()).all()
        return [
            {"id": r.id, "data": r.data, "conta": r.conta, "quantidade": r.quantidade}
            for r in registros
        ]


def remove_avanco(avanco_id: int) -> bool:
    with Session(engine) as session:
        registro = session.get(Avanco, avanco_id)
        if not registro:
            return False
        session.delete(registro)
        session.commit()
        return True


def get_analise_cliente(cliente: str, inicio: str = None, fim: str = None) -> list:
    """Série diária de disparos de um cliente (nome no sistema de avanços), somando
    todas as contas e campanhas dele por dia, cruzado com os avanços do dia
    (sistema de avanços). Cliente sem credencial cadastrada é tratado como conta. Base pra tela de análise por cliente.
    inicio/fim em 'YYYY-MM-DD' (inclusive) — se omitidos, traz o histórico inteiro."""
    from core.validation import period
    period(inicio, fim)
    from sqlalchemy import func
    from db import avancos_api

    contas = avancos_api.contas_do_cliente(cliente) or [cliente]
    with Session(engine) as session:
        query_dados = session.query(
            Dados.data,
            func.sum(Dados.total_contacted),
            func.sum(Dados.emails_sent),
            func.sum(Dados.delivered),
            func.sum(Dados.email_opens),
            func.sum(Dados.links_clicks),
            func.sum(Dados.email_replies),
        ).filter(func.lower(Dados.conta).in_([c.lower() for c in contas]))
        if inicio:
            query_dados = query_dados.filter(Dados.data >= inicio)
        if fim:
            query_dados = query_dados.filter(Dados.data <= fim)

        linhas_dados = query_dados.group_by(Dados.data).order_by(Dados.data).all()

    try:
        avancos_por_dia = avancos_api.avancos_dia_do_cliente(cliente, inicio, fim)
        avancos_available = True
    except avancos_api.IntegrationUnavailable:
        avancos_por_dia = {}
        avancos_available = False
    dados_por_dia = {
        data: {
            "totalContacted": int(contatados or 0),
            "emailsSent": int(enviados or 0),
            "delivered": int(entregues or 0),
            "emailOpens": int(abertos or 0),
            "linkClicks": int(cliques or 0),
            "emailReplies": int(respostas or 0),
        }
        for data, contatados, enviados, entregues, abertos, cliques, respostas in linhas_dados
    }

    todas_datas = sorted(set(dados_por_dia) | set(avancos_por_dia))

    dias = []
    cum_enviado = cum_aberto = cum_respondido = 0
    vazio = {"totalContacted": 0, "emailsSent": 0, "delivered": 0, "emailOpens": 0, "linkClicks": 0, "emailReplies": 0}
    for data in todas_datas:
        metricas = dados_por_dia.get(data, vazio)
        cum_enviado += metricas["emailsSent"]
        cum_aberto += metricas["emailOpens"]
        cum_respondido += metricas["emailReplies"]
        dias.append({
            "data": data,
            **metricas,
            "avancos": avancos_por_dia.get(data, 0) if avancos_available else None,
            "cumEmailsSent": cum_enviado,
            "cumEmailOpens": cum_aberto,
            "cumEmailReplies": cum_respondido,
        })
    return dias


def get_dados_by_id_conta(conta: str) -> pd.DataFrame:
    """
    Retorna um DataFrame com todos os registros da tabela 'dados'
    filtrados por um id_conta específico.
    """
    with Session(engine) as session:
        # Consulta todos os registros com id_conta especificado
        registros = session.query(Dados).filter(Dados.conta == conta).all()

        # Se não encontrar nada, retorna DataFrame vazio
        if not registros:
            return pd.DataFrame()

        # Converte a lista de objetos em lista de dicionários
        data = [
            {
                "id": r.id,
                "conta": r.conta,
                "campanha": r.campanha,
                "id_conta": r.id_conta,
                "data": r.data,
                "total_contacted": r.total_contacted,
                "emails_sent": r.emails_sent,
                "delivered": r.delivered,
                "email_opens": r.email_opens,
                "links_clicks": r.links_clicks,
                "email_replies": r.email_replies,
            }
            for r in registros
        ]

        # Cria DataFrame
        return pd.DataFrame(data)
