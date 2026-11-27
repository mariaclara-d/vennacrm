import hashlib
import os
import re
import secrets
import time
from datetime import timedelta
from urllib.parse import urlsplit

import click
from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for
from flask.cli import with_appcontext
from sqlalchemy import case, delete, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from werkzeug.security import check_password_hash, generate_password_hash

from .models import Base, LoginAttempt, User, utc_now

auth = Blueprint("auth", __name__)
PASSWORD_METHOD = "scrypt:131072:8:1"
EMAIL_PATTERN = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")
DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(32), method=PASSWORD_METHOD)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def add_attempt(key, window):
    table = LoginAttempt.__table__
    insert = postgres_insert if g.db.bind.dialect.name == "postgresql" else sqlite_insert
    command = insert(table).values(key=digest(key), window=window, attempts=1)
    return g.db.execute(command.on_conflict_do_update(
        index_elements=[table.c.key],
        set_={
            "window": window,
            "attempts": case((table.c.window == window, table.c.attempts + 1), else_=1),
        },
    ).returning(table.c.attempts)).scalar_one()


def login_rate_limited(email):
    window = int(time.time() // 900)
    ip_count = add_attempt(f"ip:{request.remote_addr}", window)
    email_count = add_attempt(f"account:{email}", window) if ip_count <= 40 else 0
    g.db.execute(delete(LoginAttempt).where(LoginAttempt.window < window - 2))
    g.db.commit()
    return ip_count > 40 or email_count > 10


def sign_in(user):
    session.clear()
    session.permanent = True
    session.update(user_id=user.id, auth_version=user.auth_version)


@auth.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("crm.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().casefold()[:254]
        password = request.form.get("password", "")
        if login_rate_limited(email):
            flash("Muitas tentativas. Aguarde alguns minutos e tente novamente.", "error")
            return render_template("auth.html", mode="login"), 429
        user = g.db.scalar(select(User).where(User.email == email))
        stored_hash = user.password_hash if user and user.active and user.password_hash else DUMMY_HASH
        valid_password = len(password) <= 256 and check_password_hash(stored_hash, password)
        if valid_password and user and user.active and user.password_hash:
            g.db.execute(delete(LoginAttempt).where(LoginAttempt.key == digest(f"account:{email}")))
            g.db.commit()
            sign_in(user)
            return redirect(url_for("crm.dashboard"))
        flash("E-mail ou senha inválidos.", "error")
        return render_template("auth.html", mode="login"), 401
    return render_template("auth.html", mode="login")


@auth.route("/ativar", methods=["GET", "POST"])
def activate():
    if request.method == "POST":
        token = request.form.get("token", "")
        if not TOKEN_PATTERN.fullmatch(token):
            return render_template("error.html", code=400, message="Convite inválido ou expirado."), 400
        password = request.form.get("password", "")
        confirmation = request.form.get("confirmation", "")
        if not 15 <= len(password) <= 256 or password != confirmation:
            flash("Use uma senha de 15 a 256 caracteres e repita a mesma senha.", "error")
            return render_template("auth.html", mode="activate"), 400
        now = utc_now()
        token_hash = digest(token)
        account = g.db.scalar(select(User.id).where(
            User.invitation_hash == token_hash, User.invitation_expires > now, User.active,
        ))
        if account is not None:
            password_hash = generate_password_hash(password, method=PASSWORD_METHOD)
            changed = g.db.execute(update(User).where(
                User.id == account, User.invitation_hash == token_hash, User.invitation_expires > utc_now(), User.active,
            ).values(
                invitation_hash=None, invitation_expires=None, password_hash=password_hash,
                auth_version=User.auth_version + 1,
            ))
            if changed.rowcount == 1:
                g.db.commit()
                session.clear()
                flash("Senha definida. Entre com seu e-mail para acessar o CRM.", "success")
                return redirect(url_for("auth.login"))
        return render_template("error.html", code=400, message="Convite inválido ou expirado."), 400
    return render_template("auth.html", mode="activate")


@auth.post("/sair")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@click.command("init-db")
@with_appcontext
def init_db():
    """Cria as tabelas do CRM."""
    with current_app.extensions["venna_db"]() as db:
        Base.metadata.create_all(db.bind)
        from sqlalchemy import text, inspect
        inspector = inspect(db.bind)
        if "users" in inspector.get_table_names():
            cols = [c["name"] for c in inspector.get_columns("users")]
            if "role" not in cols:
                db.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"))
                db.commit()
    click.echo("Banco de dados inicializado.")


@click.command("invite")
@click.option("--email", prompt="E-mail da conta")
@click.option("--name", prompt="Nome da pessoa")
@click.option("--reset", is_flag=True, help="Reemite o convite para uma conta já ativada.")
@with_appcontext
def invite(email, name, reset):
    """Gera um convite individual válido por 24 horas."""
    email, name = email.strip().casefold(), name.strip()
    if not EMAIL_PATTERN.fullmatch(email) or len(email) > 254 or not 1 <= len(name) <= 100:
        raise click.ClickException("Informe um e-mail e um nome válidos.")
    base_url = os.getenv("VENNA_BASE_URL", "").rstrip("/")
    parsed = urlsplit(base_url)
    local = (not current_app.config["SESSION_COOKIE_SECURE"]
             and parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"})
    if not parsed.hostname or parsed.username or parsed.path or parsed.query or parsed.fragment or not (
        parsed.scheme == "https" or local
    ):
        raise click.ClickException("Configure VENNA_BASE_URL com a origem do CRM.")
    token = secrets.token_urlsafe(32)
    with current_app.extensions["venna_db"]() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user and (not user.active or user.password_hash and not reset):
            raise click.ClickException("Conta existente. Para redefinir uma conta ativa, use --reset.")
        if not user:
            user = User(email=email, name=name)
            db.add(user)
        user.invitation_hash = digest(token)
        user.invitation_expires = utc_now() + timedelta(hours=24)
        db.commit()
    click.echo(f"Convite individual (24 h): {base_url}/ativar#convite={token}")


@click.command("disable-account")
@click.argument("email")
@with_appcontext
def disable_account(email):
    """Revoga uma conta e as sessões associadas."""
    with current_app.extensions["venna_db"]() as db:
        user = db.scalar(select(User).where(User.email == email.strip().casefold()))
        if not user:
            raise click.ClickException("Conta não encontrada.")
        user.active = False
        user.auth_version += 1
        user.invitation_hash = None
        user.invitation_expires = None
        db.commit()
    click.echo("Conta desativada.")


commands = (init_db, invite, disable_account)
