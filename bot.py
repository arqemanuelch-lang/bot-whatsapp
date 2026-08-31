import os
import hmac
import hashlib
import sqlite3
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, redirect, session

app = Flask(__name__)

# ---------- Variables de entorno (se configuran en Render) ----------
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "tu_token_de_verificacion")
APP_SECRET = os.getenv("APP_SECRET")  # opcional: App Secret de Meta, para validar firma del webhook
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "cambiar_esta_clave")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "cambiar_esta_clave_tambien")

DB_PATH = "mensajes.db"

# Gemini: usamos la "Interactions API", que es la que funciona con las claves
# nuevas de Google AI Studio (las que empiezan con "AQ.").
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")


# =====================================================================
#  PRODUCTOS (Kit Maestro)
# =====================================================================
PRODUCTOS = {
    "kit_maestro": {
        "titulo": "Kit Maestro de Arquitectura y Construcción",
        "precio": "$8.000",
        "link_pago": "https://mpago.la/TU-LINK-DE-PAGO",
    }
}


# =====================================================================
#  Base de datos (SQLite)
# =====================================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mensajes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT NOT NULL,
            direccion TEXT NOT NULL,
            texto TEXT NOT NULL,
            fecha TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS contactos (
            numero TEXT PRIMARY KEY,
            nombre TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def guardar_mensaje(numero, direccion, texto):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO mensajes (numero, direccion, texto, fecha) VALUES (?, ?, ?, ?)",
        (numero, direccion, texto, datetime.utcnow().strftime("%d/%m %H:%M:%S")),
    )
    conn.commit()
    conn.close()


def guardar_contacto(numero, nombre):
    if not nombre:
        return
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO contactos (numero, nombre) VALUES (?, ?)
        ON CONFLICT(numero) DO UPDATE SET nombre = excluded.nombre
        """,
        (numero, nombre),
    )
    conn.commit()
    conn.close()


init_db()


# =====================================================================
#  Webhook: verificación (Meta la pide al vincular)
# =====================================================================
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403


def verificar_firma_meta(request_data_raw, firma_header):
    # Si no configuraste APP_SECRET, no valida firma (queda como estaba antes).
    if not APP_SECRET:
        return True
    if not firma_header or not firma_header.startswith("sha256="):
        return False
    firma_recibida = firma_header.split("sha256=", 1)[1]
    firma_calculada = hmac.new(
        APP_SECRET.encode("utf-8"), request_data_raw, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(firma_recibida, firma_calculada)


# =====================================================================
#  Webhook: recepción de mensajes
# =====================================================================
@app.route("/webhook", methods=["POST"])
def receive_message():
    firma_header = request.headers.get("X-Hub-Signature-256")
    if not verificar_firma_meta(request.get_data(), firma_header):
        return "Invalid signature", 403

    data = request.json
    try:
        value = data["entry"][0]["changes"][0]["value"]
        if "messages" not in value:
            return jsonify({"status": "ignored"}), 200

        for contacto in value.get("contacts", []):
            nombre = contacto.get("profile", {}).get("name")
            numero_contacto = contacto.get("wa_id")
            if numero_contacto:
                guardar_contacto(numero_contacto, nombre)

        message_data = value["messages"][0]
        from_number = message_data["from"]
        tipo = message_data.get("type")

        if tipo == "text":
            msg_body = message_data["text"]["body"].strip()
            guardar_mensaje(from_number, "entrante", msg_body)
            manejar_texto(from_number, msg_body.lower())

        elif tipo == "interactive":
            interactive_data = message_data["interactive"]
            opcion_id = None
            if interactive_data.get("type") == "button_reply":
                opcion_id = interactive_data["button_reply"]["id"]
            elif interactive_data.get("type") == "list_reply":
                opcion_id = interactive_data["list_reply"]["id"]

            if opcion_id:
                guardar_mensaje(from_number, "entrante", f"[Opción elegida] {opcion_id}")
                manejar_boton(from_number, opcion_id)

    except Exception as e:
        print("Error procesando mensaje:", e)

    return jsonify({"status": "success"}), 200


# =====================================================================
#  Lógica del Bot (Kit Maestro)
# =====================================================================
def manejar_texto(from_number, msg_body_lower):
    msg_limpio = msg_body_lower.strip()

    # 🎯 Mensaje exacto que activa la presentación del Kit Maestro
    MENSAJE_UNICO = "kit maestro"

    if msg_limpio == MENSAJE_UNICO:
        enviar_bienvenida_pack(from_number)
    elif GEMINI_API_KEY:
        respuesta = preguntar_a_gemini(msg_limpio)
        enviar_mensaje_texto(from_number, respuesta)
    else:
        enviar_mensaje_texto(
            from_number,
            "No entendí tu mensaje 🤔. Escribí *kit maestro* para ver la información del Kit.",
        )


def manejar_boton(from_number, opcion_id):
    if opcion_id == "ver_resena":
        producto = PRODUCTOS["kit_maestro"]

        detalle = (
            "📖 *Contenido del Kit Maestro (8 Manuales en PDF)*:\n\n"
            "1️⃣ *Cómo se proyecta una Vivienda* (J.L. Moia)\n"
            "👉 *[Ver adelanto]*: https://drive.google.com/file/d/12MHAHdQZ7Bm7RTBTD1SVdd0XxDXNO54L/view?usp=sharing\n\n"
            "2️⃣ *Curso básico de instalaciones eléctricas* (Calloni Rodrigues)\n"
            "👉 *[Ver adelanto]*: https://drive.google.com/file/d/1XTeI93qPpw0BT2J0l7qhiY_MJKd1iXHD/view?usp=sharing\n\n"
            "3️⃣ *Instalaciones Eléctricas Monofásicas* (Ing. César Anibal Rey)\n"
            "👉 *[Ver adelanto]*: https://drive.google.com/file/d/19TKBsowVtj4Q0w5OSOaZ7AeS7aBEs_Kw/view?usp=sharing\n\n"
            "4️⃣ *Manual para el Técnico Instalador Electricista Domiciliario* (Levy)\n"
            "👉 *[Ver adelanto]*: https://drive.google.com/file/d/19TKBsowVtj4Q0w5OSOaZ7AeS7aBEs_Kw/view?usp=sharing\n\n"
            "5️⃣ *Manual Práctico de la Construcción* (Jaime Nisnovich)\n"
            "👉 *[Ver adelanto]*: https://drive.google.com/file/d/1kKYvLhGcKLHqmit32kLVuiX3swnBGKGv/view?usp=sharing\n\n"
            "6️⃣ *Manual Práctico de Instalaciones Sanitarias: Tomo 1* (Nisnovich, Castro, Lázaro)\n"
            "👉 *[Ver adelanto]*: https://drive.google.com/file/d/1oHuKcqXp2SFBAyYSbmqByJFjyn7i7yuY/view?usp=sharing\n\n"
            "7️⃣ *Manual Práctico de Instalaciones Sanitarias: Tomo 2* (Nisnovich, Castro, Lázaro)\n"
            "👉 *[Ver adelanto]*: https://drive.google.com/file/d/1dQQC9-GfUjkS-GTAfzL8x1_G4A15k1GO/view?usp=sharing\n\n"
            "8️⃣ *Manual Práctico para Proyectar Buenas Viviendas* (Jaime Nisnovich)\n"
            "👉 *[Ver adelanto]*: https://drive.google.com/file/d/1_YZf_GexbX-nE-PK4fBWlv05Ygu1iVw5/view?usp=sharing\n\n"
            f"💰 *Precio promocional del Kit Completo:* {producto['precio']}"
        )

        enviar_mensaje_texto(from_number, detalle)
        enviar_botones_comerciales(from_number)

    elif opcion_id == "comprar_pack":
        producto = PRODUCTOS["kit_maestro"]
        enviar_mensaje_texto(
            from_number,
            "🎉 ¡Excelente decisión! Podés abonar por cualquiera de estos medios:\n\n"
            f"1️⃣ *Pago Online (Tarjeta / Rapipago / Dinero en cuenta):*\n"
            f"🔗 {producto['link_pago']}\n\n"
            "2️⃣ *Transferencia Bancaria o Lemon 🍋:*\n"
            "👉 *Alias:* `droply.ia`\n"
            "👉 *CVU:* `0000168300000023859803`\n"
            "👉 *Lemontag:* `$emanuel.cristian`\n"
            "👤 *Titular:* Cristian Emanuel Chicchi Verbo\n\n"
            "📩 *Importante:* Una vez realizado el pago, envianos el comprobante por este medio "
            "y te enviamos los 8 manuales al instante.",
        )

    elif opcion_id == "hablar_vendedor":
        enviar_mensaje_texto(
            from_number,
            "💬 Perfecto. En unos minutos un asesor humano te va a responder por este medio "
            "para ayudarte con tus dudas. ¡Quedate atento!",
        )
    else:
        enviar_bienvenida_pack(from_number)


def enviar_bienvenida_pack(to):
    texto = (
        "¡Hola! 👋 Gracias por tu interés en el *Kit Maestro de Arquitectura y Construcción*. "
        "Tenemos disponible el pack completo con los 8 manuales técnicos en PDF.\n\n"
        "¿Qué te gustaría hacer?"
    )
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": texto},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "comprar_pack", "title": "💳 Comprar el Kit"}},
                    {"type": "reply", "reply": {"id": "ver_resena", "title": "📚 Ver qué incluye"}},
                    {"type": "reply", "reply": {"id": "hablar_vendedor", "title": "💬 Hablar con asesor"}},
                ]
            },
        },
    }
    _enviar_interactivo(to, payload, texto)


def enviar_botones_comerciales(to):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": "¿Cómo querés avanzar?"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "comprar_pack", "title": "💳 Comprar el Kit"}},
                    {"type": "reply", "reply": {"id": "hablar_vendedor", "title": "💬 Hablar con asesor"}},
                ]
            },
        },
    }
    _enviar_interactivo(to, payload, "[Botones de compra enviados]")


def _enviar_interactivo(to, payload, texto_para_guardar):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    _post_a_meta(url, headers, payload)
    guardar_mensaje(to, "saliente", texto_para_guardar)


# =====================================================================
#  IA de Respaldo (Gemini) — Interactions API
# =====================================================================
def preguntar_a_gemini(texto_usuario):
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
    }
    payload = {
        "model": GEMINI_MODEL,
        "store": False,
        "input": (
            "Sos un asistente de ventas por WhatsApp para un negocio de manuales "
            "técnicos de construcción y arquitectura. Respondé breve, claro y "
            "amable en español, orientando siempre a que compren el Kit Maestro "
            "(escribiendo 'kit maestro'). "
            f"Mensaje del cliente: {texto_usuario}"
        ),
    }
    try:
        resp = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=30)
        if resp.status_code >= 400:
            print("Gemini devolvió error, cuerpo de la respuesta:", resp.text)
            return "Un encargado te va a responder a la brevedad para ayudarte con tu consulta."

        data = resp.json()
        for step in data.get("steps", []):
            if step.get("type") == "model_output":
                for bloque in step.get("content", []):
                    if bloque.get("type") == "text":
                        return bloque["text"]
        return "Un encargado te va a responder a la brevedad para ayudarte con tu consulta."
    except Exception as e:
        print("Error al consultar Gemini:", e)
        return "Perdón, tuve un problema. Un asesor te contestará en breve."


# =====================================================================
#  Envío de mensajes de texto simples + llamada a la API de Meta
# =====================================================================
def enviar_mensaje_texto(to, texto):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": texto},
    }
    _post_a_meta(url, headers, payload)
    guardar_mensaje(to, "saliente", texto)


def _post_a_meta(url, headers, payload):
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code >= 400:
            print("Error de Meta al enviar mensaje:", response.status_code, response.text)
    except requests.exceptions.RequestException as e:
        print("Error al llamar a la API de Meta:", e)


# =====================================================================
#  Panel web: login + ver conversaciones + responder manualmente
# =====================================================================
LOGIN_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ingresar — Panel Droply IA</title>
  <style>
    body { font-family: Arial, sans-serif; background:#f2f2f2; display:flex; align-items:center;
           justify-content:center; height:100vh; margin:0; }
    .caja { background:white; padding:24px; border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,.12);
            width:90%; max-width:320px; }
    h1 { font-size:18px; color:#1f6feb; margin-top:0; }
    input { width:100%; padding:10px; margin:10px 0; border:1px solid #ccc; border-radius:8px;
            font-size:15px; box-sizing:border-box; }
    button { width:100%; padding:10px; background:#1f6feb; color:white; border:none;
             border-radius:8px; font-size:15px; cursor:pointer; }
    .error { color:#c0392b; font-size:13px; }
  </style>
</head>
<body>
  <div class="caja">
    <h1>🔒 Panel Droply IA</h1>
    <form method="POST">
      <input type="password" name="clave" placeholder="Clave de acceso" autofocus required>
      <button type="submit">Ingresar</button>
    </form>
    {% if error %}<p class="error">{{ error }}</p>{% endif %}
  </div>
</body>
</html>
"""

PANEL_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="15">
  <title>Panel Droply IA</title>
  <style>
    body { font-family: Arial, sans-serif; background:#f2f2f2; margin:0; padding:0; display:flex; height:100vh; }
    .lista { width:100%; max-width:280px; background:white; overflow-y:auto; border-right:1px solid #ddd; }
    .lista a { display:block; padding:12px 14px; text-decoration:none; color:#222; border-bottom:1px solid #eee; }
    .lista a.activo { background:#e8f0fe; }
    .avatar { display:inline-block; width:28px; height:28px; border-radius:50%; background:#1f6feb;
              color:white; text-align:center; line-height:28px; margin-right:8px; font-size:13px; }
    .chat { flex:1; display:flex; flex-direction:column; }
    .header { padding:14px; background:white; border-bottom:1px solid #ddd; font-weight:bold; }
    .mensajes { flex:1; overflow-y:auto; padding:14px; }
    .msg { padding:8px 12px; border-radius:10px; margin:6px 0; max-width:75%; font-size:14px; }
    .entrante { background:#e8f0fe; }
    .saliente { background:#d1f5d3; margin-left:auto; text-align:right; }
    .fecha { font-size:11px; color:#888; margin-top:2px; }
    form.responder { display:flex; padding:10px; background:white; border-top:1px solid #ddd; }
    form.responder input { flex:1; padding:10px; border:1px solid #ccc; border-radius:8px; margin-right:8px; }
    form.responder button { padding:10px 16px; background:#1f6feb; color:white; border:none; border-radius:8px; }
    .salir { font-size:12px; color:#888; text-decoration:none; float:right; padding:14px; }
  </style>
</head>
<body>
  <div class="lista">
    <a href="/panel/logout" class="salir">Salir</a>
    {% for numero, datos in conversaciones.items() %}
      <a href="/panel?numero={{ numero }}" class="{{ 'activo' if numero == numero_activo else '' }}">
        <span class="avatar">{{ datos.inicial }}</span>{{ datos.nombre }}
      </a>
    {% else %}
      <p style="padding:14px;">Sin mensajes todavía.</p>
    {% endfor %}
  </div>
  <div class="chat">
    {% if numero_activo and conversaciones.get(numero_activo) %}
      <div class="header">📱 {{ conversaciones[numero_activo].nombre }} ({{ numero_activo }})</div>
      <div class="mensajes">
        {% for direccion, texto, fecha in conversaciones[numero_activo].mensajes %}
          <div class="msg {{ 'entrante' if direccion == 'entrante' else 'saliente' }}">
            {{ texto }}
            <div class="fecha">{{ fecha }}</div>
          </div>
        {% endfor %}
      </div>
      <form class="responder" method="POST" action="/panel/responder">
        <input type="hidden" name="numero" value="{{ numero_activo }}">
        <input type="text" name="texto" placeholder="Escribí una respuesta..." required>
        <button type="submit">Enviar</button>
      </form>
    {% else %}
      <div class="header">Elegí una conversación de la izquierda</div>
    {% endif %}
  </div>
</body>
</html>
"""


def logueado():
    return session.get("panel_ok") is True


@app.route("/panel/login", methods=["GET", "POST"])
def panel_login():
    error = None
    if request.method == "POST":
        clave = request.form.get("clave", "")
        if hmac.compare_digest(clave, PANEL_PASSWORD):
            session["panel_ok"] = True
            return redirect("/panel")
        error = "Clave incorrecta."
    return render_template_string(LOGIN_HTML, error=error)


@app.route("/panel/logout")
def panel_logout():
    session.pop("panel_ok", None)
    return redirect("/panel/login")


@app.route("/panel")
def panel():
    if not logueado():
        return redirect("/panel/login")

    conn = sqlite3.connect(DB_PATH)
    filas = conn.execute(
        "SELECT numero, direccion, texto, fecha FROM mensajes ORDER BY id ASC"
    ).fetchall()
    contactos_filas = conn.execute("SELECT numero, nombre FROM contactos").fetchall()
    conn.close()

    nombres = {numero: nombre for numero, nombre in contactos_filas if nombre}

    conversaciones = {}
    for numero, direccion, texto, fecha in filas:
        if numero not in conversaciones:
            nombre = nombres.get(numero, numero)
            conversaciones[numero] = {
                "nombre": nombre,
                "inicial": nombre[0].upper() if nombre else "?",
                "mensajes": [],
            }
        conversaciones[numero]["mensajes"].append((direccion, texto, fecha))

    numero_activo = request.args.get("numero")
    if not numero_activo and conversaciones:
        numero_activo = list(conversaciones.keys())[-1]

    return render_template_string(
        PANEL_HTML, conversaciones=conversaciones, numero_activo=numero_activo
    )


@app.route("/panel/responder", methods=["POST"])
def panel_responder():
    if not logueado():
        return redirect("/panel/login")
    numero = request.form.get("numero")
    texto = request.form.get("texto", "").strip()
    if numero and texto:
        enviar_mensaje_texto(numero, texto)
    return redirect(f"/panel?numero={numero}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
