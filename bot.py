import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Lee el token que guardamos en Render
TOKEN = os.environ.get("WHATSAPP_TOKEN")
# El Phone Number ID de tu cuenta de Meta (lo sacas de tu panel de WhatsApp API)
PHONE_NUMBER_ID = "122930466027325"

@app.route("/", methods=["GET"])
def home():
    return "¡El Bot de Droply IA está activo y respondiendo!", 200

# Ruta para verificar y recibir mensajes de WhatsApp
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    # Verificación del webhook con Meta (GET)
    if request.method == "GET":
        verify_token = "mi_token_de_verificacion" # El token que pusiste en Meta
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        
        if mode and token:
            if mode == "subscribe" and token == verify_token:
                return challenge, 200
            else:
                return "Verification failed", 403
        return "Hello World", 200

    # Recepción de mensajes (POST)
    elif request.method == "POST":
        data = request.json
        print(data) # Esto es lo que ves en los logs de Render
        
        try:
            # Intentamos extraer el mensaje entrante
            entry = data["entry"][0]
            changes = entry["changes"][0]
            value = changes["value"]
            
            if "messages" in value:
                message = value["messages"][0]
                from_number = message["from"] # Número del cliente
                
                # Responde automáticamente con un menú de botones
                enviar_botones(from_number)
                
        except Exception as e:
            print(f"Error procesando el mensaje: {e}")
            
        return "EVENT_RECEIVED", 200

def enviar_botones(to_phone):
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Estructura del mensaje interactivo con botones
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": "¡Hola! Bienvenido a Droply IA 🤖. ¿En qué te podemos ayudar hoy?"
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": "btn_1",
                            "title": "Ver Catálogo 🛍️"
                        }
                    },
                    {
                        "type": "reply",
                        "reply": {
                            "id": "btn_2",
                            "title": "Hablar con Asesor 8️⃣"
                        }
                    }
                ]
            }
        }
    }
    
    response = requests.post(url, headers=headers, json=payload)
    print("Respuesta de Meta al enviar botones:", response.json())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
