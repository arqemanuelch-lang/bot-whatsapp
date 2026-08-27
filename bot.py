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

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)

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
#  Base de datos: guarda cada mensaje entrante y saliente
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
    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}
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
    try:
        resp = requests.post(
            GEMINI_URL, headers=headers, params=params, json=payload, timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print("Error al consultar Gemini:", e)
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
#  Panel web para ver los mensajes desde el celular o la compu
#  Se abre en: https://TU-BOT.onrender.com/panel?clave=TU_CLAVE
# =====================================================================
PANEL_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="15">
  <title>Panel Droply IA</title>
  <style>
    body { font-family: Arial, sans-serif; background:#f2f2f2; margin:0; padding:16px; }
    h1 { font-size: 18px; color:#1f6feb; }
    .numero { background:white; border-radius:10px; margin-bottom:14px; padding:12px; box-shadow:0 1px 3px rgba(0,0,0,.1); }
    .numero h2 { font-size:15px; margin:0 0 8px 0; }
    .msg { padding:6px 10px; border-radius:8px; margin:4px 0; max-width:85%; font-size:14px; }
    .entrante { background:#e8f0fe; }
    .saliente { background:#d1f5d3; margin-left:auto; text-align:right; }
    .fecha { font-size:11px; color:#888; }
  </style>
</head>
<body>
  <h1>📋 Mensajes — Droply IA (se actualiza solo cada 15s)</h1>
  {% for numero, mensajes in conversaciones.items() %}
    <div class="numero">
      <h2>📱 {{ numero }}</h2>
      {% for direccion, texto, fecha in mensajes %}
        <div class="msg {{ 'entrante' if direccion=='entrante' else 'saliente' }}">
          {{ texto }}
          <div class="fecha">{{ fecha }}</div>
        </div>
      {% endfor %}
    </div>
  {% else %}
    <p>Todavía no llegaron mensajes.</p>
  {% endfor %}
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
    conn.close()

    conversaciones = {}
    for numero, direccion, texto, fecha in filas:
        conversaciones.setdefault(numero, []).append((direccion, texto, fecha))

    return render_template_string(PANEL_HTML, conversaciones=conversaciones)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
