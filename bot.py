import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "tu_token_de_verificacion")


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        else:
            return "Verification failed", 403
    return "Hello world", 200


@app.route("/webhook", methods=["POST"])
def receive_message():
    data = request.json
    print("Webhook recibido:", data)

    try:
        value = data["entry"][0]["changes"][0]["value"]
        if "messages" in value:
            message_data = value["messages"][0]
            from_number = message_data["from"]
            msg_body = message_data.get("text", {}).get("body", "").lower()

            if "hola" in msg_body:
                send_interactive_menu(from_number)

    except Exception as e:
        print("Error procesando mensaje:", e)

    return jsonify({"status": "success"}), 200


def send_interactive_menu(to):
    url = f"https://graph.facebook.com/v26.0/{PHONE_NUMBER_ID}/messages"
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
            "body": {"text": "¡Hola! Bienvenido a Droply IA. Selecciona una opción:"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "opcion_1", "title": "Opción 1"}},
                    {"type": "reply", "reply": {"id": "opcion_2", "title": "Opción 2"}},
                ]
            },
        },
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        print("Status:", response.status_code)
        print("Respuesta de Meta al enviar botones:", response.json())
    except requests.exceptions.RequestException as e:
        print("Error al llamar a la API de Meta:", e)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
