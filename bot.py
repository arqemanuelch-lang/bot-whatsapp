import os
import sqlite3
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# ---------- Variables de entorno (se configuran en Render) ----------
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "tu_token_de_verificacion")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")            # opcional: si no está, no usa IA
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "cambiar_esta_clave")

DB_PATH = "mensajes.db"

# GEMINI_MODEL: podés cambiarlo por variable de entorno si querés probar otros modelos
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# =====================================================================
#  ACÁ programás vos las respuestas fijas (sin IA)
# =====================================================================
PALABRAS_MENU = ["hola", "buenas", "buenos dias", "buenas tardes", "info"]

RESPUESTAS_BOTONES = {
    "opcion_1": "Elegiste la Opción 1. Acá va la info que quieras dejar programada.",
    "opcion_2": "Elegiste la Opción 2. Acá va la otra info que quieras dejar programada.",
}

RESPUESTA_DEFAULT = (
    "No entendí tu mensaje 🤔. Escribí *hola* para ver el menú de opciones."
)


# =====================================================================
#  Base de datos: guarda cada mensaje y cada contacto
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


# =====================================================================
#  Webhook: recepción de mensajes (de cualquier número del mundo)
# =====================================================================
@app.route("/webhook", methods=["POST"])
def receive_message():
    data = request.json
    print("Webhook recibido:", data)

    try:
        value = data["entry"][0]["changes"][0]["value"]
        if "messages" not in value:
            return jsonify({"status": "ignored"}), 200

        # WhatsApp manda el nombre del contacto junto con el mensaje entrante
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
            boton_id = message_data["interactive"]["button_reply"]["id"]
            guardar_mensaje(from_number, "entrante", f"[Botón elegido] {boton_id}")
            manejar_boton(from_number, boton_id)

    except Exception as e:
        print("Error procesando mensaje:", e)

    return jsonify({"status": "success"}), 200


# =====================================================================
#  Lógica de respuestas: primero reglas fijas, después IA de respaldo
# =====================================================================
def manejar_texto(from_number, msg_body_lower):
    if any(palabra in msg_body_lower for palabra in PALABRAS_MENU):
        enviar_menu_botones(from_number)
    elif GEMINI_API_KEY:
        respuesta = preguntar_a_gemini(msg_body_lower)
        enviar_mensaje_texto(from_number, respuesta)
    else:
        enviar_mensaje_texto(from_number, RESPUESTA_DEFAULT)


def manejar_boton(from_number, boton_id):
    respuesta = RESPUESTAS_BOTONES.get(boton_id, "No reconozco esa opción.")
    enviar_mensaje_texto(from_number, respuesta)


# =====================================================================
#  IA de respaldo (Gemini) — solo se usa si el mensaje no matchea nada
# =====================================================================
def preguntar_a_gemini(texto_usuario):
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
    }
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Sos un asistente de atención al cliente por WhatsApp "
                            "para el negocio Droply IA. Respondé breve, claro y "
                            "amable, en español. Si no sabés algo con certeza, "
                            "decí que un encargado va a responder a la brevedad. "
                            f"Mensaje del cliente: {texto_usuario}"
                        )
                    }
                ]
            }
        ]
    }

    print("---- Llamando a Gemini ----")
    print("URL:", GEMINI_URL)
    print("Payload enviado:", payload)

    try:
        resp = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=40)

        print("Status code de Gemini:", resp.status_code)
        print("Body crudo de la respuesta de Gemini:", resp.text)

        if resp.status_code >= 400:
            try:
                error_json = resp.json()
                print("Detalle del error (JSON):", error_json.get("error", error_json))
            except ValueError:
                print("La respuesta de error no vino en JSON.")
            resp.raise_for_status()

        data = resp.json()

        candidatos = data.get("candidates", [])
        if not candidatos:
            print("Gemini no devolvió 'candidates'. Respuesta completa:", data)
            raise ValueError("Gemini no devolvió candidatos")

        partes = candidatos[0].get("content", {}).get("parts", [])
        for bloque in partes:
            if "text" in bloque:
                return bloque["text"]

        raise ValueError("Gemini no devolvió texto en 'parts'")

    except Exception as e:
        print("Error al consultar Gemini:", repr(e))
        return "Perdón, tuve un problema para responderte. Un encargado te va a contestar pronto."


# =====================================================================
#  Envío de mensajes por la API de WhatsApp
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


def enviar_menu_botones(to):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": "¡Hola! Bienvenido a Droply IA. Elegí una opción:"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "opcion_1", "title": "Opción 1"}},
                    {"type": "reply", "reply": {"id": "opcion_2", "title": "Opción 2"}},
                ]
            },
        },
    }
    _post_a_meta(url, headers, payload)
    guardar_mensaje(to, "saliente", "[Menú de botones enviado]")


def _post_a_meta(url, headers, payload):
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        print("Status:", response.status_code)
        print("Respuesta de Meta:", response.json())
    except requests.exceptions.RequestException as e:
        print("Error al llamar a la API de Meta:", e)


# =====================================================================
#  Panel web estilo WhatsApp
#  Se abre en: https://TU-BOT.onrender.com/panel?clave=TU_CLAVE
# =====================================================================
PANEL_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="20">
  <title>Droply IA — Mensajes</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
      margin: 0; height: 100vh; display: flex;
      background: #f0f2f5;
    }
    /* ---------- Barra lateral de contactos ---------- */
    .sidebar {
      width: 320px; min-width: 260px; background: #fff;
      border-right: 1px solid #e9edef; display: flex; flex-direction: column;
    }
    .sidebar-header {
      background: #075E54; color: white; padding: 16px;
      font-size: 17px; font-weight: 600;
    }
    .contact-list { overflow-y: auto; flex: 1; }
    .contact {
      display: flex; align-items: center; gap: 12px;
      padding: 12px 16px; cursor: pointer; text-decoration: none; color: inherit;
      border-bottom: 1px solid #f2f2f2;
    }
    .contact:hover, .contact.active { background: #f5f6f6; }
    .avatar {
      width: 42px; height: 42px; border-radius: 50%; background: #25D366;
      color: white; display: flex; align-items: center; justify-content: center;
      font-weight: 600; font-size: 16px; flex-shrink: 0;
    }
    .contact-info { min-width: 0; flex: 1; }
    .contact-name { font-size: 15px; font-weight: 500; color: #111b21; }
    .contact-preview {
      font-size: 13px; color: #667781; white-space: nowrap;
      overflow: hidden; text-overflow: ellipsis;
    }
    .contact-time { font-size: 11px; color: #667781; }
    /* ---------- Panel de conversación ---------- */
    .chat-panel { flex: 1; display: flex; flex-direction: column; }
    .chat-header {
      background: #f0f2f5; padding: 14px 20px; border-bottom: 1px solid #e9edef;
      display: flex; align-items: center; gap: 12px;
    }
    .chat-header .contact-name { font-size: 16px; }
    .chat-body {
      flex: 1; overflow-y: auto; padding: 20px 8%;
      background-color: #efeae2;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='60' height='60'%3E%3C/svg%3E");
    }
    .msg-row { display: flex; margin-bottom: 4px; }
    .msg-row.entrante { justify-content: flex-start; }
    .msg-row.saliente { justify-content: flex-end; }
    .bubble {
      max-width: 65%; padding: 8px 12px; border-radius: 8px;
      font-size: 14.5px; line-height: 1.4; box-shadow: 0 1px 0.5px rgba(0,0,0,.13);
      position: relative;
    }
    .entrante .bubble { background: #fff; border-top-left-radius: 0; }
    .saliente .bubble { background: #d9fdd3; border-top-right-radius: 0; }
    .bubble .fecha {
      font-size: 10.5px; color: #667781; text-align: right; margin-top: 4px;
    }
    .empty-state {
      flex: 1; display: flex; align-items: center; justify-content: center;
      color: #667781; font-size: 15px; flex-direction: column; gap: 10px;
    }
  </style>
</head>
<body>

  <div class="sidebar">
    <div class="sidebar-header">📋 Droply IA</div>
    <div class="contact-list">
      {% for numero, info in conversaciones.items() %}
        {% set ultimo = info.mensajes[-1] %}
        <a class="contact {{ 'active' if numero == numero_activo else '' }}" href="?clave={{ clave }}&numero={{ numero }}">
          <div class="avatar">{{ info.inicial }}</div>
          <div class="contact-info">
            <div class="contact-name">{{ info.nombre }}</div>
            <div class="contact-preview">{{ ultimo[1][:40] }}</div>
          </div>
          <div class="contact-time">{{ ultimo[2].split(' ')[1] if ' ' in ultimo[2] else '' }}</div>
        </a>
      {% else %}
        <div style="padding:16px; color:#667781;">Todavía no llegaron mensajes.</div>
      {% endfor %}
    </div>
  </div>

  <div class="chat-panel">
    {% if numero_activo and numero_activo in conversaciones %}
      <div class="chat-header">
        <div class="avatar">{{ conversaciones[numero_activo].inicial }}</div>
        <div>
          <div class="contact-name">{{ conversaciones[numero_activo].nombre }}</div>
          <div class="contact-preview">{{ numero_activo }}</div>
        </div>
      </div>
      <div class="chat-body">
        {% for direccion, texto, fecha in conversaciones[numero_activo].mensajes %}
          <div class="msg-row {{ direccion }}">
            <div class="bubble">
              {{ texto }}
              <div class="fecha">{{ fecha }}</div>
            </div>
          </div>
        {% endfor %}
      </div>
    {% else %}
      <div class="empty-state">
        <div style="font-size:40px;">💬</div>
        <div>Elegí una conversación para verla acá</div>
      </div>
    {% endif %}
  </div>

</body>
</html>
"""


@app.route("/panel")
def panel():
    clave = request.args.get("clave")
    if clave != PANEL_PASSWORD:
        return "Acceso denegado. Agregá ?clave=TU_CLAVE al final de la URL.", 403

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
        # Por defecto, abrí la conversación más reciente
        numero_activo = list(conversaciones.keys())[-1]

    return render_template_string(
        PANEL_HTML,
        conversaciones=conversaciones,
        numero_activo=numero_activo,
        clave=clave,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
