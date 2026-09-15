import os
from flask import Flask, render_template, request, jsonify
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from marshmallow import Schema, fields, validate, ValidationError, pre_load

from decoder import Decoder, carregar_dic, carregar_freq

# --- App ---
app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-fallback-nao-use-em-prod')

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

# --- Segurança: cabeçalhos HTTP ---
# CSP desativado para não bloquear os <script>/<style> inline do index.html.
# Os outros cabeçalhos (X-Frame-Options, X-Content-Type-Options, HSTS, etc.)
# continuam sendo aplicados automaticamente.
Talisman(
    app,
    force_https=False,
    content_security_policy=None,
)

# --- Segurança: rate limiting ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "60 per hour"],
    storage_uri="memory://",
)

# --- Carregar dicionário uma vez ---
palavras = carregar_dic()
freq = carregar_freq()
dec = Decoder(palavras, freq=freq)

print(f"[dic]  {len(palavras)} palavras")
print(f"[freq] {len(freq)} palavras com frequência")


# --- Esquema de validação ---
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
    def limpar_limite(self, data, **kwargs):
        if isinstance(data, dict):
            v = data.get("limite")
            if v is None or (isinstance(v, str) and v.strip() == ""):
                data["limite"] = None
        return data


schema = DecodeRequestSchema()


# --- Rotas ---
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/decode", methods=["POST"])
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

    resposta = []
    for tok, matches in zip(tokens, listas):
        resposta.append({
            "token": tok,
            "total": len(matches),
            "matches": matches,
        })
    return jsonify({"tokens": resposta})


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"erro": "Muitas requisições. Tente novamente em instantes."}), 429


# --- Main (uso local) ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)