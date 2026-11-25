from datetime import datetime

from flask import Blueprint, abort, flash, g, redirect, render_template, request, send_file, url_for
from sqlalchemy import func, or_, select, update

from .models import Activity, Lead, Quote, Revision, Task, User, utc_now
from .pdf import quote_pdf
from .quotes import InvalidForm, LOCAL_TZ, parse_date, parse_quote, quote_number, text_field

crm = Blueprint("crm", __name__)
STAGES = {
    "new": "Novo",
    "contact": "Em atendimento",
    "quoted": "Orçamento enviado",
    "negotiating": "Em negociação",
    "won": "Fechado",
    "lost": "Perdido",
}
SOURCES = ("WhatsApp", "Instagram", "Indicação", "Site", "Prospecção", "Outro")
QUOTE_STATES = {"draft": "Rascunho", "sent": "Enviado", "accepted": "Aceito", "declined": "Recusado"}
TRANSITIONS = {"draft": ("sent",), "sent": ("accepted", "declined"), "accepted": (), "declined": ()}


@crm.context_processor
def labels():
    return dict(stages=STAGES, sources=SOURCES, quote_states=QUOTE_STATES)


def get_record(model, key):
    result = g.db.get(model, key)
    if result is None:
        abort(404)
    return result


def record_activity(lead_id, message):
    g.db.add(Activity(lead_id=lead_id, user_id=g.user.id, message=message))


def get_posted_version(name="version"):
    raw = request.form.get(name, "")
    if not raw.isascii() or not raw.isdigit() or not 1 <= len(raw) <= 9:
        abort(400)
    return int(raw)


@crm.get("/")
def dashboard():
    today = datetime.now(LOCAL_TZ).date()
    stage = request.args.get("stage", "")
    q = request.args.get("q", "").strip()[:100]
    page = request.args.get("page", 1, type=int)
    page = max(1, min(page, 100_000))
    filters = []
    if stage in STAGES:
        filters.append(Lead.stage == stage)
    if q:
        filters.append(or_(*(field.icontains(q, autoescape=True) for field in
                             (Lead.name, Lead.phone, Lead.email, Lead.city))))
    if request.args.get("retornos") == "1":
        filters.extend([Lead.followup <= today, Lead.stage.not_in(("won", "lost"))])
    leads = g.db.execute(select(Lead, User.name).outerjoin(User, User.id == Lead.assignee_id)
                         .where(*filters).order_by(Lead.created_at.desc(), Lead.id.desc())
                         .offset((page - 1) * 30).limit(31)).all()
    counts = dict(g.db.execute(select(Lead.stage, func.count()).group_by(Lead.stage)).all())
    due_count = g.db.scalar(select(func.count()).select_from(Lead).where(
        Lead.followup <= today, Lead.stage.not_in(("won", "lost")),
    ))
    quote_count = g.db.scalar(select(func.count()).select_from(Quote).where(Quote.status == "sent"))
    return render_template("dashboard.html", leads=leads[:30], has_more=len(leads) > 30, counts=counts,
                           stage=stage, q=q, page=page, today=today, due_count=due_count,
                           quote_count=quote_count, due_only=request.args.get("retornos") == "1")


@crm.get("/leads/<int:lead_id>")
def lead_detail(lead_id):
    lead = get_record(Lead, lead_id)
    assignee = g.db.get(User, lead.assignee_id) if lead.assignee_id else None
    quotes = g.db.execute(select(Quote, Revision).join(
        Revision, (Revision.quote_id == Quote.id) & (Revision.number == Quote.revision)
    ).where(Quote.lead_id == lead.id).order_by(Quote.created_at.desc(), Quote.id.desc())).all()
    activity = g.db.execute(select(Activity, User.name).join(User, User.id == Activity.user_id)
                            .where(Activity.lead_id == lead.id).order_by(Activity.id.desc()).limit(60)).all()
    return render_template("lead.html", lead=lead, assignee=assignee, quotes=quotes, activity=activity)


def parse_lead(form):
    stage, source = form.get("stage", "new"), form.get("source", "")
    if stage not in STAGES or source not in SOURCES:
        raise InvalidForm("Selecione uma etapa e uma origem válidas.")
    assignee = form.get("assignee_id", type=int)
    if form.get("assignee_id") and not g.db.scalar(select(User.id).where(
        User.id == assignee, User.active, User.password_hash.is_not(None),
    )):
        raise InvalidForm("Escolha uma responsável com conta ativa.")
    return dict(
        name=text_field(form, "name", 100, "o nome do cliente", required=True),
        phone=text_field(form, "phone", 36, "o telefone"),
        email=text_field(form, "email", 254, "o e-mail"),
        city=text_field(form, "city", 100, "a cidade/UF"),
        document=text_field(form, "document", 30, "o CPF/CNPJ"),
        notes=text_field(form, "notes", 2000, "as notas internas"),
        stage=stage, source=source, assignee_id=assignee,
        followup=parse_date(form.get("followup", ""), "retorno"),
    )


@crm.route("/leads/novo", methods=["GET", "POST"])
@crm.route("/leads/<int:lead_id>/editar", methods=["GET", "POST"])
def edit_lead(lead_id=None):
    lead = get_record(Lead, lead_id) if lead_id is not None else None
    status = 200
    if request.method == "POST":
        try:
            values = parse_lead(request.form)
        except InvalidForm as error:
            flash(str(error), "error")
            status = 422
        else:
            if lead is None:
                lead = Lead(**values)
                g.db.add(lead)
                g.db.flush()
                record_activity(lead.id, "Cadastrou o lead.")
            else:
                updated = g.db.execute(update(Lead).where(
                    Lead.id == lead.id, Lead.version == get_posted_version(),
                ).values(**values, version=Lead.version + 1).execution_options(synchronize_session=False))
                if updated.rowcount != 1:
                    abort(409)
                message = (f"Alterou a etapa de {STAGES[lead.stage]} para {STAGES[values['stage']]}."
                           if lead.stage != values["stage"] else "Atualizou os dados do lead.")
                record_activity(lead.id, message)
            g.db.commit()
            flash("Lead salvo.", "success")
            return redirect(url_for("crm.lead_detail", lead_id=lead.id))
    users = g.db.scalars(select(User).where(User.active, User.password_hash.is_not(None)).order_by(User.name)).all()
    values = request.form if request.method == "POST" else {
        key: getattr(lead, key) or "" for key in (
            "name", "phone", "email", "city", "document", "notes", "stage", "source", "assignee_id", "followup",
        )
    } if lead else {"stage": "new", "source": "WhatsApp", "assignee_id": g.user.id}
    return render_template("lead_form.html", lead=lead, users=users, values=values), status


@crm.route("/leads/<int:lead_id>/orcamentos/novo", methods=["GET", "POST"])
@crm.route("/orcamentos/<int:quote_id>/revisar", methods=["GET", "POST"])
def edit_quote(lead_id=None, quote_id=None, available_leads=None):
    quote = get_record(Quote, quote_id) if quote_id is not None else None
    lead = get_record(Lead, quote.lead_id if quote else lead_id) if quote or lead_id is not None else None
    previous = get_record(Revision, (quote.id, quote.revision)) if quote else None
    status = 200
    if request.method == "POST":
        now = utc_now()
        try:
            if lead is None:
                raise InvalidForm("Selecione o lead para salvar a simulação.")
            data = parse_quote(request.form, lead, g.user.name, now.astimezone(LOCAL_TZ).date())
        except InvalidForm as error:
            flash(str(error), "error")
            status = 422
        else:
            if quote is None:
                quote = Quote(lead_id=lead.id, created_by=g.user.id)
                g.db.add(quote)
                g.db.flush()
                number = 1
            else:
                old_revision = get_posted_version("revision")
                old_status = request.form.get("old_status")
                changed = g.db.execute(update(Quote).where(
                    Quote.id == quote.id, Quote.revision == old_revision, Quote.status == old_status,
                ).values(revision=Quote.revision + 1, status="draft").execution_options(synchronize_session=False))
                if changed.rowcount != 1:
                    abort(409)
                number = old_revision + 1
            g.db.add(Revision(quote_id=quote.id, number=number, author_id=g.user.id, issued_at=now, data=data))
            record_activity(lead.id, f"Salvou {quote_number(quote)}, revisão {number}.")
            g.db.commit()
            return redirect(url_for("crm.quote_detail", quote_id=quote.id))
    return render_template("quote_form.html", quote=quote, lead=lead, previous=previous,
                           available_leads=available_leads, posted=request.form if request.method == "POST" else None,
                           today=datetime.now(LOCAL_TZ).date().isoformat()), status


@crm.get("/orcamentos/<int:quote_id>")
def quote_detail(quote_id):
    quote = get_record(Quote, quote_id)
    lead = get_record(Lead, quote.lead_id)
    revisions = g.db.execute(select(Revision, User.name).join(User, User.id == Revision.author_id)
                             .where(Revision.quote_id == quote.id).order_by(Revision.number.desc())).all()
    return render_template("quote.html", quote=quote, lead=lead, revisions=revisions,
                           version=revisions[0][0], transitions=TRANSITIONS[quote.status])


@crm.post("/orcamentos/<int:quote_id>/status")
def quote_status(quote_id):
    quote = get_record(Quote, quote_id)
    new_status = request.form.get("status")
    revision = get_posted_version("revision")
    old_status = request.form.get("old_status")
    if revision != quote.revision or old_status != quote.status:
        abort(409)
    if new_status not in TRANSITIONS[old_status]:
        abort(400)
    changed = g.db.execute(update(Quote).where(
        Quote.id == quote.id, Quote.revision == revision, Quote.status == old_status,
    ).values(status=new_status))
    if changed.rowcount != 1:
        abort(409)
    if new_status == "sent":
        g.db.execute(update(Lead).where(Lead.id == quote.lead_id, Lead.stage.in_(("new", "contact")))
                     .values(stage="quoted", version=Lead.version + 1))
    record_activity(quote.lead_id, f"Marcou {quote_number(quote)}, revisão {revision}, como {QUOTE_STATES[new_status].lower()}.")
    g.db.commit()
    return redirect(url_for("crm.quote_detail", quote_id=quote.id))


@crm.get("/orcamentos/<int:quote_id>/v/<int:number>/pdf")
def download_pdf(quote_id, number):
    quote = get_record(Quote, quote_id)
    revision = get_record(Revision, (quote_id, number))
    return send_file(quote_pdf(quote, revision), mimetype="application/pdf", as_attachment=True,
                     download_name=f"{quote_number(quote)}-V{revision.number}.pdf")


@crm.route("/simulador", methods=["GET", "POST"])
def simulator():
    leads = g.db.scalars(select(Lead).where(Lead.stage.not_in(("won", "lost")))
                         .order_by(Lead.name, Lead.id)).all()
    submitted = request.form.get("lead_id", type=int)
    chosen_id = submitted if any(lead.id == submitted for lead in leads) else None
    return edit_quote(lead_id=chosen_id, available_leads=leads)


@crm.post("/leads/<int:lead_id>/apagar")
def delete_lead(lead_id):
    lead = get_record(Lead, lead_id)
    has_quotes = g.db.scalar(select(func.count()).select_from(Quote).where(Quote.lead_id == lead_id))
    if has_quotes:
        flash("Apague os orçamentos deste lead antes de excluí-lo.", "error")
        return redirect(url_for("crm.lead_detail", lead_id=lead_id))
    for act in g.db.scalars(select(Activity).where(Activity.lead_id == lead_id)).all():
        g.db.delete(act)
    g.db.delete(lead)
    g.db.commit()
    flash("Lead apagado.", "success")
    return redirect(url_for("crm.dashboard"))


@crm.post("/orcamentos/<int:quote_id>/apagar")
def delete_quote(quote_id):
    quote = get_record(Quote, quote_id)
    lead_id = quote.lead_id
    label = quote_number(quote)
    for rev in g.db.scalars(select(Revision).where(Revision.quote_id == quote_id)).all():
        g.db.delete(rev)
    g.db.flush()
    g.db.delete(quote)
    record_activity(lead_id, f"Apagou {label}.")
    g.db.commit()
    flash("Orçamento apagado.", "success")
    return redirect(url_for("crm.lead_detail", lead_id=lead_id))


@crm.get("/orcamentos")
def quotes_list():
    state = request.args.get("status", "")
    page = max(1, min(request.args.get("page", 1, type=int), 100_000))
    query = select(Quote, Lead.name, Revision).join(Lead, Lead.id == Quote.lead_id).join(
        Revision, (Revision.quote_id == Quote.id) & (Revision.number == Quote.revision)
    )
    if state in QUOTE_STATES:
        query = query.where(Quote.status == state)
    rows = g.db.execute(query.order_by(Quote.id.desc()).offset((page - 1) * 30).limit(31)).all()
    return render_template("quotes_list.html", rows=rows[:30], has_more=len(rows) > 30, state=state, page=page)


@crm.get("/kanban")
def kanban():
    today = datetime.now(LOCAL_TZ).date()
    leads = g.db.execute(
        select(Lead, User.name).outerjoin(User, User.id == Lead.assignee_id)
        .order_by(Lead.created_at.desc(), Lead.id.desc())
    ).all()
    by_stage = {key: [] for key in STAGES}
    for lead, assignee in leads:
        if lead.stage in by_stage:
            by_stage[lead.stage].append((lead, assignee))
    return render_template("kanban.html", by_stage=by_stage, today=today)


@crm.post("/kanban/<int:lead_id>/stage")
def kanban_stage(lead_id):
    lead = get_record(Lead, lead_id)
    new_stage = request.form.get("stage", "")
    if new_stage not in STAGES:
        abort(400)
    if lead.stage != new_stage:
        g.db.execute(update(Lead).where(Lead.id == lead_id).values(
            stage=new_stage, version=Lead.version + 1
        ).execution_options(synchronize_session=False))
        record_activity(lead_id, f"Moveu etapa para {STAGES[new_stage]} via Kanban.")
        g.db.commit()
    return "", 204


@crm.get("/tarefas")
def tasks():
    leads = g.db.scalars(select(Lead).where(Lead.stage.not_in(("won", "lost"))).order_by(Lead.name)).all()
    rows = g.db.execute(
        select(Task, Lead.name, User.name).outerjoin(Lead, Lead.id == Task.lead_id)
        .join(User, User.id == Task.created_by)
        .order_by(Task.position, Task.id)
    ).all()
    by_status = {"todo": [], "doing": [], "done": []}
    for task, lead_name, user_name in rows:
        if task.status in by_status:
            by_status[task.status].append((task, lead_name, user_name))
    return render_template("tasks.html", by_status=by_status, leads=leads)


@crm.post("/tarefas/nova")
def task_create():
    title = request.form.get("title", "").strip()[:200]
    if not title:
        abort(400)
    notes = request.form.get("notes", "").strip()[:1000]
    lead_id = request.form.get("lead_id", type=int)
    if lead_id and not g.db.get(Lead, lead_id):
        lead_id = None
    g.db.add(Task(title=title, notes=notes, lead_id=lead_id, created_by=g.user.id))
    g.db.commit()
    return redirect(url_for("crm.tasks"))


@crm.post("/tarefas/<int:task_id>/status")
def task_status(task_id):
    task = get_record(Task, task_id)
    new_status = request.form.get("status", "")
    if new_status not in ("todo", "doing", "done"):
        abort(400)
    task.status = new_status
    g.db.commit()
    return "", 204


@crm.post("/tarefas/<int:task_id>/apagar")
def task_delete(task_id):
    task = get_record(Task, task_id)
    g.db.delete(task)
    g.db.commit()
    return redirect(url_for("crm.tasks"))


@crm.get("/financeiro")
def financeiro():
    rows = g.db.execute(
        select(Quote, Lead, Revision)
        .join(Lead, Lead.id == Quote.lead_id)
        .join(Revision, (Revision.quote_id == Quote.id) & (Revision.number == Quote.revision))
        .where(
            (Quote.status.in_(["accepted", "sent", "declined"])) |
            (Lead.stage.in_(["won", "negotiating"]))
        )
        .order_by(Quote.id.desc())
    ).all()
    return render_template("financeiro.html", rows=rows)
