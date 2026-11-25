import os
from datetime import timedelta
from urllib.parse import urlsplit

from flask import Flask, g, redirect, render_template, request, session, url_for
from flask_wtf.csrf import CSRFError, CSRFProtect
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from .models import User
from .quotes import date_label, local_datetime, money, number_input, quantity_text, quote_number


def create_app(config=None):
    app = Flask(__name__)
    db_url = os.getenv("VENNA_DATABASE_URL", "sqlite:///instance/venna.sqlite3")
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
    elif db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
    app.config.update(
        SECRET_KEY=os.getenv("VENNA_SECRET_KEY"),
        DATABASE_URL=db_url,
        SESSION_COOKIE_NAME="venna_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=os.getenv("VENNA_LOCAL_HTTP") != "1",
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_REFRESH_EACH_REQUEST=False,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAX_CONTENT_LENGTH=64 * 1024,
        MAX_FORM_MEMORY_SIZE=64 * 1024,
        MAX_FORM_PARTS=250,
    )
    if config:
        app.config.update(config)
    base_hostname = urlsplit(os.getenv("VENNA_BASE_URL", "")).hostname
    if base_hostname and app.config["SESSION_COOKIE_SECURE"] and not app.config["TRUSTED_HOSTS"]:
        app.config["TRUSTED_HOSTS"] = [base_hostname]
    if not app.config["SECRET_KEY"] or len(app.config["SECRET_KEY"]) < 32:
        raise RuntimeError("Configure VENNA_SECRET_KEY com pelo menos 32 caracteres aleatórios.")
    if app.config["DATABASE_URL"] == "sqlite:///instance/venna.sqlite3":
        os.makedirs("instance", exist_ok=True)
    engine = create_engine(app.config["DATABASE_URL"], pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    app.extensions["venna_db"] = sessionmaker(bind=engine, expire_on_commit=False)
    CSRFProtect(app)

    @app.before_request
    def load_user():
        if request.endpoint == "static":
            return
        g.db = app.extensions["venna_db"]()
        g.user = None
        if "user_id" in session:
            user = g.db.get(User, session["user_id"])
            if user and user.active and user.auth_version == session.get("auth_version"):
                g.user = user
            else:
                session.clear()
        if not g.user and request.blueprint == "crm":
            return redirect(url_for("auth.login"))

    @app.teardown_request
    def close_db(_error):
        db = g.pop("db", None)
        if db:
            db.close()

    @app.after_request
    def secure_response(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'self'"
        )
        if app.config["SESSION_COOKIE_SECURE"]:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(CSRFError)
    def csrf_expired(_error):
        return render_template("error.html", code=400,
                               message="A sessão do formulário expirou. Volte à página e tente de novo."), 400

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="Esta página não está disponível."), 404

    @app.errorhandler(409)
    def conflict(_error):
        return render_template("error.html", code=409,
                               message="Este registro mudou em outra sessão. Abra a página novamente antes de editar."), 409

    app.jinja_env.filters.update(
        money=money, quantity=quantity_text, number_input=number_input,
        brdate=date_label, local=local_datetime, quote_number=quote_number,
    )
    from .auth import auth, commands
    from .crm import crm

    app.register_blueprint(auth)
    app.register_blueprint(crm)
    for command in commands:
        app.cli.add_command(command)
    return app
