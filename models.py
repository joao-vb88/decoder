"""
Banco de dados SQLite para usuários.

Simples, sem ORM. Usa o módulo sqlite3 nativo do Python.
"""

import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")


# ============================================================
# Conexão
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


# ============================================================
# Criação / busca
# ============================================================

def criar_usuario(username, email, password):
    """Retorna (True, None) em sucesso ou (False, mensagem)."""
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, generate_password_hash(password)),
            )
            conn.commit()
        return True, None
    except sqlite3.IntegrityError as e:
        msg = str(e).lower()
        if "username" in msg:
            return False, "Este usuário já está em uso."
        if "email" in msg:
            return False, "Este email já está cadastrado."
        return False, "Erro ao criar conta."


def verificar_login(identificador, password):
    """Aceita username OU email. Retorna dict do usuário ou None."""
    with get_db() as conn:
        row = conn.execute(
            """SELECT id, username, email, password_hash
               FROM users
               WHERE username = ? OR email = ?""",
            (identificador, identificador),
        ).fetchone()
    if row and check_password_hash(row["password_hash"], password):
        return {"id": row["id"], "username": row["username"], "email": row["email"]}
    return None


def buscar_usuario(user_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def verificar_senha(user_id, password):
    with get_db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return bool(row) and check_password_hash(row["password_hash"], password)


# ============================================================
# Atualização
# ============================================================

def atualizar_perfil(user_id, username, email):
    """Retorna (True, None) ou (False, mensagem)."""
    try:
        with get_db() as conn:
            conn.execute(
                "UPDATE users SET username = ?, email = ? WHERE id = ?",
                (username, email, user_id),
            )
            conn.commit()
        return True, None
    except sqlite3.IntegrityError as e:
        msg = str(e).lower()
        if "username" in msg:
            return False, "Este usuário já está em uso."
        if "email" in msg:
            return False, "Este email já está cadastrado."
        return False, "Erro ao atualizar."


def atualizar_senha(user_id, nova_senha):
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (generate_password_hash(nova_senha), user_id),
        )
        conn.commit()


def deletar_usuario(user_id):
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()