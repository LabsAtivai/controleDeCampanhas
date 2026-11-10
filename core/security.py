import json
import os
import re
import secrets
from datetime import datetime, timedelta
from core.time import utcnow
from functools import wraps

from flask import g, jsonify, request, session
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from core.config import enabled
from db.models import AuditEvent, LoginAttempt, User
from db.session import engine

DUMMY_HASH = generate_password_hash('constant-timing-fallback')


def redact(value):
    value = str(value)
    for name in ('PAINEL_TOKEN', 'CREDENTIALS_API_KEY', 'SENDGRID_API_KEY', 'SECRET_KEY', 'DATABASE_URL', 'LISTAS_SQUAD_DATABASE_URL', 'AVANCOS_API_KEY'):
        secret = os.getenv(name, '')
        if secret:
            value = value.replace(secret, '[REDACTED]')
    value = re.sub(r'(?i)(access_token|client_secret|password|senha)([=:\s]+)[^\s&,;]+', r'\1\2[REDACTED]', value)
    return re.sub(r'://[^/\s@]+:[^/\s@]+@', '://[REDACTED]@', value)


def audit(actor, action, details=None):
    with Session(engine) as db:
        db.add(AuditEvent(actor=actor, action=action, details=json.dumps(details or {}, ensure_ascii=False), created_at=utcnow()))
        db.commit()


def save_user(email, password, role='viewer', active=True):
    email = str(email).strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email) > 255:
        raise ValueError('E-mail inválido.')
    if role not in {'admin', 'viewer'}:
        raise ValueError('Perfil inválido.')
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise ValueError('A senha deve ter entre 12 e 128 caracteres.')
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == email))
        if user:
            if user.role == 'admin' and user.active and (role != 'admin' or not active):
                count = db.scalar(select(func.count()).select_from(User).where(User.role == 'admin', User.active.is_(True)))
                if count <= 1:
                    raise ValueError('Mantenha pelo menos um administrador ativo.')
            user.password_hash = generate_password_hash(password)
            user.role, user.active = role, active
            user.session_version += 1
        else:
            db.add(User(email=email, password_hash=generate_password_hash(password), role=role,
                        active=active, created_at=utcnow()))
        db.commit()
    audit('management', 'user.saved', {'email': email, 'role': role, 'active': active})


def login(email, password):
    if not isinstance(email, str) or not isinstance(password, str) or len(email) > 255 or len(password) > 128:
        return None, 400
    email = email.strip().lower()
    ip = request.remote_addr or 'unknown'
    now = utcnow()
    with Session(engine) as db:
        db.query(LoginAttempt).filter(LoginAttempt.created_at < now - timedelta(days=1)).delete()
        attempts = db.scalar(select(func.count()).select_from(LoginAttempt).where(
            LoginAttempt.created_at >= now - timedelta(minutes=15),
            or_(LoginAttempt.identity == email, LoginAttempt.ip == ip)))
        if attempts >= 10:
            db.commit()
            return None, 429
        user = db.scalar(select(User).where(User.email == email))
        dummy = DUMMY_HASH if not user else user.password_hash
        correct = check_password_hash(dummy, password)
        if not user or not correct or not user.active:
            db.add(LoginAttempt(identity=email, ip=ip, created_at=now))
            db.commit()
            return None, 401
        session.clear()
        session.update(user_id=user.id, version=user.session_version, csrf=secrets.token_urlsafe(32))
        session.permanent = True
        result = {'email': user.email, 'role': user.role, 'csrf': session['csrf']}
        db.commit()
    audit(email, 'auth.login')
    return result, 200


def require_user(admin=False):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            legacy = request.headers.get('X-API-Token', '')
            configured = os.getenv('PAINEL_TOKEN', '')
            if enabled('ALLOW_LEGACY_TOKEN') and legacy and configured and secrets.compare_digest(legacy, configured):
                g.actor, g.role = 'legacy-token', 'admin'
            else:
                with Session(engine) as db:
                    user = db.get(User, session.get('user_id')) if session.get('user_id') else None
                    if not user or not user.active or user.session_version != session.get('version'):
                        session.clear()
                        return jsonify(error='Entre com sua conta para continuar.'), 401
                    g.actor, g.role = user.email, user.role
                if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
                    csrf = request.headers.get('X-CSRF-Token', '')
                    if not csrf or not secrets.compare_digest(csrf, session.get('csrf', '')):
                        return jsonify(error='Sessão inválida. Atualize a página.'), 403
            if admin and g.role != 'admin':
                return jsonify(error='Esta ação exige perfil administrador.'), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
