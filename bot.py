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
APP_SECRET = os.getenv("APP_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "cambiar_esta_clave")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "cambiar_esta_clave_tambien")

DB_PATH = "mensajes.db"

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

PALABRAS_MENU = ["hola", "buenas", "buenos dias", "buenas tardes", "info", "menu"]

RESPUESTA_DEFAULT = (
    "No entendí tu mensaje 🤔. Escribí *hola* para ver la información del Kit."
)

# =====================================================================
#  PRODUCTOS (Kit Maestro)
# =====================================================================
PRODUCTOS = {
    "kit_maestro": {
        "titulo": "Kit Maestro de Arquitectura y Construcción",
        "precio": "$15.000",  # Acá ponés tu precio real
        "link_pago": "https://mpago.la/TU-LINK-DE-PAGO",  # Acá tu link de pago
        
        # ACÁ QUEDA FIJADO EL MENSAJE ENTRANTE EXACTO DEL ANUNCIO:
        "frases_entrada": [
            "hola, quiero mas informacion del kit maestro de la arquitectura y construccion",
            "kit maestro",
            "arquitectura y construccion"
        ],
        
        "mensaje_bienvenida": (
            "¡Incluye los 8 manuales fundamentales en PDF:\n"
            "1. Cómo se proyecta una Vivienda (J.L. Moia)\n"
            "2. Curso básico de instalaciones eléctricas (Calloni Rodrigues)\n"
            "3. Instalaciones Eléctricas Monofásicas\n"
            "4. Manual para el Técnico Instalador Electricista Domiciliario\n"
            "5. Manual Práctico de Construcción\n"
            "6. Manual Práctico de Instalaciones Sanitarias (Tomo 1)\n"
            "7. Manual Práctico de Instalaciones Sanitarias (Tomo 2)\n"
            "8. Manual Práctico para Proyectar Buenas Viviendas"
        ),
        "imagenes": [
            "https://tusitio.com/imagenes/pack-portada.jpg"
        ],
        "video": "",
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
#  Webhook Web
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
    if not APP_SECRET:
        return True
    if not firma_header or not firma_header.startswith("sha256="):
        return False
    firma_recibida = firma_header.split("sha256=", 1)[1]
    firma_calculada = hmac.new(
        APP_SECRET.encode("utf-8"), request_data_raw, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(firma_recibida, firma_calculada)

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
    # Verificamos si mandó el saludo o la frase exacta del Kit Maestro
    coincide_frase = any(frase in msg_body_lower for frase in PRODUCTOS["kit_maestro"]["frases_entrada"])
    es_saludo = any(palabra in msg_body_lower for palabra in PALABRAS_MENU)

    if coincide_frase or es_saludo:
        enviar_bienvenida_pack(from_number)
    elif GEMINI_API_KEY:
        respuesta = preguntar_a_gemini(msg_body_lower)
        enviar_mensaje_texto(from_number, respuesta)
    else:
        enviar_bienvenida_pack(from_number)

def manejar_boton(from_number, opcion_id):
    if opcion_id == "ver_resena":
        producto = PRODUCTOS["kit_maestro"]
        detalle = (
            "📖 *Detalle del Kit Maestro:*\n\n"
            f"{producto['mensaje_bienvenida']}\n\n"
            f"💰 *Precio promocional:* {producto['precio']}"
        )
        enviar_mensaje_texto(from_number, detalle)
        enviar_botones_comerciales(from_number)

    elif opcion_id == "comprar_pack":
        producto = PRODUCTOS["kit_maestro"]
        enviar_mensaje_texto(
            from_number,
            f"🎉 ¡Excelente decisión! Podés abonar de forma segura en el siguiente link:\n\n"
            f"🔗 {producto['link_pago']}\n\n"
            "Una vez realizado el pago, envianos el comprobante por acá y te mandamos los 8 PDFs al instante. 📥"
        )

    elif opcion_id == "hablar_vendedor":
        enviar_mensaje_texto(
            from_number,
            "💬 Perfecto. En unos minutos un asesor humano te va a responder por este medio para ayudarte con tus dudas. ¡Quedate atento!"
        )
    else:
        enviar_bienvenida_pack(from_number)

def enviar_bienvenida_pack(to):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    texto = (
        "¡Hola! 👋 Gracias por tu interés en el **Kit Maestro de Arquitectura y Construcción**. "
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
                    {"type": "reply", "reply": {"id": "ver_resena", "title": "📖 Ver qué incluye"}},
                    {"type": "reply", "reply": {"id": "hablar_vendedor", "title": "💬 Hablar con asesor"}},
                ]
            },
        },
    }
    _post_a_meta(url, headers, payload)
    guardar_mensaje(to, "saliente", texto)

def enviar_botones_comerciales(to):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    texto = "¿Cómo querés avanzar?"
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
                    {"type": "reply", "reply": {"id": "hablar_vendedor", "title": "💬 Hablar con asesor"}},
                ]
            },
        },
    }
    _post_a_meta(url, headers, payload)

# =====================================================================
#  IA de Respaldo (Gemini)
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
                            "Sos un asistente de ventas por WhatsApp para un negocio de manuales "
                            "técnicos de construcción y arquitectura. Respondé breve, claro y "
                            "amable en español, orientando siempre a que compren el Kit Maestro. "
                            f"Mensaje del cliente: {texto_usuario}"
                        )
                    }
                ]
            }
        ]
    }
    try:
        resp = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=30)
        if resp.status_code >= 400:
            return "Un encargado te va a responder a la brevedad para ayudarte con tu consulta."
        data = resp.json()
        candidatos = data.get("candidates", [])
        if candidatos:
            partes = candidatos[0].get("content", {}).get("parts", [])
            for bloque in partes:
                if "text" in bloque:
                    return bloque["text"]
    except Exception:
        pass
    return "Perdón, tuve un problema. Un asesor te contestará en breve."

# =====================================================================
#  Funciones de Envío WhatsApp & Panel Web
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
        requests.post(url, headers=headers, json=payload, timeout=10)
    except requests.exceptions.RequestException as e:
        print("Error al llamar a la API de Meta:", e)

LOGIN_HTML = """<!doctype html>..."""
PANEL_HTML = """<!doctype html>..."""

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
    filas = conn.execute("SELECT numero, direccion, texto, fecha FROM mensajes ORDER BY id ASC").fetchall()
    contactos_filas = conn.execute("SELECT numero, nombre FROM contactos").fetchall()
    conn.close()
    nombres = {numero: nombre for numero, nombre in contactos_filas if nombre}
    conversaciones = {}
    for numero, direccion, texto, fecha in filas:
        if numero not in conversaciones:
            nombre = nombres.get(numero, numero)
            conversaciones[numero] = {"nombre": nombre, "inicial": nombre[0].upper() if nombre else "?", "mensajes": []}
        conversaciones[numero]["mensajes"].append((direccion, texto, fecha))
    numero_activo = request.args.get("numero")
    if not numero_activo and conversaciones:
        numero_activo = list(conversaciones.keys())[-1]
    return render_template_string(PANEL_HTML, conversaciones=conversaciones, numero_activo=numero_activo)

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
