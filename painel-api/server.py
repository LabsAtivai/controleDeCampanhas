import os
import secrets
import sys
import threading
from collections import deque
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Flask, jsonify, request

from db.session import create_tables
from db import dashboard, crud
from rotina import acao, credentials_api

create_tables()

app = Flask(__name__)

API_TOKEN = os.environ.get("PAINEL_TOKEN", "")
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "*")

LOG_BUFFER = deque(maxlen=5000)
LOG_LOCK = threading.Lock()

STATE = {
    "running": False,
    "action": None,
    "started_at": None,
    "finished_at": None,
    "success": None,
    "error": None,
}
STATE_LOCK = threading.Lock()
RUN_LOCK = threading.Lock()


class TeeStream:
    def __init__(self, original):
        self.original = original

    def write(self, text):
        self.original.write(text)
        if text.strip():
            with LOG_LOCK:
                LOG_BUFFER.append(text.rstrip("\n"))

    def flush(self):
        self.original.flush()


sys.stdout = TeeStream(sys.stdout)
sys.stderr = TeeStream(sys.stderr)


def require_token(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not API_TOKEN:
            return jsonify({"error": "PAINEL_TOKEN não configurado no servidor"}), 500
        token = request.headers.get("X-API-Token", "")
        if not secrets.compare_digest(token, API_TOKEN):
            return jsonify({"error": "token inválido"}), 401
        return fn(*args, **kwargs)

    return wrapper


@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = FRONTEND_ORIGIN
    resp.headers["Access-Control-Allow-Headers"] = "X-API-Token, Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    return resp


@app.route("/api/<path:_ignored>", methods=["OPTIONS"])
def options_handler(_ignored):
    return "", 204


def run_job(action_name, func):
    if not RUN_LOCK.acquire(blocking=False):
        return False

    def target():
        with STATE_LOCK:
            STATE.update(
                running=True,
                action=action_name,
                started_at=datetime.now().isoformat(),
                finished_at=None,
                success=None,
                error=None,
            )
        print(f"\n########## INÍCIO: {action_name} ##########")
        try:
            func()
            with STATE_LOCK:
                STATE["success"] = True
        except Exception as e:
            print(f"[ERRO] {action_name}: {e}")
            with STATE_LOCK:
                STATE["success"] = False
                STATE["error"] = str(e)
        finally:
            print(f"########## FIM: {action_name} ##########")
            with STATE_LOCK:
                STATE["running"] = False
                STATE["finished_at"] = datetime.now().isoformat()
            RUN_LOCK.release()

    threading.Thread(target=target, daemon=True).start()
    return True


def run_response(ok):
    if not ok:
        return jsonify({"error": "já existe um job em execução"}), 409
    return jsonify({"started": True})


@app.route("/api/health")
def health():
    return jsonify({"ok": True})


@app.route("/api/status")
@require_token
def status():
    with STATE_LOCK:
        return jsonify(dict(STATE))


@app.route("/api/logs")
@require_token
def logs():
    since = int(request.args.get("since", 0))
    with LOG_LOCK:
        lines = list(LOG_BUFFER)
    return jsonify({"total": len(lines), "lines": lines[since:]})


@app.route("/api/run/campanhas", methods=["POST"])
@require_token
def run_campanhas():
    return run_response(run_job("extrai_campanhas", acao.extrai_campanhas))


@app.route("/api/run/campanhas-selecionadas", methods=["POST"])
@require_token
def run_campanhas_selecionadas():
    body = request.get_json(silent=True) or {}
    ids = body.get("ids") or []
    if not ids:
        return jsonify({"error": "informe 'ids' (lista de ids de conta do sistema de credenciais)"}), 400

    def job():
        acao.extrai_campanhas(ids_selecionados=set(ids))

    label = f"extrai_campanhas(selecionados: {len(ids)})"
    return run_response(run_job(label, job))


@app.route("/api/clientes")
@require_token
def clientes():
    try:
        ativos = credentials_api.get_active_clients()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    # nunca expor client_secret/senha pro frontend
    safe = [{"id": c["id"], "email": c["email"], "emailSnovio": c["email_snovio"]} for c in ativos]
    return jsonify(safe)


@app.route("/api/squads")
@require_token
def squads():
    try:
        return jsonify({"squads": dashboard.get_squads_summary(), "geradoEm": datetime.now().isoformat()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/avancos", methods=["GET"])
@require_token
def listar_avancos():
    conta = request.args.get("conta")
    return jsonify(crud.lista_avancos(conta))


@app.route("/api/avancos", methods=["POST"])
@require_token
def criar_avanco():
    body = request.get_json(silent=True) or {}
    data = body.get("data")
    conta = body.get("conta")
    quantidade = body.get("quantidade")
    if not data or not conta or quantidade is None:
        return jsonify({"error": "informe 'data' (YYYY-MM-DD), 'conta' e 'quantidade'"}), 400
    try:
        quantidade = int(quantidade)
    except (TypeError, ValueError):
        return jsonify({"error": "'quantidade' precisa ser um número inteiro"}), 400
    try:
        datetime.strptime(data, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "'data' inválida, use YYYY-MM-DD"}), 400
    return jsonify(crud.cria_avanco(data, conta, quantidade)), 201


@app.route("/api/avancos/<int:avanco_id>", methods=["DELETE"])
@require_token
def deletar_avanco(avanco_id):
    if not crud.remove_avanco(avanco_id):
        return jsonify({"error": "avanço não encontrado"}), 404
    return jsonify({"deleted": True})


@app.route("/api/analise-cliente")
@require_token
def analise_cliente():
    conta = request.args.get("conta")
    inicio = request.args.get("inicio")
    fim = request.args.get("fim")
    if not conta:
        return jsonify({"error": "informe 'conta' (ex: abluo@ativa.ai)"}), 400
    try:
        return jsonify({"conta": conta, "dias": crud.get_analise_cliente(conta, inicio, fim)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/analise-contas")
@require_token
def analise_contas():
    inicio = request.args.get("inicio")
    fim = request.args.get("fim")
    try:
        return jsonify({"squads": dashboard.get_contas_resumo(inicio, fim), "geradoEm": datetime.now().isoformat()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/run/dia-anterior", methods=["POST"])
@require_token
def run_dia_anterior():
    return run_response(run_job("extrai_dia_anterior", acao.extrai_dia_anterior))


@app.route("/api/run/custom", methods=["POST"])
@require_token
def run_custom():
    body = request.get_json(silent=True) or {}
    inicio = body.get("inicio") or body.get("data")
    fim = body.get("fim") or inicio
    if not inicio:
        return jsonify({"error": "informe 'data' ou 'inicio'/'fim' (YYYY-MM-DD)"}), 400
    try:
        d_ini = datetime.strptime(inicio, "%Y-%m-%d").date()
        d_fim = datetime.strptime(fim, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "formato de data inválido, use YYYY-MM-DD"}), 400
    if d_fim < d_ini:
        return jsonify({"error": "'fim' não pode ser antes de 'inicio'"}), 400
    if (d_fim - d_ini).days > 31:
        return jsonify({"error": "intervalo máximo de 31 dias"}), 400

    def job():
        d = d_ini
        while d <= d_fim:
            print(f"\n=== Processando {d.isoformat()} ===")
            acao.extrai_dia_anterior_custom(d.isoformat())
            d += timedelta(days=1)

    label = f"extrai_custom({inicio}..{fim})"
    return run_response(run_job(label, job))


@app.route("/api/run/planilhas", methods=["POST"])
@require_token
def run_planilhas():
    return run_response(run_job("atualiza_planilhas_controle", acao.atualiza_planilhas_controle))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
