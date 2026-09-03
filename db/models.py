from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey

Base = declarative_base()

class Dados(Base):
    __tablename__ = "dados"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conta = Column(String(350))
    campanha = Column(String(350))
    id_conta = Column(String(350))
    data = Column(String(350))
    total_contacted = Column(Integer)
    emails_sent = Column(Integer)
    delivered = Column(Integer)
    email_opens = Column(Integer)
    links_clicks = Column(Integer)
    email_replies = Column(Integer)


class ContaSnovio(Base):
    """Espelho leve das contas ativas do sistema de credenciais (id, e-mails,
    status). Sem segredo nenhum aqui — client_id/secret continuam só no
    sistema de credenciais. Mesmo papel da tabela homônima no painel_listas."""
    __tablename__ = "contas_snovio"

    id = Column(String(36), primary_key=True)  # id da conta no sistema de credenciais
    email = Column(String(255), nullable=False)
    conta_snovio = Column(String(255), nullable=False)  # e-mail de login do Snov.io
    status = Column(String(20), nullable=False, default="ACTIVE")
    sincronizado_em = Column(DateTime, nullable=False)


class Avanco(Base):
    """Quantidade de avanços por cliente/data — o time preenche na mão (não vem
    do Snov.io). Substitui a aba "Avanços" da planilha de controle."""
    __tablename__ = "avancos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(String(20), nullable=False)  # YYYY-MM-DD
    conta = Column(String(255), nullable=False)  # e-mail da conta Snov.io do cliente
    quantidade = Column(Integer, nullable=False)
    criado_em = Column(DateTime, nullable=False)


class Campanha(Base):
    """Cache das campanhas por conta (GET /v1/get-user-campaigns), atualizado a
    cada execução de extrai_campanhas(). Substitui a aba "campanhas" do Sheet
    de controle."""
    __tablename__ = "campanhas"

    id = Column(BigInteger, primary_key=True)  # id da campanha no Snov.io
    conta_id = Column(String(36), ForeignKey("contas_snovio.id"), nullable=False)
    nome = Column(String(500), nullable=False)
    list_id = Column(BigInteger, nullable=True)
    status_snovio = Column(String(50), nullable=True)
    sincronizado_em = Column(DateTime, nullable=False)