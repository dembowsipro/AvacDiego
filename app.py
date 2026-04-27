"""
AVAC DESING — Sistema de Gestión de Accesos
Empresa de Construcción | Python + Flask + pywebview
Instalar: pip install flask pywebview requests
Ejecutar: python app.py
"""

import threading, json, datetime, random, hashlib, os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

app = Flask(__name__)
app.secret_key = "avac_construccion_2024_secret"

# ══════════════════════════════════════════════
#  BASE DE DATOS EN MEMORIA
# ══════════════════════════════════════════════

ROLES = {
    "gerente_general":   {"nivel": 5, "label": "Gerente General",    "color": "#E74C3C", "icon": "👑"},
    "jefe_obra":         {"nivel": 4, "label": "Jefe de Obra",        "color": "#E67E22", "icon": "🏗️"},
    "ingeniero":         {"nivel": 3, "label": "Ingeniero",           "color": "#3498DB", "icon": "⚙️"},
    "supervisor":        {"nivel": 3, "label": "Supervisor",          "color": "#9B59B6", "icon": "👷"},
    "administrativo":    {"nivel": 2, "label": "Administrativo",      "color": "#27AE60", "icon": "📋"},
    "marketing":         {"nivel": 1, "label": "Marketing",           "color": "#1ABC9C", "icon": "📣"},
    "obrero":            {"nivel": 1, "label": "Obrero",              "color": "#95A5A6", "icon": "🔨"},
}

RECURSOS = {
    "planos_confidenciales": {"nivel_req": 4, "label": "Planos Confidenciales",  "icon": "📐", "categoria": "Diseño"},
    "presupuestos":          {"nivel_req": 4, "label": "Presupuestos",            "icon": "💰", "categoria": "Finanzas"},
    "contratos_clientes":    {"nivel_req": 4, "label": "Contratos de Clientes",   "icon": "📄", "categoria": "Legal"},
    "nomina":                {"nivel_req": 5, "label": "Nómina",                  "icon": "💵", "categoria": "RRHH"},
    "reportes_obra":         {"nivel_req": 3, "label": "Reportes de Obra",        "icon": "📊", "categoria": "Operaciones"},
    "inventario":            {"nivel_req": 2, "label": "Inventario",              "icon": "📦", "categoria": "Logística"},
    "datos_clientes":        {"nivel_req": 4, "label": "Datos de Clientes",       "icon": "👥", "categoria": "CRM"},
    "cronogramas":           {"nivel_req": 2, "label": "Cronogramas",             "icon": "📅", "categoria": "Planificación"},
    "cotizaciones":          {"nivel_req": 3, "label": "Cotizaciones",            "icon": "📋", "categoria": "Ventas"},
    "estadisticas_mkt":      {"nivel_req": 1, "label": "Estadísticas Marketing",  "icon": "📈", "categoria": "Marketing"},
}

USUARIOS = [
    {"id":1, "nombre":"Carlos Ramírez",  "email":"carlos@avac.com",   "rol":"gerente_general",  "status":"activo",    "depto":"Gerencia",     "avatar":"CR"},
    {"id":2, "nombre":"Ana Herrera",     "email":"ana@avac.com",       "rol":"jefe_obra",         "status":"activo",    "depto":"Operaciones",  "avatar":"AH"},
    {"id":3, "nombre":"Luis Mendoza",    "email":"luis@avac.com",      "rol":"ingeniero",         "status":"activo",    "depto":"Ingeniería",   "avatar":"LM"},
    {"id":4, "nombre":"Sofía Torres",    "email":"sofia@avac.com",     "rol":"administrativo",    "status":"activo",    "depto":"Admón",        "avatar":"ST"},
    {"id":5, "nombre":"Pedro Guzmán",    "email":"pedro@avac.com",     "rol":"marketing",         "status":"activo",    "depto":"Marketing",    "avatar":"PG"},
    {"id":6, "nombre":"María Castillo",  "email":"maria@avac.com",     "rol":"supervisor",        "status":"activo",    "depto":"Operaciones",  "avatar":"MC"},
    {"id":7, "nombre":"Jorge Salinas",   "email":"jorge@avac.com",     "rol":"obrero",            "status":"activo",    "depto":"Obra",         "avatar":"JS"},
    {"id":8, "nombre":"Elena Ríos",      "email":"elena@avac.com",     "rol":"ingeniero",         "status":"suspendido","depto":"Ingeniería",   "avatar":"ER"},
]

ACCESOS_ESP = []   # solicitudes de acceso especial
REGISTRO    = []   # log de actividad

def _def_pass(p): return hashlib.sha256(p.encode()).hexdigest()

USUARIOS_AUTH = {
    "carlos@avac.com": {"pass": _def_pass("admin123"), "uid": 1},
    "ana@avac.com":    {"pass": _def_pass("pass123"),  "uid": 2},
    "pedro@avac.com":  {"pass": _def_pass("pass123"),  "uid": 5},
}

# Generar log inicial
_acciones = ["LOGIN","LOGOUT","VER_DATOS","EXPORTAR","MODIFICAR","DENEGADO","ACCESO_ESP"]
_ips = ["192.168.1.10","192.168.1.22","192.168.1.45","10.0.0.5","10.0.0.12"]
for _i in range(50):
    _u  = random.choice(USUARIOS)
    _ac = random.choice(_acciones)
    _rs = random.choice(list(RECURSOS.keys()))
    _ts = datetime.datetime.now() - datetime.timedelta(hours=random.randint(0,120))
    _ok = "DENEGADO" if (_ac=="DENEGADO" or ROLES[_u["rol"]]["nivel"] < RECURSOS[_rs]["nivel_req"]) else "OK"
    REGISTRO.append({
        "id":_i+1, "usuario":_u["nombre"], "rol":_u["rol"],
        "accion":_ac, "recurso":_rs,
        "ts":_ts.strftime("%Y-%m-%d %H:%M"),
        "ip":random.choice(_ips), "status":_ok,
    })
REGISTRO.sort(key=lambda x: x["ts"], reverse=True)

# ══════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════
def usuario_actual():
    uid = session.get("uid")
    if not uid: return None
    return next((u for u in USUARIOS if u["id"]==uid), None)

def tiene_acceso(rol_key, recurso_key):
    rol = ROLES.get(rol_key, {})
    rec = RECURSOS.get(recurso_key, {})
    return rol.get("nivel",0) >= rec.get("nivel_req",99)

def log_accion(usuario, accion, recurso, ip="—", status="OK"):
    REGISTRO.insert(0, {
        "id": len(REGISTRO)+1,
        "usuario": usuario["nombre"], "rol": usuario["rol"],
        "accion": accion, "recurso": recurso,
        "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "ip": ip, "status": status,
    })

# ══════════════════════════════════════════════
#  RUTAS
# ══════════════════════════════════════════════

@app.route("/")
def index():
    if not usuario_actual():
        return redirect("/login")
    return redirect("/dashboard")

@app.route("/login", methods=["GET","POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email","").strip()
        pw    = request.form.get("password","")
        auth  = USUARIOS_AUTH.get(email)
        if auth and auth["pass"] == _def_pass(pw):
            session["uid"] = auth["uid"]
            u = next(u for u in USUARIOS if u["id"]==auth["uid"])
            log_accion(u, "LOGIN", "sistema", request.remote_addr, "OK")
            return redirect("/dashboard")
        error = "Credenciales incorrectas"
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    u = usuario_actual()
    if u: log_accion(u, "LOGOUT", "sistema", request.remote_addr, "OK")
    session.clear()
    return redirect("/login")

@app.route("/registro_usuario", methods=["GET","POST"])
def registro_usuario():
    if usuario_actual():
        return redirect("/dashboard")
    error = None
    success = None
    if request.method == "POST":
        nombre = request.form.get("nombre","").strip()
        email  = request.form.get("email","").strip()
        pw     = request.form.get("password","")
        pw2    = request.form.get("password2","")
        depto  = request.form.get("depto","").strip()
        # Validaciones
        if not nombre or not email or not pw or not depto:
            error = "Todos los campos son obligatorios"
        elif pw != pw2:
            error = "Las contraseñas no coinciden"
        elif len(pw) < 6:
            error = "La contraseña debe tener al menos 6 caracteres"
        elif email in USUARIOS_AUTH:
            error = "Ya existe una cuenta con ese correo"
        else:
            nuevo_id = max(x["id"] for x in USUARIOS) + 1
            initials = "".join(p[0].upper() for p in nombre.split()[:2])
            USUARIOS.append({
                "id": nuevo_id, "nombre": nombre, "email": email,
                "rol": "obrero", "status": "activo",
                "depto": depto, "avatar": initials
            })
            USUARIOS_AUTH[email] = {"pass": _def_pass(pw), "uid": nuevo_id}
            success = "Cuenta creada exitosamente. Ya puedes iniciar sesión."
    return render_template("registro_usuario.html", error=error, success=success)

@app.route("/dashboard")
def dashboard():
    u = usuario_actual()
    if not u: return redirect("/login")
    denied  = sum(1 for r in REGISTRO if r["status"]=="DENEGADO")
    activos = sum(1 for x in USUARIOS if x["status"]=="activo")
    esp_pen = sum(1 for a in ACCESOS_ESP if a["status"]=="pendiente")
    exports = sum(1 for r in REGISTRO if r["accion"]=="EXPORTAR")
    recents = REGISTRO[:12]
    return render_template("dashboard.html", u=u, roles=ROLES, recursos=RECURSOS,
        denied=denied, activos=activos, esp_pen=esp_pen, exports=exports,
        recents=recents, usuarios=USUARIOS)

@app.route("/usuarios")
def usuarios():
    u = usuario_actual()
    if not u: return redirect("/login")
    if ROLES[u["rol"]]["nivel"] < 4:
        return redirect("/dashboard")
    return render_template("usuarios.html", u=u, roles=ROLES, usuarios=USUARIOS)

@app.route("/api/usuario/nuevo", methods=["POST"])
def nuevo_usuario():
    u = usuario_actual()
    if not u or ROLES[u["rol"]]["nivel"] < 5: return jsonify({"ok":False,"msg":"Sin permiso"})
    d = request.json
    nuevo_id = max(x["id"] for x in USUARIOS)+1
    initials = "".join(p[0].upper() for p in d["nombre"].split()[:2])
    USUARIOS.append({"id":nuevo_id,"nombre":d["nombre"],"email":d["email"],
        "rol":d["rol"],"status":"activo","depto":d["depto"],"avatar":initials})
    log_accion(u,"CREAR_USUARIO","usuarios",request.remote_addr,"OK")
    return jsonify({"ok":True})

@app.route("/api/usuario/toggle", methods=["POST"])
def toggle_usuario():
    u = usuario_actual()
    if not u or ROLES[u["rol"]]["nivel"] < 4: return jsonify({"ok":False})
    d = request.json
    for usr in USUARIOS:
        if usr["id"]==d["id"]: usr["status"]=d["status"]
    log_accion(u,f"CAMBIAR_STATUS_{d['status'].upper()}","usuarios",request.remote_addr,"OK")
    return jsonify({"ok":True})

@app.route("/api/usuario/cambiar_rol", methods=["POST"])
def cambiar_rol():
    u = usuario_actual()
    if not u or ROLES[u["rol"]]["nivel"] < 5: return jsonify({"ok":False,"msg":"Solo Gerente General"})
    d = request.json
    for usr in USUARIOS:
        if usr["id"]==d["id"]: usr["rol"]=d["rol"]
    log_accion(u,"CAMBIAR_ROL","usuarios",request.remote_addr,"OK")
    return jsonify({"ok":True})

@app.route("/permisos")
def permisos():
    u = usuario_actual()
    if not u: return redirect("/login")
    return render_template("permisos.html", u=u, roles=ROLES, recursos=RECURSOS,
        usuarios=USUARIOS, tiene_acceso=tiene_acceso)

@app.route("/registro")
def registro():
    u = usuario_actual()
    if not u: return redirect("/login")
    if ROLES[u["rol"]]["nivel"] < 3: return redirect("/dashboard")
    filtro = request.args.get("filtro","TODOS")
    logs = REGISTRO if filtro=="TODOS" else [r for r in REGISTRO if r["status"]==filtro]
    return render_template("registro.html", u=u, roles=ROLES, logs=logs[:60], filtro=filtro)

@app.route("/acceso_especial")
def acceso_especial():
    u = usuario_actual()
    if not u: return redirect("/login")
    return render_template("acceso_especial.html", u=u, roles=ROLES,
        recursos=RECURSOS, solicitudes=ACCESOS_ESP, USUARIOS=USUARIOS)

@app.route("/api/solicitar_acceso", methods=["POST"])
def solicitar_acceso():
    u = usuario_actual()
    if not u: return jsonify({"ok":False})
    d = request.json
    ACCESOS_ESP.append({
        "id": len(ACCESOS_ESP)+1,
        "solicitante": u["nombre"], "uid": u["id"], "rol": u["rol"],
        "recurso": d["recurso"], "motivo": d["motivo"],
        "dias": int(d.get("dias",7)),
        "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "status": "pendiente", "aprobado_por": None,
    })
    log_accion(u,"SOLICITAR_ACCESO_ESP",d["recurso"],request.remote_addr,"OK")
    return jsonify({"ok":True})

@app.route("/api/resolver_acceso", methods=["POST"])
def resolver_acceso():
    u = usuario_actual()
    if not u or ROLES[u["rol"]]["nivel"] < 4: return jsonify({"ok":False})
    d = request.json
    for s in ACCESOS_ESP:
        if s["id"]==d["id"]:
            s["status"] = d["accion"]
            s["aprobado_por"] = u["nombre"]
    log_accion(u,f"ACCESO_ESP_{d['accion'].upper()}","accesos",request.remote_addr,"OK")
    return jsonify({"ok":True})

@app.route("/api/verificar_acceso", methods=["POST"])
def verificar_acceso():
    u = usuario_actual()
    if not u: return jsonify({"ok":False})
    d = request.json
    uid = int(d.get("uid",0))
    recurso = d.get("recurso","")
    target = next((x for x in USUARIOS if x["id"]==uid), None)
    if not target: return jsonify({"ok":False,"msg":"Usuario no encontrado"})
    if target["status"]=="suspendido":
        log_accion(u,"VERIFICAR","accesos",request.remote_addr,"DENEGADO")
        return jsonify({"ok":True,"tiene":False,"razon":"Usuario suspendido"})
    tiene = tiene_acceso(target["rol"], recurso)
    status = "OK" if tiene else "DENEGADO"
    log_accion(u,"VERIFICAR",recurso,request.remote_addr,status)
    return jsonify({"ok":True,"tiene":tiene,
        "razon":"Nivel insuficiente" if not tiene else "Acceso permitido",
        "nivel_usuario": ROLES[target["rol"]]["nivel"],
        "nivel_requerido": RECURSOS[recurso]["nivel_req"]})

@app.route("/api/stats")
def stats():
    total = len(REGISTRO)
    denied = sum(1 for r in REGISTRO if r["status"]=="DENEGADO")
    by_action = {}
    for r in REGISTRO:
        by_action[r["accion"]] = by_action.get(r["accion"],0)+1
    by_rol = {}
    for r in REGISTRO:
        by_rol[r["rol"]] = by_rol.get(r["rol"],0)+1
    return jsonify({"total":total,"denied":denied,"by_action":by_action,"by_rol":by_rol})

if __name__ == "__main__":
    port = 5050
    try:
        import webview
        t = threading.Thread(target=lambda: app.run(port=port, debug=False, use_reloader=False))
        t.daemon = True
        t.start()
        import time; time.sleep(1.2)
        webview.create_window(
            "AVAC DESING — Sistema de Gestión de Accesos",
            f"http://127.0.0.1:{port}",
            width=1400, height=900,
            min_size=(1100,700),
        )
        webview.start()
    except ImportError:
        print(f"⚡ Abriendo en navegador → http://127.0.0.1:{port}")
        print("   (instala pywebview para modo escritorio: pip install pywebview)")
        import webbrowser, time
        t = threading.Thread(target=lambda: app.run(port=port, debug=False, use_reloader=False))
        t.daemon = True
        t.start()
        time.sleep(0.8)
        webbrowser.open(f"http://127.0.0.1:{port}")
        input("Presiona Enter para cerrar...\n")