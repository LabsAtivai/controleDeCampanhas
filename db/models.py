from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey, Index, Text, Boolean
from sqlalchemy.dialects.mysql import LONGTEXT

LargeText = Text().with_variant(LONGTEXT(), 'mysql')

Base = declarative_base()

class Dados(Base):
    __tablename__ = "dados"
    __table_args__ = (Index('uq_dados_campaign_day', 'id_conta', 'data', unique=True),
                      Index('ix_dados_conta_data', 'conta', 'data'), Index('ix_dados_data', 'data'))

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
    __table_args__ = (Index('uq_avancos_conta_data', 'conta', 'data', unique=True),)

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
    source_json = Column(Text, nullable=True)
    sincronizado_em = Column(DateTime, nullable=False)


class User(Base):
    __tablename__ = 'painel_users'
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default='viewer')
    active = Column(Boolean, nullable=False, default=True)
    session_version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False)


class LoginAttempt(Base):
    __tablename__ = 'painel_login_attempts'
    id = Column(Integer, primary_key=True)
    identity = Column(String(255), nullable=False, index=True)
    ip = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, index=True)


class Job(Base):
    __tablename__ = 'painel_jobs'
    id = Column(String(36), primary_key=True)
    action = Column(String(100), nullable=False)
    params = Column(Text, nullable=False, default='{}')
    actor = Column(String(255), nullable=False)
    schedule_key = Column(String(100), unique=True, nullable=True)
    status = Column(String(20), nullable=False, default='queued', index=True)
    created_at = Column(DateTime, nullable=False, index=True)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    heartbeat_at = Column(DateTime)
    result = Column(LargeText)
    error = Column(Text)


class JobLog(Base):
    __tablename__ = 'painel_job_logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), ForeignKey('painel_jobs.id'), nullable=False, index=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)


class RunLease(Base):
    __tablename__ = 'painel_run_lease'
    id = Column(Integer, primary_key=True)
    owner = Column(String(36))
    expires_at = Column(DateTime, nullable=False)


class AuditEvent(Base):
    __tablename__ = 'painel_audit'
    id = Column(Integer, primary_key=True)
    actor = Column(String(255), nullable=False)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=False, default='{}')
    created_at = Column(DateTime, nullable=False, index=True)


class IntegrationCache(Base):
    __tablename__ = 'painel_integration_cache'
    key = Column(String(64), primary_key=True)
    value = Column(LargeText, nullable=False)
    updated_at = Column(DateTime, nullable=False, index=True)


class SchemaMigration(Base):
    __tablename__ = 'painel_schema_migrations'
    version = Column(String(50), primary_key=True)
    applied_at = Column(DateTime, nullable=False)


class DataRepair(Base):
    __tablename__ = 'painel_data_repairs'
    id = Column(Integer, primary_key=True)
    source_table = Column(String(50), nullable=False)
    source_id = Column(Integer, nullable=False)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)


class SquadMapping(Base):
    __tablename__ = 'painel_squad_mapping'
    campanha_id = Column(String(350), primary_key=True)
    squad = Column(String(100), nullable=False)


class ClientAlias(Base):
    __tablename__ = 'painel_client_aliases'
    alias = Column(String(255), primary_key=True)
    canonical = Column(String(255), nullable=False)
