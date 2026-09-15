"""
Decoder — API Flask para decifrar frases com teclas próximas.

Endpoints:
    GET  /                    → página principal (PWA)
    GET  /service-worker.js   → service worker na raiz (obrigatório para PWA)
    GET  /favicon.ico         → evita 404 no navegador
    POST /decode              → decifra uma frase

Segurança:
    - SECRET_KEY via variável de ambiente
    - Cookies de sessão com Secure/HttpOnly/SameSite
    - Cabeçalhos HTTP via Flask-Talisman
    - Rate limiting via Flask-Limiter
    - Validação de entrada via Marshmallow
"""

import os

from flask import Flask, render_template, request, jsonify
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from marshmallow import Schema, fields, validate, ValidationError, pre_load

from decoder import Decoder, carregar_dic, carregar_freq


# ============================================================
# Configuração do app
# ============================================================

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get(
    'SECRET_KEY', 'dev-fallback-nao-use-em-prod'
)

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)


# ============================================================
# Segurança: cabeçalhos HTTP (Flask-Talisman)
# ============================================================
# CSP desativado porque o index.html usa <script> e <style> inline.
# Os demais cabeçalhos (X-Frame-Options, X-Content-Type-Options,
# Referrer-Policy, HSTS) continuam sendo aplicados automaticamente.

Talisman(
    app,
    force_https=False,
    content_security_policy=None,
)


# ============================================================
# Segurança: rate limiting (Flask-Limiter)
# ============================================================

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "60 per hour"],
    storage_uri="memory://",
)


# ============================================================
# Carregamento do dicionário (uma vez, na inicialização)
# ============================================================

palavras = carregar_dic()
freq = carregar_freq()
dec = Decoder(palavras, freq=freq)

print(f"[dic]  {len(palavras)} palavras")
print(f"[freq] {len(freq)} palavras com frequência")


# ============================================================
# Schema de validação (Marshmallow)
# ============================================================

class DecodeRequestSchema(Schema):
    """Valida o corpo JSON do endpoint /decode."""

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
        """Converte limite vazio ('') em None antes da validação."""
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
def index():
    """Página principal (PWA)."""
    return render_template("index.html")


@app.route("/service-worker.js")
def service_worker():
    """
    Serve o service worker na raiz do site.
    Precisa estar em /service-worker.js (não em /static/) para
    que o escopo padrão seja '/', controlando o site inteiro.
    """
    return app.send_static_file("service-worker.js")


@app.route("/favicon.ico")
def favicon():
    """Evita 404 no console do navegador."""
    return app.send_static_file("icons/icon-192.png")


@app.route("/decode", methods=["POST"])
@limiter.limit("30 per minute")
def decode():
    """Decifra uma frase e retorna os candidatos ordenados por frequência."""
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
        {
            "token": tok,
            "total": len(matches),
            "matches": matches,
        }
        for tok, matches in zip(tokens, listas)
    ]
    return jsonify({"tokens": resposta})


# ============================================================
# Tratamento de erros
# ============================================================

@app.errorhandler(429)
def ratelimit_handler(e):
    """Resposta JSON para o erro de rate limit (Too Many Requests)."""
    return jsonify({
        "erro": "Muitas requisições. Tente novamente em instantes."
    }), 429


# ============================================================
# Execução local
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)