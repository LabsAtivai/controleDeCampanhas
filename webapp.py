"""Same-origin web application. Schema creation and job execution are separate commands."""
import json
import os
from urllib.parse import urlparse
from datetime import datetime, timedelta
from core.time import utcnow

from flask import Flask, g, jsonify, redirect, request, send_from_directory, session
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from core.config import ROOT, enabled
from core.security import audit, login, require_user, save_user
from core.validation import iso_date, json_object, period
from core import jobs
from db import avancos_api, crud, dashboard
from db.models import AuditEvent, Job, JobLog, User, RunLease
from db.session import engine


def create_app(test_config=None):
    app = Flask(__name__, static_folder=str(ROOT / 'painel-frontend'), static_url_path='/assets')
    app.config.update(SECRET_KEY=os.getenv('SECRET_KEY'), SESSION_COOKIE_NAME='ativa_session',
        SESSION_COOKIE_SECURE=enabled('COOKIE_SECURE', True), SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Strict', PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAX_CONTENT_LENGTH=64 * 1024)
    if test_config:
        app.config.update(test_config)
    if not app.config['SECRET_KEY'] or len(app.config['SECRET_KEY']) < 32:
        raise RuntimeError('Configure SECRET_KEY aleatória com pelo menos 32 caracteres.')
    if enabled('TRUST_PROXY'):
        # Enable only behind a trusted reverse proxy; never publish the API directly.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    @app.before_request
    def begin():
        avancos_api.begin_request()

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        if request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(ValueError)
    def bad_input(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(Exception)
    def error(error):
        if isinstance(error, HTTPException):
            return jsonify(error=error.description), error.code
        # No credentials, URLs, DB tracebacks or upstream payloads in responses.
        app.logger.error('Request failed: %s %s [%s]', request.method, request.path, type(error).__name__)
        return jsonify(error='Não foi possível concluir a operação. Consulte o histórico e a prontidão do serviço.'), 503

    @app.get('/')
    def root():
        return redirect('/dados.html')

    @app.get('/<page>.html')
    def page(page):
        if page not in {'index', 'dados', 'analise', 'login', 'equipe'}:
            return jsonify(error='Página não encontrada.'), 404
        return send_from_directory(app.static_folder, page + '.html')

    @app.get('/api/health')
    def health():
        return jsonify(ok=True)

    @app.get('/api/ready')
    def readiness():
        from db.migrations import ready
        try:
            ok = ready()
        except Exception:
            ok = False
        return jsonify(ok=ok, database=ok, schema=ok), 200 if ok else 503

    @app.post('/api/auth/login')
    def auth_login():
        origin = request.headers.get('Origin')
        if origin:
            public_domain = os.getenv('PUBLIC_DOMAIN', '').strip().rstrip('/')
            if public_domain:
                configured = public_domain if '://' in public_domain else (
                    ('https://' if enabled('COOKIE_SECURE', True) else f'{request.scheme}://') + public_domain
                )
                parsed = urlparse(configured)
                expected_origin = f'{parsed.scheme}://{parsed.netloc}'
            else:
                expected_origin = request.host_url.rstrip('/')
            if origin.rstrip('/') != expected_origin:
                return jsonify(error='Origem inválida.'), 403
        body = json_object(request)
        user, code = login(body.get('email'), body.get('password'))
        if not user:
            return jsonify(error='Muitas tentativas. Aguarde 15 minutos.' if code == 429 else 'E-mail ou senha inválidos.'), code
        return jsonify(user)

    @app.get('/api/auth/me')
    @require_user()
    def me():
        return jsonify(email=g.actor, role=g.role, csrf=session.get('csrf'),
            avancosUrl=os.getenv('AVANCOS_FRONTEND_URL', ''), semaforoTipos=os.getenv('SEMAFORO_TIPOS', 'Interessado'))

    @app.post('/api/auth/logout')
    @require_user()
    def logout():
        audit(g.actor, 'auth.logout')
        session.clear()
        return jsonify(ok=True)

    @app.get('/api/users')
    @require_user(admin=True)
    def users():
        with Session(engine) as db:
            return jsonify([{'id': u.id, 'email': u.email, 'role': u.role, 'active': u.active}
                for u in db.scalars(select(User).order_by(User.email))])

    @app.post('/api/users')
    @require_user(admin=True)
    def user_save():
        body = json_object(request)
        email, role, active = body.get('email'), body.get('role', 'viewer'), body.get('active', True)
        if isinstance(email, str):
            email = email.strip().lower()
        if type(active) is not bool:
            raise ValueError('active precisa ser booleano.')
        if email == g.actor and (not active or role != 'admin'):
            raise ValueError('Você não pode retirar seu próprio acesso administrativo.')
        save_user(email, body.get('password'), role, active)
        audit(g.actor, 'user.updated', {'email': email, 'role': role, 'active': active})
        return jsonify(saved=True), 201

    @app.get('/api/audit')
    @require_user(admin=True)
    def events():
        with Session(engine) as db:
            return jsonify([{'id': e.id, 'actor': e.actor, 'action': e.action, 'details': json.loads(e.details),
                'createdAt': e.created_at.isoformat() + 'Z'} for e in db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(200))])

    @app.get('/api/jobs')
    @require_user(admin=True)
    def history():
        return jsonify(jobs.list_jobs())

    @app.get('/api/config/status')
    @require_user(admin=True)
    def configuration():
        from core.config import integration_url
        integrations = []
        for label, url_key, key_name in [('Contas e credenciais', 'CREDENTIALS_API_URL', 'CREDENTIALS_API_KEY'),
                                       ('Indicadores de avanços', 'AVANCOS_API_URL', None)]:
            value = os.getenv(url_key)
            message, ok = 'Configurado; valide com uma coleta controlada.', True
            if not value or (key_name and not os.getenv(key_name)):
                ok, message = False, 'Configuração de conexão incompleta.'
            else:
                try:
                    integration_url(value)
                except ValueError:
                    ok, message = False, 'A URL precisa de HTTPS ou de rede privada.'
            integrations.append({'name': label, 'configured': ok, 'message': message})
        integrations.append({'name': 'Registro de avanços', 'configured': bool(os.getenv('AVANCOS_FRONTEND_URL')),
            'message': 'Destino configurado.' if os.getenv('AVANCOS_FRONTEND_URL') else 'Endereço do sistema oficial ainda não configurado.'})
        sheets = enabled('GOOGLE_SHEETS_ENABLED', True)
        integrations.append({'name': 'Google Sheets', 'configured': bool(sheets and os.getenv('GOOGLE_MASTER_SHEET_ID')),
            'message': 'Publicação habilitada; valide acesso à planilha.' if sheets else 'Publicação desabilitada neste ambiente.'})
        return jsonify(integrations=integrations)

    @app.post('/api/jobs/<job_id>/retry')
    @require_user(admin=True)
    def retry(job_id):
        with Session(engine) as db:
            previous = db.get(Job, job_id)
            if not previous or previous.status not in {'partial', 'failed', 'interrupted'}:
                raise ValueError('Somente execuções com falha, parciais ou interrompidas podem ser reprocessadas.')
            action, params = previous.action, json.loads(previous.params)
        new_id = jobs.enqueue(action, params, g.actor)
        return jsonify(job_id=new_id, queued=True), 202

    @app.get('/api/status')
    @require_user(admin=True)
    def status():
        history = jobs.list_jobs(100)
        current = next((j for j in history if j['status'] == 'running'), history[0] if history else None)
        with Session(engine) as db:
            lease = db.get(RunLease, 1)
            worker_online = bool(lease and lease.expires_at >= utcnow() - timedelta(minutes=2))
        return jsonify(running=bool(current and current['status'] == 'running'),
            action=current['action'] if current else None, started_at=current['started_at'] if current else None,
            finished_at=current['finished_at'] if current else None,
            success=(current['status'] == 'completed') if current and current['status'] in jobs.TERMINAL else None,
            status=current['status'] if current else 'idle', error=current['error'] if current else None,
            queued=sum(j['status'] == 'queued' for j in history), job=current, worker_online=worker_online)

    @app.get('/api/logs')
    @require_user(admin=True)
    def logs():
        try:
            since = int(request.args.get('since', '0'))
        except (ValueError, TypeError):
            raise ValueError('Cursor inválido.') from None
        if since < 0:
            raise ValueError('Cursor inválido.')
        with Session(engine) as db:
            maximum = db.scalar(select(func.max(JobLog.id))) or 0
            reset = since > maximum
            query = select(JobLog).where(JobLog.id > (0 if reset else since)).order_by(JobLog.id).limit(500)
            if request.args.get('job_id'):
                query = query.where(JobLog.job_id == request.args['job_id'])
            rows = db.scalars(query).all()
            cursor = rows[-1].id if rows else (0 if reset else since)
            return jsonify(total=cursor, cursor=cursor, reset=reset,
                lines=[f'{r.created_at.isoformat()}Z [{r.job_id[:8]}] {r.message}' for r in rows])

    @app.post('/api/run/<action>')
    @require_user(admin=True)
    def run(action):
        params = {}
        if action == 'campanhas-selecionadas':
            body = json_object(request)
            ids = body.get('ids')
            if not isinstance(ids, list) or not 1 <= len(ids) <= 1000 or any(not isinstance(i, str) or not 1 <= len(i) <= 36 for i in ids):
                raise ValueError('Informe uma lista de 1 a 1000 ids de conta válidos.')
            params, action = {'ids': sorted(set(ids))}, 'campanhas'
        elif action == 'custom':
            body = json_object(request)
            start = body.get('inicio') or body.get('data')
            end = body.get('fim') or start
            if not start:
                raise ValueError('Informe inicio e fim ou data.')
            first, last = period(start, end, max_days=31)
            if last >= avancos_api.hoje_sp():
                raise ValueError('Selecione somente dias fechados, anteriores a hoje.')
            params = {'inicio': first.isoformat(), 'fim': last.isoformat()}
        elif action not in {'campanhas', 'dia-anterior', 'planilhas', 'diario'}:
            raise ValueError('Ação desconhecida.')
        with Session(engine) as db:
            if db.scalar(select(func.count()).select_from(Job).where(Job.status.in_(['queued', 'running']))) >= 20:
                return jsonify(error='Fila cheia; aguarde as execuções atuais.'), 409
        job_id = jobs.enqueue(action, params, g.actor)
        return jsonify(started=True, queued=True, job_id=job_id), 202

    @app.get('/api/clientes')
    @require_user(admin=True)
    def clients():
        # Local metadata mirror: selecting accounts never decrypts Snov secrets.
        from db.models import ContaSnovio
        with Session(engine) as db:
            return jsonify([{'id': c.id, 'email': c.email, 'emailSnovio': c.conta_snovio}
                for c in db.scalars(select(ContaSnovio).where(ContaSnovio.status == 'ACTIVE').order_by(ContaSnovio.email))])

    @app.get('/api/squads')
    @require_user()
    def squads():
        data = dashboard.get_squads_summary()
        return jsonify(squads=data, warnings=avancos_api.warnings(), geradoEm=utcnow().isoformat() + 'Z',
            metricScope='Última coleta por campanha; datas podem variar. Avanços de hoje.')

    @app.get('/api/analise-contas')
    @require_user()
    def accounts():
        start, end = request.args.get('inicio'), request.args.get('fim')
        period(start, end)
        data = dashboard.get_contas_resumo(start, end)
        return jsonify(squads=data, warnings=avancos_api.warnings(), geradoEm=utcnow().isoformat() + 'Z')

    @app.get('/api/analise-cliente')
    @require_user()
    def client_analysis():
        client = request.args.get('cliente') or request.args.get('conta')
        if not client or len(client) > 350:
            raise ValueError('Informe um cliente válido.')
        start, end = request.args.get('inicio'), request.args.get('fim')
        period(start, end)
        days = crud.get_analise_cliente(client, start, end)
        statuses = dashboard.optional(avancos_api.status_por_cliente)
        status = 'indisponivel' if statuses is None else statuses.get(avancos_api._norm(client), 'vermelho') if avancos_api.tem_vinculo(client) else 'sem_vinculo'
        return jsonify(cliente=client, dias=days, statusAvanco=status, warnings=avancos_api.warnings())

    @app.route('/api/avancos', methods=['GET', 'POST', 'DELETE'])
    @app.route('/api/avancos/<int:record_id>', methods=['DELETE'])
    @require_user()
    def retired_advances(record_id=None):
        return jsonify(error='Registre e consulte os avanços no sistema oficial.', url=os.getenv('AVANCOS_FRONTEND_URL', '')), 410

    return app
