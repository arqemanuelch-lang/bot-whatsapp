import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "¡El Bot está activo!", 200

# Ruta para verificar y recibir mensajes de WhatsApp
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        # Meta envía una petición GET para verificar el token
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        
        VERIFY_TOKEN = "miprimertoken123"
        
        if mode and token:
            if mode == "subscribe" and token == VERIFY_TOKEN:
                return challenge, 200
            else:
                return "Error de token", 403
        return "Hola", 200

    elif request.method == "POST":
        # Aquí es donde el bot recibirá los mensajes de los usuarios más adelante
        data = request.json
        print(data)
        return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
