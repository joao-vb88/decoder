import os
from flask import Flask, render_template, request, jsonify
from decoder import Decoder, carregar_dic, carregar_freq

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-fallback-nao-use-em-prod')
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

# Carrega uma vez só (na inicialização do servidor)
palavras = carregar_dic()
freq = carregar_freq()
dec = Decoder(palavras, freq=freq)

print(f"[dic]  {len(palavras)} palavras")
print(f"[freq] {len(freq)} palavras com frequência")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/decode", methods=["POST"])
def decode():
    data = request.get_json(silent=True) or {}
    frase = (data.get("frase") or "").strip()
    limite = data.get("limite")  # None ou int
    try:
        limite = int(limite) if limite not in (None, "", "0") else None
    except (TypeError, ValueError):
        limite = None

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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)