import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ---------- Variables de entorno (se configuran en Render) ----------
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "tu_token_de_verificacion")


# =====================================================================
#  ACÁ programás vos las respuestas. No hay IA, todo es fijo.
# =====================================================================

# Palabras clave que activan el menú de botones (vos agregás las que quieras)
PALABRAS_MENU = ["hola", "buenas", "buenos dias", "buenas tardes", "info"]

# Respuestas fijas para cuando el usuario aprieta un botón
RESPUESTAS_BOTONES = {
    "opcion_1": "Elegiste la Opción 1. Acá va la info que quieras dejar programada.",
    "opcion_2": "Elegiste la Opción 2. Acá va la otra info que quieras dejar programada.",
}

# Respuesta por defecto si no reconoce el mensaje
RESPUESTA_DEFAULT = (
    "No entendí tu mensaje 🤔. Escribí *hola* para ver el menú de opciones."
)


# =====================================================================
#  Webhook: verificación (Meta la pide una sola vez al vincular)
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
            # Es una notificación de "entregado/leído", no un mensaje nuevo
            return jsonify({"status": "ignored"}), 200

        message_data = value["messages"][0]
        from_number = message_data["from"]
        tipo = message_data.get("type")

        if tipo == "text":
            msg_body = message_data["text"]["body"].strip().lower()
            manejar_texto(from_number, msg_body)

        elif tipo == "interactive":
            # El usuario apretó un botón
            boton_id = message_data["interactive"]["button_reply"]["id"]
            manejar_boton(from_number, boton_id)

    except Exception as e:
        print("Error procesando mensaje:", e)

    return jsonify({"status": "success"}), 200


# =====================================================================
#  Lógica de respuestas (sin IA, todo si/entonces programado por vos)
# =====================================================================
def manejar_texto(from_number, msg_body):
    if any(palabra in msg_body for palabra in PALABRAS_MENU):
        enviar_menu_botones(from_number)
    else:
        enviar_mensaje_texto(from_number, RESPUESTA_DEFAULT)


def manejar_boton(from_number, boton_id):
    respuesta = RESPUESTAS_BOTONES.get(
        boton_id, "No reconozco esa opción."
    )
    enviar_mensaje_texto(from_number, respuesta)


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


def _post_a_meta(url, headers, payload):
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        print("Status:", response.status_code)
        print("Respuesta de Meta:", response.json())
    except requests.exceptions.RequestException as e:
        print("Error al llamar a la API de Meta:", e)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
