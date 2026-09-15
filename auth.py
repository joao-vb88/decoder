"""
Blueprint de autenticação + configurações de conta.

Rotas:
    /auth/login          — entrar (mostra landing com aba "Entrar")
    /auth/register       — criar conta (mostra landing com aba "Criar conta")
    /auth/logout         — sair
    /auth/account        — configurações da conta (perfil)
    /auth/change-password— trocar senha
    /auth/delete-account — apagar conta
"""

import re
from datetime import datetime
from functools import wraps

from flask import (
    Blueprint, render_template, request,
    redirect, url_for, session, g, flash,
)

from models import (
    criar_usuario, verificar_login, buscar_usuario,
    verificar_senha, atualizar_perfil, atualizar_senha, deletar_usuario,
)


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,20}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ============================================================
# Helpers
# ============================================================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Sessão válida E usuário existe no banco
        if "user_id" not in session or not getattr(g, "usuario", None):
            session.clear()
            return redirect(url_for("auth.login", next=request.path))
        return f(*args, **kwargs)
    return decorated


def usuario_atual():
    """Retorna o dict do usuário logado ou None."""
    uid = session.get("user_id")
    return buscar_usuario(uid) if uid else None


def carregar_usuario_em_g():
    """Hook chamado em cada request: guarda o usuário em flask.g."""
    g.usuario = usuario_atual()


def _safe_next(url):
    """Evita open redirect: só aceita caminhos internos."""
    if not url or not url.startswith("/") or url.startswith("//"):
        return "/"
    return url


# ============================================================
# Login / Register / Logout
# ============================================================

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    # Já logado? Vai direto pra home
    if session.get("user_id"):
        return redirect(url_for("raiz"))

    if request.method == "POST":
        username  = (request.form.get("username") or "").strip()
        email     = (request.form.get("email") or "").strip().lower()
        password  = request.form.get("password") or ""
        password2 = request.form.get("password2") or ""
        termos    = request.form.get("termos")

        erro = None
        if not USERNAME_RE.match(username):
            erro = "Usuário deve ter 3-20 caracteres (letras, números, _)."
        elif not EMAIL_RE.match(email):
            erro = "Email inválido."
        elif len(password) < 6:
            erro = "Senha deve ter pelo menos 6 caracteres."
        elif password != password2:
            erro = "As senhas não coincidem."
        elif not termos:
            erro = "Você precisa aceitar os termos."

        if erro:
            return render_template(
                "landing.html",
                aba="register",
                erro=erro,
                username=username,
                email=email,
            )

        ok, msg = criar_usuario(username, email, password)
        if not ok:
            return render_template(
                "landing.html",
                aba="register",
                erro=msg,
                username=username,
                email=email,
            )

        # Auto-login após registro
        user = verificar_login(username, password)
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        return redirect(url_for("raiz"))

    # GET
    return render_template("landing.html", aba="register")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # Já logado? Vai direto pra home
    if session.get("user_id"):
        return redirect(url_for("raiz"))

    if request.method == "POST":
        identificador = (request.form.get("identificador") or "").strip()
        password      = request.form.get("password") or ""
        lembrar       = request.form.get("lembrar")

        user = verificar_login(identificador, password)
        if user:
            session.permanent = bool(lembrar)
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(_safe_next(request.args.get("next")))

        return render_template(
            "landing.html",
            aba="login",
            erro="Usuário/email ou senha inválidos.",
            identificador=identificador,
        )

    # GET
    return render_template("landing.html", aba="login")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("raiz"))


# ============================================================
# Configurações da conta
# ============================================================

@auth_bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email    = (request.form.get("email") or "").strip().lower()

        erro = None
        if not USERNAME_RE.match(username):
            erro = "Usuário deve ter 3-20 caracteres (letras, números, _)."
        elif not EMAIL_RE.match(email):
            erro = "Email inválido."

        if erro:
            flash(erro, "erro")
        else:
            ok, msg = atualizar_perfil(session["user_id"], username, email)
            if ok:
                session["username"] = username
                flash("Perfil atualizado com sucesso.", "ok")
            else:
                flash(msg, "erro")

        return redirect(url_for("auth.account"))

    # Formata created_at pra exibir bonito (dd/mm/aaaa)
    if g.usuario and g.usuario.get("created_at"):
        try:
            dt = datetime.strptime(g.usuario["created_at"], "%Y-%m-%d %H:%M:%S")
            g.usuario["created_at"] = dt.strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            pass

    return render_template("account.html")


@auth_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    atual = request.form.get("atual") or ""
    nova  = request.form.get("nova") or ""
    nova2 = request.form.get("nova2") or ""

    erro = None
    if not verificar_senha(session["user_id"], atual):
        erro = "Senha atual incorreta."
    elif len(nova) < 6:
        erro = "Nova senha deve ter pelo menos 6 caracteres."
    elif nova != nova2:
        erro = "As senhas não coincidem."

    if erro:
        flash(erro, "erro")
    else:
        atualizar_senha(session["user_id"], nova)
        flash("Senha alterada com sucesso.", "ok")

    return redirect(url_for("auth.account"))


@auth_bp.route("/delete-account", methods=["POST"])
@login_required
def delete_account():
    senha       = request.form.get("senha") or ""
    confirmacao = request.form.get("confirmacao") or ""

    if not verificar_senha(session["user_id"], senha):
        flash("Senha incorreta.", "erro")
        return redirect(url_for("auth.account"))

    if confirmacao != "APAGAR":
        flash('Digite exatamente "APAGAR" para confirmar.', "erro")
        return redirect(url_for("auth.account"))

    deletar_usuario(session["user_id"])
    session.clear()
    flash("Sua conta foi apagada.", "ok")
    return redirect(url_for("raiz"))