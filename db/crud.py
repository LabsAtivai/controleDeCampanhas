from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine
from db.session import create_tables
import pandas as pd
from sqlalchemy.orm import Session
from db.models import Dados, ContaSnovio, Campanha, Avanco
from db.session import get_engine

# Lê o CSV
def atualiza_registros(df):
    # Abre sessão
    with Session(get_engine()) as session:
        total = len(df)
        for i, (_, row) in enumerate(df.iterrows(), start=1):
            # Progresso sequencial
            print(f"[{i}/{total}] Atualizando registro id_conta={row['id_conta']}, data={row['data']}", flush=True)

            # Procura registro existente pelo par (id_conta, data)
            existente = session.query(Dados).filter_by(
                id_conta=row["id_conta"],
                data=row["data"]
            ).first()

            if existente:
                # Atualiza os campos
                existente.conta = row.get("conta")
                existente.campanha = row.get("campanha")
                existente.total_contacted = row.get("total_contacted")
                existente.emails_sent = row.get("emails_sent")
                existente.delivered = row.get("delivered")
                existente.email_opens = row.get("email_opens")
                existente.links_clicks = row.get("link_clicks")
                existente.email_replies = row.get("email_replies")
            else:
                # Insere novo registro
                novo = Dados(
                    conta=row.get("conta"),
                    campanha=row.get("campanha"),
                    id_conta=row.get("id_conta"),
                    data=row.get("data"),
                    total_contacted=row.get("total_contacted"),
                    emails_sent=row.get("emails_sent"),
                    delivered=row.get("delivered"),
                    email_opens=row.get("email_opens"),
                    links_clicks=row.get("link_clicks"),
                    email_replies=row.get("email_replies"),
                )
                session.add(novo)

        # Confirma as alterações
        session.commit()
        print("✅ Registros atualizados no Banco de Dados")
        
        
def upsert_conta_snovio(session: Session, cliente: dict) -> None:
    """Upsert de uma conta em contas_snovio (dict no formato de api.get_active_clients:
    id, email, client_id, client_secret, email_snovio, senha — só id/email/email_snovio
    são usados, segredo nunca é gravado)."""
    conta = session.get(ContaSnovio, cliente["id"])
    agora = datetime.utcnow()
    if conta:
        conta.email = cliente["email"]
        conta.conta_snovio = cliente["email_snovio"]
        conta.status = "ACTIVE"
        conta.sincronizado_em = agora
    else:
        session.add(ContaSnovio(
            id=cliente["id"],
            email=cliente["email"],
            conta_snovio=cliente["email_snovio"],
            status="ACTIVE",
            sincronizado_em=agora,
        ))


def upsert_campanhas(session: Session, conta_id: str, campanhas_df: pd.DataFrame) -> None:
    """Upsert em lote das campanhas de uma conta (retorno de GET /v1/get-user-campanhas)."""
    if campanhas_df.empty:
        return
    agora = datetime.utcnow()
    for _, row in campanhas_df.iterrows():
        campanha_id = row.get("id")
        if campanha_id is None or pd.isna(campanha_id):
            continue
        campanha_id = int(campanha_id)
        nome = row.get("campaign") or ""
        existente = session.get(Campanha, campanha_id)
        if existente:
            existente.conta_id = conta_id
            existente.nome = nome
            existente.list_id = row.get("list_id")
            existente.status_snovio = row.get("status")
            existente.sincronizado_em = agora
        else:
            session.add(Campanha(
                id=campanha_id,
                conta_id=conta_id,
                nome=nome,
                list_id=row.get("list_id"),
                status_snovio=row.get("status"),
                sincronizado_em=agora,
            ))


def sincroniza_campanhas(clientes_com_campanhas: list) -> int:
    """Recebe uma lista de (cliente_dict, campanhas_df) — um item por conta
    processada em extrai_campanhas() — e grava tudo em uma única transação.
    cliente_dict precisa ter as chaves id/email/email_snovio (sem segredo).
    Retorna o total de linhas de campanha gravadas."""
    total_campanhas = 0
    with Session(get_engine()) as session:
        for cliente, campanhas_df in clientes_com_campanhas:
            upsert_conta_snovio(session, cliente)
            upsert_campanhas(session, cliente["id"], campanhas_df)
            total_campanhas += len(campanhas_df)
        session.commit()
    return total_campanhas


def get_campanhas_ativas() -> pd.DataFrame:
    """Substitui api.contas_ativas() — lê de campanhas/contas_snovio (MySQL) em vez
    da aba "campanhas" do Sheet de controle. Mesmas colunas que o resto do código já
    espera: id (campanha), campaign (nome), conta (e-mail Snovio), status."""
    with Session(get_engine()) as session:
        registros = (
            session.query(Campanha, ContaSnovio)
            .join(ContaSnovio, Campanha.conta_id == ContaSnovio.id)
            .filter(Campanha.status_snovio == "Active")
            .all()
        )
        if not registros:
            return pd.DataFrame(columns=["id", "campaign", "conta", "status"])

        data = [
            {
                "id": campanha.id,
                "campaign": campanha.nome,
                "conta": conta.conta_snovio,
                "status": campanha.status_snovio,
            }
            for campanha, conta in registros
        ]
        return pd.DataFrame(data)


def cria_avanco(data: str, conta: str, quantidade: int) -> dict:
    """Registra a quantidade de avanços do dia pra um cliente (substitui digitar
    na aba "Avanços" do Sheet)."""
    with Session(get_engine()) as session:
        registro = Avanco(data=data, conta=conta, quantidade=quantidade, criado_em=datetime.utcnow())
        session.add(registro)
        session.commit()
        return {"id": registro.id, "data": registro.data, "conta": registro.conta, "quantidade": registro.quantidade}


def lista_avancos(conta: str = None) -> list:
    with Session(get_engine()) as session:
        query = session.query(Avanco)
        if conta:
            query = query.filter(Avanco.conta == conta)
        registros = query.order_by(Avanco.data.desc()).all()
        return [
            {"id": r.id, "data": r.data, "conta": r.conta, "quantidade": r.quantidade}
            for r in registros
        ]


def remove_avanco(avanco_id: int) -> bool:
    with Session(get_engine()) as session:
        registro = session.get(Avanco, avanco_id)
        if not registro:
            return False
        session.delete(registro)
        session.commit()
        return True


def get_analise_cliente(conta: str, inicio: str = None, fim: str = None) -> list:
    """Série diária de disparos de um cliente (identificado por conta, ex:
    abluo@ativa.ai), somando todas as campanhas dele por dia, cruzado com a
    quantidade de avanços manuais do dia. Base pra tela de análise por cliente.
    inicio/fim em 'YYYY-MM-DD' (inclusive) — se omitidos, traz o histórico inteiro."""
    from sqlalchemy import func

    with Session(get_engine()) as session:
        query_dados = session.query(
            Dados.data,
            func.sum(Dados.total_contacted),
            func.sum(Dados.emails_sent),
            func.sum(Dados.delivered),
            func.sum(Dados.email_opens),
            func.sum(Dados.links_clicks),
            func.sum(Dados.email_replies),
        ).filter(Dados.conta == conta)
        query_avancos = session.query(Avanco.data, func.sum(Avanco.quantidade)).filter(Avanco.conta == conta)
        if inicio and fim:
            query_dados = query_dados.filter(Dados.data.between(inicio, fim))
            query_avancos = query_avancos.filter(Avanco.data.between(inicio, fim))

        linhas_dados = query_dados.group_by(Dados.data).order_by(Dados.data).all()
        linhas_avancos = query_avancos.group_by(Avanco.data).all()

    avancos_por_dia = {data: int(qtd) for data, qtd in linhas_avancos}
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
            "avancos": avancos_por_dia.get(data, 0),
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
    with Session(get_engine()) as session:
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