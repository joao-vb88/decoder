"""
Decoder — API Flask para decifrar frases com teclas próximas.
"""

import os

from flask import Flask, render_template, request, jsonify, g, session
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, CSRFError
from marshmallow import Schema, fields, validate, ValidationError, pre_load

from decoder import Decoder, carregar_dic, carregar_freq
from models import init_db
from auth import auth_bp, carregar_usuario_em_g


# ============================================================
# Configuração
# ============================================================

app = Flask(__name__)

# Em produção o Render injeta SECRET_KEY. Em local, usa fallback.
IS_PRODUCTION = "SECRET_KEY" in os.environ

app.config['SECRET_KEY'] = os.environ.get(
    'SECRET_KEY', 'dev-fallback-nao-use-em-prod'
)

app.config.update(
    # Secure só em produção (em HTTP local o navegador descarta o cookie)
    SESSION_COOKIE_SECURE=IS_PRODUCTION,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 30,  # 30 dias
)


# ============================================================
# Segurança
# ============================================================

Talisman(
    app,
    force_https=False,
    content_security_policy=None,
)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "60 per hour"],
    storage_uri="memory://",
)

csrf = CSRFProtect(app)


# ============================================================
# Banco de dados + Autenticação
# ============================================================

init_db()
app.register_blueprint(auth_bp)


# Carrega o usuário logado em g, mas só quando faz sentido.
# Pula estáticos, service worker, favicon e /decode (API pública).
_ENDPOINTS_SEM_USUARIO = {"static", "service_worker", "favicon", "decode"}

@app.before_request
def before_req():
    if request.endpoint in _ENDPOINTS_SEM_USUARIO:
        return
    carregar_usuario_em_g()


@app.context_processor
def injetar_usuario():
    """Deixa {{ usuario }} disponível em todos os templates."""
    return {"usuario": getattr(g, "usuario", None)}


# ============================================================
# Dicionário
# ============================================================

palavras = carregar_dic()
freq = carregar_freq()
dec = Decoder(palavras, freq=freq)

print(f"[dic]  {len(palavras)} palavras")
print(f"[freq] {len(freq)} palavras com frequência")


# ============================================================
# Schema de validação
# ============================================================

class DecodeRequestSchema(Schema):
    frase = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=500),
    )
    limite = fields.Int(
        required=False,
        allow_none=True,
        validate=validate.Range(min=1, max=100),
    )

    @pre_load
    def normalizar_limite(self, data, **kwargs):
        if isinstance(data, dict):
            v = data.get("limite")
            if v is None or (isinstance(v, str) and v.strip() == ""):
                data["limite"] = None
        return data


schema = DecodeRequestSchema()


# ============================================================
# Rotas
# ============================================================

@app.route("/")
def raiz():
    """Landing se deslogado, decoder se logado."""
    # Só considera logado se o usuário REALMENTE existe no banco.
    # Se a sessão aponta pra um user_id que sumiu (banco resetado),
    # limpa a sessão e manda pra landing.
    if session.get("user_id"):
        if getattr(g, "usuario", None):
            return render_template("index.html")
        session.clear()
    return render_template("landing.html")


@app.route("/app")
def app_decoder():
    """Decoder acessível pra qualquer um (logado ou não)."""
    return render_template("index.html")


@app.route("/service-worker.js")
def service_worker():
    return app.send_static_file("service-worker.js")


@app.route("/favicon.ico")
def favicon():
    return app.send_static_file("icons/icon-192.png")


@app.route("/decode", methods=["POST"])
@csrf.exempt
@limiter.limit("30 per minute")
def decode():
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return jsonify({"erro": "Dados inválidos.", "detalhes": err.messages}), 400

    frase = data["frase"].strip()
    limite = data.get("limite")

    if not frase:
        return jsonify({"tokens": []})

    tokens = frase.split()
    listas = dec.decode(frase, limit=limite)

    resposta = [
        {"token": tok, "total": len(matches), "matches": matches}
        for tok, matches in zip(tokens, listas)
    ]
    return jsonify({"tokens": resposta})


# ============================================================
# Tratamento de erros
# ============================================================

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        "erro": "Muitas requisições. Tente novamente em instantes."
    }), 429


@app.errorhandler(CSRFError)
def csrf_error_handler(e):
    """Token CSRF inválido ou expirado."""
    # Se for /decode (API JSON), responde JSON
    if request.path == "/decode":
        return jsonify({"erro": "Token CSRF inválido ou expirado."}), 400
    # Senão, mostra a landing com a aba de login e aviso
    return render_template(
        "landing.html",
        aba="login",
        erro="Sessão expirada. Faça login novamente.",
    ), 400


# ============================================================
# Execução local
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)