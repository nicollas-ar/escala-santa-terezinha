"""Escalas e avisos — Paróquia Santa Terezinha do Menino Jesus."""
import json
import os
import random
import secrets
import time
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from zoneinfo import ZoneInfo

from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

import database

try:
    FUSO = ZoneInfo("America/Sao_Paulo")
except Exception:
    FUSO = timezone(timedelta(hours=-3))

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
app.config.update(
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.environ.get("PRODUCAO")),
    MAX_CONTENT_LENGTH=1024 * 1024,
)
chave = os.environ.get("SECRET_KEY")
if os.environ.get("PRODUCAO") and (not chave or len(chave) < 32):
    raise RuntimeError("Defina SECRET_KEY com pelo menos 32 caracteres na produção")
app.secret_key = chave or secrets.token_hex(32)
database.init_db()

DIAS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
        "sexta-feira", "sábado", "domingo")
MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro")

def agora():
    return datetime.now(FUSO)

def hoje_iso():
    return agora().date().isoformat()

@app.template_filter("data_bonita")
def data_bonita(valor):
    d = date.fromisoformat(valor)
    return f"{DIAS[d.weekday()]}, {d.day} de {MESES[d.month-1]} de {d.year}"

@app.template_filter("data_curta")
def data_curta(valor):
    return date.fromisoformat(valor).strftime("%d/%m/%Y")

@app.template_filter("hora_bonita")
def hora_bonita(valor):
    return valor.replace(":", "h", 1)

def get_db():
    if "db" not in g:
        g.db = database.conectar()
    return g.db

@app.teardown_appcontext
def close_db(exception):
    c = g.pop("db", None)
    if c is not None:
        c.close()

def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]

app.jinja_env.globals["csrf_token"] = csrf_token

@app.before_request
def carregar_usuario():
    g.usuario = None
    ident = session.get("usuario_id")
    if ident:
        g.usuario = get_db().execute(
            "SELECT id,nome,usuario,perfil,ativo FROM usuarios WHERE id=?", (ident,)
        ).fetchone()
        if not g.usuario or not g.usuario["ativo"]:
            session.clear()
            g.usuario = None
    if request.method == "POST":
        esperado = session.get("csrf", "")
        recebido = request.form.get("csrf_token", "")
        if not esperado or not secrets.compare_digest(esperado, recebido):
            abort(400)

@app.context_processor
def globais():
    return {"usuario_logado": g.get("usuario"), "hoje": hoje_iso()}

@app.after_request
def seguranca(resposta):
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    resposta.headers["X-Frame-Options"] = "DENY"
    resposta.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resposta.headers["Cache-Control"] = "no-store"
    return resposta

def acesso(*perfis):
    def decorador(func):
        @wraps(func)
        def interno(*args, **kwargs):
            if not g.usuario:
                flash("Faça login para continuar.", "erro")
                return redirect(url_for("entrar"))
            if perfis and g.usuario["perfil"] not in perfis:
                abort(403)
            return func(*args, **kwargs)
        return interno
    return decorador

def escalas_para(missas):
    ids = [m["id"] for m in missas]
    if not ids:
        return {}
    marcas = ",".join("?" for _ in ids)
    rows = get_db().execute(
        f"""SELECT e.id,e.missa_id,e.servidor_id,e.funcao,e.ordem,u.nome
            FROM escala e JOIN usuarios u ON u.id=e.servidor_id
            WHERE e.missa_id IN ({marcas})
            ORDER BY e.missa_id,e.ordem,e.id""", ids
    ).fetchall()
    saida = {mid: [] for mid in ids}
    for r in rows:
        saida[r["missa_id"]].append(r)
    return saida

def avisos():
    return get_db().execute("SELECT * FROM avisos ORDER BY id DESC").fetchall()

@app.route("/")
def index():
    instante = agora()
    m = get_db().execute(
        """SELECT * FROM missas WHERE publicada=1
           AND (data>? OR (data=? AND hora>=?))
           ORDER BY data,hora,id LIMIT 60""",
        (instante.date().isoformat(), instante.date().isoformat(), instante.strftime("%H:%M"))
    ).fetchall()
    return render_template("index.html", missas=m, escalas=escalas_para(m), avisos=avisos())

@app.route("/saude")
def saude():
    return "ok", 200, {"Content-Type": "text/plain; charset=utf-8"}

FALHAS = {}
@app.route("/entrar", methods=["GET", "POST"])
def entrar():
    if g.usuario:
        return redirect(url_for("painel"))
    if request.method == "POST":
        ip = request.remote_addr or "?"
        falhas, bloqueio = FALHAS.get(ip, (0, 0))
        if bloqueio > time.time():
            flash("Muitas tentativas. Tente novamente em alguns minutos.", "erro")
            return render_template("login.html"), 429
        login = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")
        u = get_db().execute("SELECT * FROM usuarios WHERE usuario=?", (login,)).fetchone()
        if u and u["ativo"] and u["perfil"] in ("padre", "coordenador") and check_password_hash(u["senha_hash"], senha):
            session.clear()
            session["usuario_id"] = u["id"]
            session.permanent = True
            FALHAS.pop(ip, None)
            return redirect(url_for("painel"))
        falhas += 1
        FALHAS[ip] = (falhas, time.time() + 300 if falhas >= 5 else 0)
        flash("Usuário ou senha inválidos.", "erro")
    return render_template("login.html")

@app.post("/sair")
def sair():
    session.clear()
    return redirect(url_for("index"))

@app.route("/painel")
@acesso("padre", "coordenador")
def painel():
    instante = agora()
    base = (instante.date().isoformat(), instante.date().isoformat(), instante.strftime("%H:%M"))
    proximas = get_db().execute(
        """SELECT * FROM missas WHERE (data>? OR (data=? AND hora>=?))
           ORDER BY data,hora,id LIMIT 100""", base
    ).fetchall()
    anteriores = get_db().execute(
        """SELECT * FROM missas WHERE (data<? OR (data=? AND hora<?))
           ORDER BY data DESC,hora DESC LIMIT 15""", base
    ).fetchall()
    lista = proximas + anteriores
    return render_template("painel.html", proximas=proximas, anteriores=anteriores,
                           escalas=escalas_para(lista), avisos=avisos())

@app.route("/usuarios", methods=["GET", "POST"])
@acesso("padre", "coordenador")
def usuarios():
    db = get_db()
    perfil_novo = "coordenador" if g.usuario["perfil"] == "padre" else "servidor"
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        if not (2 <= len(nome) <= 100):
            flash("Informe um nome entre 2 e 100 caracteres.", "erro")
        elif perfil_novo == "servidor":
            # Identificadores internos aleatórios: não são contas e nunca permitem login.
            identificador = "servidor_" + secrets.token_hex(16)
            db.execute(
                "INSERT INTO usuarios (nome,usuario,senha_hash,perfil,criado_por) VALUES (?,?,?,?,?)",
                (nome, identificador, generate_password_hash(secrets.token_urlsafe(48)), "servidor", g.usuario["id"])
            )
            db.commit()
            flash("Servidor cadastrado apenas com o nome.", "ok")
            return redirect(url_for("usuarios"))
        else:
            login = request.form.get("usuario", "").strip().lower()
            senha = request.form.get("senha", "")
            if not (3 <= len(login) <= 40 and login.replace("_", "").replace("-", "").isalnum()):
                flash("Usuário inválido (3 a 40 caracteres).", "erro")
            elif len(senha) < 12:
                flash("A senha deve ter pelo menos 12 caracteres.", "erro")
            elif db.execute("SELECT id FROM usuarios WHERE usuario=?", (login,)).fetchone():
                flash("Esse nome de usuário já existe.", "erro")
            else:
                db.execute(
                    "INSERT INTO usuarios (nome,usuario,senha_hash,perfil,criado_por) VALUES (?,?,?,?,?)",
                    (nome, login, generate_password_hash(senha), perfil_novo, g.usuario["id"])
                )
                db.commit()
                flash("Coordenador cadastrado.", "ok")
                return redirect(url_for("usuarios"))
    pessoas = db.execute(
        "SELECT id,nome,usuario,ativo FROM usuarios WHERE perfil=? ORDER BY nome",
        (perfil_novo,)
    ).fetchall()
    return render_template("usuarios.html", pessoas=pessoas, perfil_novo=perfil_novo)

@app.post("/usuarios/<int:uid>/alternar")
@acesso("padre", "coordenador")
def alternar_usuario(uid):
    permitido = "coordenador" if g.usuario["perfil"] == "padre" else "servidor"
    db = get_db()
    pessoa = db.execute("SELECT * FROM usuarios WHERE id=? AND perfil=?", (uid, permitido)).fetchone()
    if not pessoa:
        abort(404)
    db.execute("UPDATE usuarios SET ativo=? WHERE id=?", (0 if pessoa["ativo"] else 1, uid))
    db.commit()
    flash("Situação atualizada.", "ok")
    return redirect(url_for("usuarios"))

def todos_servidores():
    return get_db().execute(
        "SELECT id,nome,ativo FROM usuarios WHERE perfil='servidor' ORDER BY nome"
    ).fetchall()

def sortear(db, mid, disponiveis, quantidade, data_missa, funcoes):
    """Rodízio ponderado: servidores com menos escalas nos últimos 60 dias têm preferência."""
    limite = (date.fromisoformat(data_missa) - timedelta(days=60)).isoformat()
    historico = db.execute(
        """SELECT e.servidor_id,COUNT(*) AS n FROM escala e
           JOIN missas m ON m.id=e.missa_id WHERE m.id!=? AND m.data>=?
           GROUP BY e.servidor_id""", (mid, limite)
    ).fetchall()
    contagens = {r["servidor_id"]: r["n"] for r in historico}
    rng = random.SystemRandom()
    candidatos = list(dict.fromkeys(disponiveis))
    escolhidos = []
    for _ in range(min(quantidade, len(candidatos))):
        pesos = [1.0 / ((1 + contagens.get(cid, 0)) ** 2) for cid in candidatos]
        elegido = rng.choices(candidatos, weights=pesos, k=1)[0]
        escolhidos.append(elegido)
        candidatos.remove(elegido)
    rng.shuffle(escolhidos)
    funcoes_sorteadas = list(funcoes)
    rng.shuffle(funcoes_sorteadas)
    db.execute("DELETE FROM escala WHERE missa_id=?", (mid,))
    for ordem, servidor in enumerate(escolhidos):
        funcao = funcoes_sorteadas[ordem] if ordem < len(funcoes_sorteadas) else "Servidor"
        db.execute("INSERT INTO escala (missa_id,servidor_id,funcao,ordem) VALUES (?,?,?,?)",
                   (mid, servidor, funcao, ordem))

def dados_missa_form():
    nome = request.form.get("nome", "").strip()
    data_txt = request.form.get("data", "")
    hora = request.form.get("hora", "")
    quantidade = int(request.form.get("quantidade", "0"))
    recado = request.form.get("recado", "").strip()
    funcoes = [x.strip() for x in request.form.getlist("funcoes") if x.strip()]
    if not (2 <= len(nome) <= 100 and len(recado) <= 300 and 1 <= quantidade <= 30):
        raise ValueError("Nome, quantidade ou recado inválidos.")
    if len(funcoes) != quantidade or any(len(x) > 45 for x in funcoes):
        raise ValueError("Adicione uma função por vaga (até 30), com no máximo 45 caracteres.")
    data_obj = date.fromisoformat(data_txt)
    if data_obj < agora().date():
        raise ValueError("A celebração não pode começar em uma data passada.")
    datetime.strptime(hora, "%H:%M")
    return nome, data_obj, hora, quantidade, recado, funcoes

@app.route("/missas/nova", methods=["GET", "POST"])
@acesso("padre", "coordenador")
def nova_missa():
    servidores = [s for s in todos_servidores() if s["ativo"]]
    if request.method == "POST":
        try:
            nome, inicial, hora, quantidade, recado, funcoes = dados_missa_form()
            disponiveis = list(dict.fromkeys(int(x) for x in request.form.getlist("disponiveis")))
            validos = {x["id"] for x in servidores}
            if not disponiveis or not set(disponiveis).issubset(validos) or quantidade > len(disponiveis):
                raise ValueError("Selecione servidores ativos suficientes para a quantidade informada.")
            db = get_db()
            for dia in [inicial]:
                if database.POSTGRES:
                    mid = db.execute(
                        """INSERT INTO missas(nome,data,hora,quantidade,funcoes,recado,criado_por)
                           VALUES (?,?,?,?,?,?,?) RETURNING id""",
                        (nome, dia.isoformat(), hora, quantidade, json.dumps(funcoes), recado, g.usuario["id"])
                    ).fetchone()["id"]
                else:
                    cur = db.execute(
                        """INSERT INTO missas(nome,data,hora,quantidade,funcoes,recado,criado_por)
                           VALUES (?,?,?,?,?,?,?)""",
                        (nome, dia.isoformat(), hora, quantidade, json.dumps(funcoes), recado, g.usuario["id"])
                    )
                    mid = cur.lastrowid
                for uid in disponiveis:
                    db.execute("INSERT INTO missa_disponiveis(missa_id,servidor_id) VALUES (?,?)", (mid, uid))
                sortear(db, mid, disponiveis, quantidade, dia.isoformat(), funcoes)
            db.commit()
            flash("Celebração e escala criadas como rascunho. Revise antes de publicar.", "ok")
            return redirect(url_for("painel"))
        except (ValueError, OverflowError) as exc:
            get_db().rollback()
            flash(str(exc) if isinstance(exc, ValueError) else "Dados inválidos.", "erro")
    return render_template("nova_missa.html", servidores=servidores)

def missa_ou_404(mid):
    item = get_db().execute("SELECT * FROM missas WHERE id=?", (mid,)).fetchone()
    if not item:
        abort(404)
    return item

@app.route("/missas/<int:mid>/editar", methods=["GET", "POST"])
@acesso("padre", "coordenador")
def editar_missa(mid):
    db = get_db()
    missa = missa_ou_404(mid)
    servidores = todos_servidores()
    atuais = escalas_para([missa])[mid]
    if request.method == "POST":
        acao = request.form.get("acao", "salvar")
        try:
            recado = request.form.get("recado", "").strip()
            if len(recado) > 300:
                raise ValueError("Recado muito longo.")
            if acao == "sortear":
                disponiveis = [r["servidor_id"] for r in db.execute(
                    "SELECT servidor_id FROM missa_disponiveis WHERE missa_id=?", (mid,)
                ).fetchall()]
                ativos = {s["id"] for s in servidores if s["ativo"]}
                disponiveis = [uid for uid in disponiveis if uid in ativos]
                if not disponiveis:
                    raise ValueError("Não há servidores disponíveis ativos para sortear.")
                sortear(db, mid, disponiveis, min(missa["quantidade"],len(disponiveis)),
                        missa["data"], json.loads(missa["funcoes"]))
            else:
                ids_raw = request.form.getlist("servidor_id")
                funcoes = request.form.getlist("funcao")
                if len(ids_raw) != len(funcoes) or len(ids_raw) > 30:
                    raise ValueError("A escala enviada é inválida.")
                ids = [int(x) for x in ids_raw if x]
                permitidos = {s["id"] for s in servidores if s["ativo"]} | {
                    r["servidor_id"] for r in atuais
                }
                if len(set(ids)) != len(ids) or not set(ids).issubset(permitidos):
                    raise ValueError("Servidor inválido ou duplicado.")
                if any(len(f.strip()) > 45 for f in funcoes):
                    raise ValueError("Nome de função muito longo.")
                db.execute("DELETE FROM escala WHERE missa_id=?", (mid,))
                ordem = 0
                for raw, funcao in zip(ids_raw, funcoes):
                    if raw:
                        db.execute(
                            "INSERT INTO escala(missa_id,servidor_id,funcao,ordem) VALUES (?,?,?,?)",
                            (mid, int(raw), funcao.strip() or "Servidor", ordem)
                        )
                        ordem += 1
                if acao == "publicar" and not ids:
                    raise ValueError("Inclua pelo menos um servidor antes de publicar.")
                if acao == "publicar":
                    db.execute("UPDATE missas SET publicada=1 WHERE id=?", (mid,))
            db.execute("UPDATE missas SET recado=? WHERE id=?", (recado, mid))
            db.commit()
            flash("Escala atualizada.", "ok")
            return redirect(url_for("editar_missa", mid=mid))
        except (ValueError, OverflowError) as exc:
            db.rollback()
            flash(str(exc) if isinstance(exc, ValueError) else "Dados inválidos.", "erro")
    missa = missa_ou_404(mid)
    return render_template("editar_missa.html", missa=missa,
                           escala=escalas_para([missa])[mid], servidores=servidores)

@app.post("/missas/<int:mid>/publicacao")
@acesso("padre", "coordenador")
def publicacao(mid):
    missa = missa_ou_404(mid)
    db = get_db()
    novo = 0 if missa["publicada"] else 1
    if novo and not db.execute("SELECT id FROM escala WHERE missa_id=? LIMIT 1", (mid,)).fetchone():
        flash("Não é possível publicar uma escala vazia.", "erro")
    else:
        db.execute("UPDATE missas SET publicada=? WHERE id=?", (novo, mid))
        db.commit()
        flash("Publicação atualizada.", "ok")
    return redirect(url_for("painel"))

@app.post("/missas/<int:mid>/excluir")
@acesso("padre", "coordenador")
def excluir_missa(mid):
    missa_ou_404(mid)
    db = get_db()
    db.execute("DELETE FROM escala WHERE missa_id=?", (mid,))
    db.execute("DELETE FROM missa_disponiveis WHERE missa_id=?", (mid,))
    db.execute("DELETE FROM missas WHERE id=?", (mid,))
    db.commit()
    flash("Celebração excluída.", "ok")
    return redirect(url_for("painel"))

@app.route("/avisos/novo", methods=["GET", "POST"])
@acesso("padre", "coordenador")
def novo_aviso():
    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        mensagem = request.form.get("mensagem", "").strip()
        if not (2 <= len(titulo) <= 80 and 2 <= len(mensagem) <= 600):
            flash("O aviso precisa de título e mensagem válidos.", "erro")
        else:
            db = get_db()
            db.execute("INSERT INTO avisos(titulo,mensagem,criado_por) VALUES (?,?,?)",
                       (titulo,mensagem,g.usuario["id"]))
            db.commit()
            flash("Aviso publicado.", "ok")
            return redirect(url_for("painel"))
    return render_template("novo_aviso.html")

@app.post("/avisos/<int:aid>/excluir")
@acesso("padre", "coordenador")
def excluir_aviso(aid):
    db = get_db()
    db.execute("DELETE FROM avisos WHERE id=?", (aid,))
    db.commit()
    flash("Aviso removido.", "ok")
    return redirect(url_for("painel"))

if __name__ == "__main__":
    app.run(debug=not bool(os.environ.get("PRODUCAO")))
