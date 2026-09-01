import os
import hmac
import hashlib
import sqlite3
import threading
import time
import unicodedata
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, redirect, session

# =====================================================================
#  Toda la configuración específica de ESTE negocio (productos, precios,
#  datos bancarios, mensajes de bienvenida, palabras clave, etc.) vive
#  en config.py. Este archivo (app.py) es el "motor" genérico del bot:
#  no debería hacer falta tocarlo para lanzar el bot de otro negocio,
#  solo hay que reescribir config.py.
# =====================================================================
from config import (
    NOMBRE_NEGOCIO,
    PALABRA_CLAVE_MENU,
    MENSAJE_BIENVENIDA_MENU,
    NUMERO_RESPALDO_DEFAULT,
    DATOS_TRANSFERENCIA,
    PROMPT_SISTEMA_IA,
    PALABRAS_ACTIVADORAS,
    PRODUCTOS,
    PALABRAS_POR_PRODUCTO,
)

app = Flask(__name__)

# ---------- Variables de entorno (se configuran en Render) ----------
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "tu_token_de_verificacion")
APP_SECRET = os.getenv("APP_SECRET")  # opcional: App Secret de Meta, para validar firma del webhook
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # opcional: respaldo gratuito si Gemini falla

# --- Notificaciones y respuestas por Telegram (opcional) ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # el token que te da @BotFather
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # tu chat_id personal de Telegram
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL")  # ej: https://tu-app.onrender.com/telegram_webhook
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "cambiar_esta_clave")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "cambiar_esta_clave_tambien")

DB_PATH = "mensajes.db"

# ---------------------------------------------------------------------
# Recordatorio automático de compra: si le mandamos la ficha de un producto
# a alguien y no toca NINGÚN botón en 3 minutos, le mandamos un mensaje
# reofreciendo el kit. Se cancela apenas la persona toca cualquier botón,
# o si un humano le responde/aprueba el pago desde el panel.
#
# NOTA IMPORTANTE: esto usa threading.Timer en memoria. Funciona bien
# mientras la app corra en UN SOLO proceso/worker (lo normal en Render para
# un bot chico). Si en el futuro escalás a varios workers, esto habría que
# migrarlo a algo persistente (una tabla en la base + un cron/scheduler).
# =====================================================================
SEGUNDOS_RECORDATORIO = 180  # 3 minutos
RECORDATORIOS_PENDIENTES = {}  # numero -> threading.Timer
ULTIMA_INTERACCION = {}  # numero -> timestamp (time.time()) de la última acción del usuario


def marcar_interaccion(numero):
    """Registra que este número acaba de interactuar (mandó un mensaje o tocó
    un botón). Se usa para evitar que el recordatorio de 3 minutos se dispare
    justo en el instante en que la persona ya está actuando (carrera de
    tiempos entre 'cancelar el aviso' y 'el aviso ya se estaba mandando')."""
    ULTIMA_INTERACCION[numero] = time.time()


def cancelar_recordatorio(numero):
    timer = RECORDATORIOS_PENDIENTES.pop(numero, None)
    if timer:
        timer.cancel()


def programar_recordatorio_compra(numero, clave, delay_segundos=SEGUNDOS_RECORDATORIO):
    """Programa el mensaje de recordatorio. Si ya había uno pendiente para
    este número, lo reemplaza (reinicia el conteo de 3 minutos)."""
    cancelar_recordatorio(numero)

    def _enviar_recordatorio():
        RECORDATORIOS_PENDIENTES.pop(numero, None)

        # Si la persona interactuó hace muy poquito (pudo haber tocado un
        # botón justo en el instante en que este aviso ya se estaba
        # disparando), no lo mandamos: ya está activa en la conversación.
        ultima = ULTIMA_INTERACCION.get(numero, 0)
        if time.time() - ultima < 10:
            return

        producto = PRODUCTOS.get(clave)
        if not producto:
            return
        enviar_mensaje_texto(
            numero,
            f"👋 ¿Seguís pensando en el *{producto['titulo']}*?\n\n"
            f"Te lo dejamos por solo *{producto['precio']}*: "
            f"{len(producto['manuales'])} manuales técnicos completos, listos para descargar. 📚\n\n"
            "Cuando quieras avanzar, tocá el botón de abajo 👇",
        )
        enviar_botones_pack(numero, clave, texto="¿Cómo querés avanzar?", incluir_ver=True)

    timer = threading.Timer(delay_segundos, _enviar_recordatorio)
    timer.daemon = True
    RECORDATORIOS_PENDIENTES[numero] = timer
    timer.start()

# Gemini: usamos la "Interactions API", que es la que funciona con las claves
# nuevas de Google AI Studio (las que empiezan con "AQ.").
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# Número de respaldo al que el cliente puede escribir directamente con su
# comprobante si ya pagó y no obtuvo respuesta a tiempo.
NUMERO_RESPALDO = os.getenv("NUMERO_RESPALDO", NUMERO_RESPALDO_DEFAULT)


def detectar_producto_por_texto(texto_normalizado):
    """Busca si el texto (ya pasado por _normalizar) menciona algún producto
    puntual, usando PALABRAS_POR_PRODUCTO. Devuelve la clave del producto
    encontrado, o None si no matchea ninguno."""
    for clave, palabras in PALABRAS_POR_PRODUCTO.items():
        if clave not in PRODUCTOS:
            continue  # por si quedó una clave vieja sin su producto correspondiente
        for palabra in palabras:
            if _normalizar(palabra) in texto_normalizado:
                return clave
    return None


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
            nombre TEXT,
            modo_ia INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    # Si la tabla ya existía de antes (sin la columna modo_ia), la agregamos.
    try:
        conn.execute("ALTER TABLE contactos ADD COLUMN modo_ia INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # la columna ya existe
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS comprobantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT NOT NULL,
            media_id TEXT NOT NULL,
            mime_type TEXT,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            fecha TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mensajes_procesados (
            id TEXT PRIMARY KEY,
            fecha TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_mapeo (
            telegram_message_id INTEGER PRIMARY KEY,
            numero_whatsapp TEXT NOT NULL,
            fecha TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def ya_fue_procesado(message_id):
    """Chequea si ya procesamos este mensaje antes (Meta a veces reenvía el
    mismo webhook más de una vez, por ejemplo si el servidor tardó en
    responder). Si ya lo vimos, lo ignoramos para no responder duplicado."""
    if not message_id:
        return False
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO mensajes_procesados (id, fecha) VALUES (?, ?)",
            (message_id, datetime.utcnow().strftime("%d/%m %H:%M:%S")),
        )
        conn.commit()
        return False  # se pudo insertar => es la primera vez que lo vemos
    except sqlite3.IntegrityError:
        return True  # ya existía ese id => es un duplicado, lo ignoramos
    finally:
        conn.close()


def registrar_mapeo_telegram(telegram_message_id, numero_whatsapp):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO telegram_mapeo (telegram_message_id, numero_whatsapp, fecha) VALUES (?, ?, ?)",
        (telegram_message_id, numero_whatsapp, datetime.utcnow().strftime("%d/%m %H:%M:%S")),
    )
    conn.commit()
    conn.close()


def obtener_numero_por_mensaje_telegram(telegram_message_id):
    conn = sqlite3.connect(DB_PATH)
    fila = conn.execute(
        "SELECT numero_whatsapp FROM telegram_mapeo WHERE telegram_message_id = ?",
        (telegram_message_id,),
    ).fetchone()
    conn.close()
    return fila[0] if fila else None


def enviar_notificacion_telegram(numero, resumen_texto):
    """Le avisa al dueño del negocio por Telegram que llegó un mensaje nuevo.
    Si más adelante responde a ESE mensaje de Telegram (con la función
    'responder' de Telegram), el bot sabe a qué número de WhatsApp
    reenviarle la respuesta (ver /telegram_webhook)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return  # Telegram no está configurado, no hacemos nada
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": (
                f"📩 *Nuevo mensaje de {numero}*\n\n"
                f"{resumen_texto}\n\n"
                "↩️ Respondé a este mensaje (mantené presionado y elegí 'Responder') "
                "para contestarle directo por WhatsApp."
            ),
            "parse_mode": "Markdown",
        }
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code >= 400:
            print("Error notificando a Telegram:", resp.text)
            return
        data = resp.json()
        telegram_message_id = data.get("result", {}).get("message_id")
        if telegram_message_id:
            registrar_mapeo_telegram(telegram_message_id, numero)
    except Exception as e:
        print("Error notificando a Telegram:", e)


def configurar_webhook_telegram():
    """Le dice a Telegram a qué URL mandar los updates (mensajes que te
    escriben o respuestas que hacés). Se llama solo al arrancar la app."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_WEBHOOK_URL:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
        requests.post(url, json={"url": TELEGRAM_WEBHOOK_URL}, timeout=10)
    except Exception as e:
        print("Error configurando webhook de Telegram:", e)


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


def activar_modo_ia(numero):
    """Marca que este número está siendo atendido por la IA (después de tocar
    'Hablar con asesor'), hasta que un humano le responda desde el panel."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO contactos (numero, nombre, modo_ia) VALUES (?, NULL, 1)
        ON CONFLICT(numero) DO UPDATE SET modo_ia = 1
        """,
        (numero,),
    )
    conn.commit()
    conn.close()


def desactivar_modo_ia(numero):
    """Saca a este número del modo IA (por ejemplo, cuando un humano le
    responde manualmente desde el panel)."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE contactos SET modo_ia = 0 WHERE numero = ?", (numero,))
    conn.commit()
    conn.close()


def esta_en_modo_ia(numero):
    conn = sqlite3.connect(DB_PATH)
    fila = conn.execute("SELECT modo_ia FROM contactos WHERE numero = ?", (numero,)).fetchone()
    conn.close()
    return bool(fila and fila[0] == 1)


def guardar_comprobante(numero, media_id, mime_type):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO comprobantes (numero, media_id, mime_type, estado, fecha) VALUES (?, ?, ?, 'pendiente', ?)",
        (numero, media_id, mime_type, datetime.utcnow().strftime("%d/%m %H:%M:%S")),
    )
    conn.commit()
    conn.close()


def obtener_comprobantes_pendientes_por_numero():
    conn = sqlite3.connect(DB_PATH)
    filas = conn.execute(
        "SELECT numero, id, media_id, mime_type, fecha FROM comprobantes WHERE estado = 'pendiente'"
    ).fetchall()
    conn.close()
    resultado = {}
    for numero, comp_id, media_id, mime_type, fecha in filas:
        resultado[numero] = {"id": comp_id, "media_id": media_id, "mime_type": mime_type, "fecha": fecha}
    return resultado


def marcar_comprobante_aprobado(comprobante_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE comprobantes SET estado = 'aprobado' WHERE id = ?", (comprobante_id,))
    conn.commit()
    conn.close()


init_db()
configurar_webhook_telegram()


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

        # Meta a veces reenvía el mismo mensaje más de una vez (por ejemplo si
        # el servidor tardó en responder). Si ya procesamos este mensaje
        # (mismo wamid), lo ignoramos para no contestar duplicado.
        message_id = message_data.get("id")
        if ya_fue_procesado(message_id):
            return jsonify({"status": "duplicado_ignorado"}), 200

        if tipo == "text":
            msg_body = message_data["text"]["body"].strip()
            guardar_mensaje(from_number, "entrante", msg_body)
            enviar_notificacion_telegram(from_number, msg_body)

            referral = message_data.get("referral")
            if referral:
                # La persona llegó tocando un anuncio de Facebook/Instagram
                # (Click to WhatsApp). Meta manda este dato en 'referral' sin
                # importar qué haya escrito, así que respondemos automático
                # sí o sí, independientemente de las palabras activadoras.
                manejar_entrada_desde_ads(from_number, referral, msg_body.lower())
            else:
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
                enviar_notificacion_telegram(from_number, f"👆 Eligió: {opcion_id}")
                manejar_boton(from_number, opcion_id)

        elif tipo in ("image", "document"):
            media_obj = message_data.get(tipo, {})
            media_id = media_obj.get("id")
            mime_type = media_obj.get("mime_type", "")
            if media_id:
                guardar_comprobante(from_number, media_id, mime_type)
                cancelar_recordatorio(from_number)
                guardar_mensaje(
                    from_number, "entrante", "📎 Comprobante recibido (pendiente de aprobación)"
                )
                enviar_notificacion_telegram(
                    from_number,
                    "📎 Mandó un comprobante de pago. Andá al panel para revisarlo y aprobarlo.",
                )
                enviar_mensaje_texto(
                    from_number,
                    "¡Recibimos tu comprobante! 📎 En breve lo revisamos y te enviamos los "
                    "8 manuales completos. Gracias por tu paciencia.",
                )

    except Exception as e:
        print("Error procesando mensaje:", e)

    return jsonify({"status": "success"}), 200


@app.route("/telegram_webhook", methods=["POST"])
def telegram_webhook():
    """Recibe las respuestas que mandás por Telegram. Si le respondiste
    ('Reply') a una notificación de un mensaje de WhatsApp, reenvía tu texto
    directo a ese cliente por WhatsApp."""
    try:
        data = request.json or {}
        mensaje_telegram = data.get("message") or data.get("edited_message")
        if not mensaje_telegram:
            return jsonify({"status": "ignorado"}), 200

        texto_admin = (mensaje_telegram.get("text") or "").strip()
        respondido_a = mensaje_telegram.get("reply_to_message")

        if not texto_admin or not respondido_a:
            return jsonify({"status": "ignorado"}), 200

        telegram_message_id = respondido_a.get("message_id")
        numero = obtener_numero_por_mensaje_telegram(telegram_message_id)

        if numero:
            desactivar_modo_ia(numero)  # ya lo está atendiendo un humano
            cancelar_recordatorio(numero)
            enviar_mensaje_texto(numero, texto_admin)
        elif TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            # No pudimos identificar a qué cliente corresponde esta respuesta.
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": "⚠️ No pude identificar a qué cliente corresponde esa respuesta. "
                    "Asegurate de usar 'Responder' sobre la notificación original.",
                },
                timeout=10,
            )
    except Exception as e:
        print("Error procesando webhook de Telegram:", e)

    return jsonify({"status": "ok"}), 200


# =====================================================================
#  Lógica del Bot (Kit Maestro)
# =====================================================================
def _normalizar(texto):
    """Pasa a minúsculas y saca tildes, para que 'información' e 'informacion' matcheen igual."""
    texto = texto.strip().lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def manejar_entrada_desde_ads(from_number, referral, msg_body_lower=""):
    """Se dispara automáticamente cuando alguien te escribe tocando un anuncio
    de Facebook o Instagram (Click to WhatsApp), sin importar qué haya
    escrito. 'referral' trae datos del anuncio: headline, source_type
    ('ad' o 'post'), source_url, media_type, etc.

    A diferencia del saludo genérico, acá NO mandamos la lista para elegir
    pack: la persona ya clickeó un anuncio (o escribió el texto pre-cargado
    de un anuncio), así que va directo a la ficha del producto correspondiente.

    Para saber CUÁL producto, primero miramos el texto del propio mensaje
    (el que escribió/mandó la persona) y también el headline/body que venga
    en 'referral'. Si ninguno matchea ningún producto puntual, usamos
    "kit_maestro" como default (útil mientras solo tengas un pack).
    """
    titulo_anuncio = referral.get("headline") or referral.get("source_type") or "anuncio"
    guardar_mensaje(from_number, "entrante", f"[Entró desde Facebook/Instagram: {titulo_anuncio}]")

    texto_completo = " ".join(
        [
            msg_body_lower or "",
            referral.get("headline", "") or "",
            referral.get("body", "") or "",
        ]
    )
    texto_normalizado = _normalizar(texto_completo)

    clave = detectar_producto_por_texto(texto_normalizado) or "kit_maestro"
    enviar_ficha_producto(from_number, clave)


def _con_nota_respaldo(texto_ia):
    """Agrega, al final de una respuesta de la IA, el aviso del número de
    respaldo por si el cliente ya pagó y no recibió respuesta a tiempo."""
    nota = (
        "\n\n📌 *Importante:* si ya realizaste la compra y todavía no obtuviste "
        f"respuesta, por favor escribí directamente a este número con tu "
        f"comprobante: *{NUMERO_RESPALDO}*"
    )
    return f"{texto_ia}{nota}"


def manejar_texto(from_number, msg_body_lower):
    marcar_interaccion(from_number)
    msg_normalizado = _normalizar(msg_body_lower)

    # 0) ¿El mensaje menciona un producto puntual (ej: "arquitectura y
    #    construcción")? Si es así, vamos DIRECTO a la ficha de ese
    #    producto, sin pasar por la lista general NI por el modo IA.
    #    Esto tiene prioridad siempre, aunque el número haya quedado en
    #    "modo IA" por haber tocado antes 'Hablar con asesor'.
    clave_producto = detectar_producto_por_texto(msg_normalizado)
    if clave_producto:
        desactivar_modo_ia(from_number)  # ya no hace falta que la IA lo atienda
        enviar_ficha_producto(from_number, clave_producto)
        return

    # 1) Si no menciona ningún producto puntual, pero sí un saludo genérico
    #    ("hola", "informacion", etc.) -> mandamos el menú con todos los packs.
    #    También tiene prioridad sobre el modo IA.
    if any(palabra in msg_normalizado for palabra in PALABRAS_ACTIVADORAS):
        desactivar_modo_ia(from_number)
        enviar_menu_productos(from_number)
        return

    # 2) Si este número está en "modo IA" (tocó antes 'Hablar con asesor' y
    #    todavía ningún humano le respondió desde el panel), y el mensaje no
    #    coincidió con nada de lo anterior, dejamos que la IA le conteste.
    if esta_en_modo_ia(from_number):
        respuesta_ia = generar_respuesta_ia(msg_body_lower)
        enviar_mensaje_texto(from_number, _con_nota_respaldo(respuesta_ia))
        return

    # 3) No coincidió con nada conocido y no está en modo IA.
    enviar_mensaje_texto(
        from_number,
        f"No entendí tu mensaje 🤔. Escribí *{PALABRA_CLAVE_MENU}* para ver nuestros packs disponibles.",
    )


def manejar_boton(from_number, opcion_id):
    # Si tocó cualquier botón, ya no le mandamos el recordatorio automático
    # de "¿seguís pensando en comprar?" — está interactuando activamente.
    marcar_interaccion(from_number)
    cancelar_recordatorio(from_number)

    # Los ids vienen con el formato "accion:clave_producto" (ej: "ver_resena:kit_maestro").
    # "hablar_vendedor" no tiene clave porque no depende de un producto puntual.
    accion, _, clave = opcion_id.partition(":")

    if accion == "ver_pack" and clave in PRODUCTOS:
        enviar_ficha_producto(from_number, clave)

    elif accion == "ver_resena" and clave in PRODUCTOS:
        enviar_mensaje_texto(from_number, _texto_detalle_manuales(clave))
        enviar_botones_pack(from_number, clave, incluir_ver=False)

    elif accion == "comprar_pack" and clave in PRODUCTOS:
        producto = PRODUCTOS[clave]
        enviar_mensaje_texto(
            from_number,
            "🎉 ¡Excelente decisión! Podés abonar por cualquiera de estos medios:\n\n"
            f"1️⃣ *Pago Online (Tarjeta / Rapipago / Dinero en cuenta):*\n"
            f"🔗 {producto['link_pago']}\n\n"
            "2️⃣ *Transferencia Bancaria o Lemon 🍋:*\n"
            f"👉 *Alias:* `{DATOS_TRANSFERENCIA['alias']}`\n"
            f"👉 *CVU:* `{DATOS_TRANSFERENCIA['cvu']}`\n"
            f"👉 *Lemontag:* `{DATOS_TRANSFERENCIA['lemontag']}`\n"
            f"👤 *Titular:* {DATOS_TRANSFERENCIA['titular']}\n\n"
            "📩 *Importante:* Una vez realizado el pago, envianos el comprobante por este medio "
            f"y te enviamos los {len(producto['manuales'])} manuales al instante.",
        )
        # Botón para que el cliente avise que ya pagó (le recordamos mandar el comprobante).
        payload_ya_pague = {
            "messaging_product": "whatsapp",
            "to": from_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": "Cuando termines de pagar, tocá el botón 👇"},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": f"ya_pague:{clave}", "title": "✅ Ya pagué"}},
                    ]
                },
            },
        }
        _enviar_interactivo(from_number, payload_ya_pague, "Cuando termines de pagar, tocá el botón 👇")

    elif accion == "ya_pague" and clave in PRODUCTOS:
        enviar_mensaje_texto(
            from_number,
            "📎 ¡Genial! Para confirmar tu compra, enviame ahora mismo la *foto o PDF* del "
            "comprobante de pago acá mismo en el chat. En cuanto lo recibamos, te mandamos "
            "los manuales completos. 🙌",
        )

    elif accion == "hablar_vendedor":
        activar_modo_ia(from_number)
        respuesta_ia = generar_respuesta_ia(
            "El cliente tocó el botón 'Hablar con asesor' porque tiene una duda. "
            "Saludalo, decile que en breve un asesor humano lo va a atender, y "
            "preguntale en qué le podés ayudar mientras tanto."
        )
        enviar_mensaje_texto(from_number, _con_nota_respaldo(respuesta_ia))
    else:
        enviar_menu_productos(from_number)


def enviar_menu_productos(to):
    """Menú principal: una fila por PACK (bloque), no por manual individual.
    Si agregás un producto nuevo a PRODUCTOS, aparece acá solo."""
    filas = [
        {
            "id": f"ver_pack:{clave}",
            "title": producto["titulo"][:24],
            "description": f"{producto['descripcion_corta']} · {producto['precio']}"[:72],
        }
        for clave, producto in PRODUCTOS.items()
    ]

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": "Nuestros packs"},
            "body": {"text": MENSAJE_BIENVENIDA_MENU},
            "footer": {"text": "Tocá el botón para ver las opciones"},
            "action": {
                "button": "Ver packs",
                "sections": [{"title": "Packs disponibles", "rows": filas}],
            },
        },
    }
    _enviar_interactivo(to, payload, "[Menú de packs enviado]")


def enviar_ficha_producto(to, clave):
    """Se muestra cuando el usuario elige un pack de la lista principal,
    o cuando se detecta el producto directamente por texto/anuncio.
    El texto descriptivo SIEMPRE se manda (con los botones), y si el
    producto tiene una imagen de portada configurada, se manda ADEMÁS
    esa imagen por separado. Así, si el link de la imagen falla (algo
    que puede pasar con links de Google Drive), el cliente igual recibe
    toda la información del producto."""
    producto = PRODUCTOS[clave]
    texto = (
        f"¡Hola! 👋 Gracias por tu interés en nuestro *{producto['titulo']}* 🏗️\n\n"
        f"Son {producto['descripcion_corta']}, pensados para que tengas todo lo que "
        "necesitás en un solo lugar: desde los primeros planos hasta instalaciones "
        "eléctricas y sanitarias. 📐📚\n\n"
        f"💰 *Precio promocional:* {producto['precio']}\n\n"
        "¿Cómo te gustaría seguir? 👇"
    )

    imagen_url = producto.get("imagen")
    if imagen_url:
        enviar_imagen(to, imagen_url)  # imagen sin caption, es solo un extra visual

    enviar_botones_pack(to, clave, texto=texto, incluir_ver=True)

    # Si en 3 minutos no toca ningún botón, le mandamos un recordatorio.
    programar_recordatorio_compra(to, clave)


def enviar_imagen(to, imagen_url, caption=""):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {"link": imagen_url, "caption": caption},
    }
    _post_a_meta(url, headers, payload)
    guardar_mensaje(to, "saliente", f"[Imagen enviada] {caption}")


def enviar_botones_pack(to, clave, texto="¿Cómo querés avanzar?", incluir_ver=False):
    botones = []
    if incluir_ver:
        botones.append({"type": "reply", "reply": {"id": f"ver_resena:{clave}", "title": "📚 Ver qué incluye"}})
    botones.append({"type": "reply", "reply": {"id": f"comprar_pack:{clave}", "title": "💳 Comprar el Kit"}})
    botones.append({"type": "reply", "reply": {"id": "hablar_vendedor", "title": "💬 Hablar con asesor"}})

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": texto},
            "action": {"buttons": botones},
        },
    }
    _enviar_interactivo(to, payload, texto)


def _texto_detalle_manuales(clave):
    producto = PRODUCTOS[clave]
    lineas = [f"📖 *Contenido del {producto['titulo']}*:\n"]
    for i, manual in enumerate(producto["manuales"], start=1):
        lineas.append(f"{i}️⃣ *{manual['titulo']}* ({manual['autor']})\n👉 *Ver adelanto:* {manual['link']}\n")
    lineas.append(f"💰 *Precio promocional:* {producto['precio']}")
    return "\n".join(lineas)


def _enviar_interactivo(to, payload, texto_para_guardar):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    _post_a_meta(url, headers, payload)
    guardar_mensaje(to, "saliente", texto_para_guardar)


def enviar_manuales_completos(to, clave="kit_maestro"):
    # TODO: cuando tengas más de un pack, guardá la "clave" del producto comprado
    # junto con el comprobante en la base, para saber cuál aprobar acá (hoy siempre
    # asume "kit_maestro" porque es el único que existe).
    producto = PRODUCTOS[clave]
    lineas = [f"✅ *¡Pago confirmado! Acá tenés tus {len(producto['manuales'])} manuales completos:*\n"]
    for i, manual in enumerate(producto["manuales"], start=1):
        lineas.append(f"{i}️⃣ *{manual['titulo']}* ({manual['autor']})\n👉 {manual['link']}\n")
    lineas.append("¡Gracias por tu compra! 🙌")
    enviar_mensaje_texto(to, "\n".join(lineas))


def obtener_media_de_meta(media_id):
    """Descarga una imagen/documento recibido por WhatsApp usando el WHATSAPP_TOKEN."""
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    info = requests.get(f"https://graph.facebook.com/v21.0/{media_id}", headers=headers, timeout=15)
    info.raise_for_status()
    url = info.json()["url"]
    archivo = requests.get(url, headers=headers, timeout=15)
    archivo.raise_for_status()
    return archivo.content, info.json().get("mime_type", "application/octet-stream")


# =====================================================================
#  IA de Respaldo (Gemini) — Interactions API
#  (Ya no se usa en el flujo de mensajes de texto; queda disponible por si
#  en el futuro querés engancharla, por ejemplo, en "hablar_vendedor".)
# =====================================================================


def generar_respuesta_ia(texto_usuario):
    """Intenta responder con Gemini (varios modelos) y, si todo falla, con Groq (gratis)."""
    if GEMINI_API_KEY:
        respuesta = preguntar_a_gemini(texto_usuario)
        if respuesta is not None:
            return respuesta

    if GROQ_API_KEY:
        respuesta = preguntar_a_groq(texto_usuario)
        if respuesta is not None:
            return respuesta

    return "Un encargado te va a responder a la brevedad para ayudarte con tu consulta."


def preguntar_a_groq(texto_usuario):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}",
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": PROMPT_SISTEMA_IA},
            {"role": "user", "content": texto_usuario},
        ],
    }
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=20,
        )
        if resp.status_code >= 400:
            print("Groq devolvió error:", resp.text)
            return None
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print("Error al consultar Groq:", e)
        return None


def preguntar_a_gemini(texto_usuario):
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
    }
    texto_prompt = f"{PROMPT_SISTEMA_IA} Mensaje del cliente: {texto_usuario}"

    # Probamos el modelo principal y, si está saturado, modelos de respaldo.
    modelos_a_probar = [GEMINI_MODEL, "gemini-3.5-flash", "gemini-3.5-flash-lite"]
    # Evitamos duplicados manteniendo el orden
    modelos_a_probar = list(dict.fromkeys(modelos_a_probar))

    for modelo in modelos_a_probar:
        payload = {"model": modelo, "store": False, "input": texto_prompt}
        for intento in range(2):  # hasta 2 intentos por modelo
            try:
                resp = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=20)
                if resp.status_code >= 400:
                    print(f"Gemini ({modelo}, intento {intento+1}) devolvió error:", resp.text)
                    cuerpo = resp.text.lower()
                    if "high demand" in cuerpo or "unavailable" in cuerpo or resp.status_code in (429, 503):
                        continue  # reintenta o pasa al siguiente modelo
                    break  # error distinto (ej. modelo no existe): probamos el siguiente modelo directamente

                data = resp.json()
                for step in data.get("steps", []):
                    if step.get("type") == "model_output":
                        for bloque in step.get("content", []):
                            if bloque.get("type") == "text":
                                return bloque["text"]
                break  # respondió 200 pero sin texto útil: probamos el siguiente modelo
            except Exception as e:
                print(f"Error al consultar Gemini ({modelo}, intento {intento+1}):", e)

    return None  # Gemini falló del todo; generar_respuesta_ia pasará a Groq si está disponible


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
  <title>Ingresar — Panel {{ nombre_negocio }}</title>
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
    <h1>🔒 Panel {{ nombre_negocio }}</h1>
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
  <title>Panel {{ nombre_negocio }}</title>
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
    .comprobante { background:#fff8e1; border:1px solid #ffd54f; border-radius:10px; padding:12px;
                   margin:10px 14px; font-size:14px; }
    .comprobante img { max-width:100%; border-radius:8px; margin:8px 0; display:block; }
    .comprobante a.ver { color:#1f6feb; font-size:13px; }
    .comprobante form { margin-top:8px; }
    .btn-aprobar { background:#2e7d32; color:white; border:none; padding:8px 14px; border-radius:8px;
                   cursor:pointer; font-size:14px; }
    .badge { background:#ffd54f; color:#7a5b00; font-size:11px; padding:2px 6px; border-radius:6px;
             margin-left:6px; }
  </style>
</head>
<body>
  <div class="lista">
    <a href="/panel/logout" class="salir">Salir</a>
    {% for numero, datos in conversaciones.items() %}
      <a href="/panel?numero={{ numero }}" class="{{ 'activo' if numero == numero_activo else '' }}">
        <span class="avatar">{{ datos.inicial }}</span>{{ datos.nombre }}
        {% if numero in comprobantes_pendientes %}<span class="badge">📎 pendiente</span>{% endif %}
      </a>
    {% else %}
      <p style="padding:14px;">Sin mensajes todavía.</p>
    {% endfor %}
  </div>
  <div class="chat">
    {% if numero_activo and conversaciones.get(numero_activo) %}
      <div class="header">📱 {{ conversaciones[numero_activo].nombre }} ({{ numero_activo }})</div>
      {% if numero_activo in comprobantes_pendientes %}
        {% set comp = comprobantes_pendientes[numero_activo] %}
        <div class="comprobante">
          📎 <strong>Comprobante pendiente de aprobación</strong> ({{ comp.fecha }})
          {% if comp.mime_type.startswith('image') %}
            <img src="/panel/media/{{ comp.id }}" alt="Comprobante">
          {% else %}
            <br><a class="ver" href="/panel/media/{{ comp.id }}" target="_blank">📄 Ver archivo adjunto</a>
          {% endif %}
          <form method="POST" action="/panel/aprobar">
            <input type="hidden" name="numero" value="{{ numero_activo }}">
            <input type="hidden" name="comprobante_id" value="{{ comp.id }}">
            <button type="submit" class="btn-aprobar">✅ Aprobar y enviar manuales</button>
          </form>
        </div>
      {% endif %}
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
    return render_template_string(LOGIN_HTML, error=error, nombre_negocio=NOMBRE_NEGOCIO)


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

    comprobantes_pendientes = obtener_comprobantes_pendientes_por_numero()

    return render_template_string(
        PANEL_HTML,
        conversaciones=conversaciones,
        numero_activo=numero_activo,
        comprobantes_pendientes=comprobantes_pendientes,
        nombre_negocio=NOMBRE_NEGOCIO,
    )


@app.route("/panel/media/<int:comprobante_id>")
def panel_media(comprobante_id):
    if not logueado():
        return redirect("/panel/login")
    conn = sqlite3.connect(DB_PATH)
    fila = conn.execute(
        "SELECT media_id, mime_type FROM comprobantes WHERE id = ?", (comprobante_id,)
    ).fetchone()
    conn.close()
    if not fila:
        return "No encontrado", 404
    media_id, mime_type = fila
    try:
        contenido, mime_type_real = obtener_media_de_meta(media_id)
        return app.response_class(contenido, mimetype=mime_type_real or mime_type)
    except Exception as e:
        print("Error al descargar comprobante:", e)
        return "No se pudo cargar el archivo (puede haber expirado)", 500


@app.route("/panel/aprobar", methods=["POST"])
def panel_aprobar():
    if not logueado():
        return redirect("/panel/login")
    numero = request.form.get("numero")
    comprobante_id = request.form.get("comprobante_id")
    if numero and comprobante_id:
        marcar_comprobante_aprobado(comprobante_id)
        desactivar_modo_ia(numero)  # ya lo atendió un humano al aprobar el pago
        cancelar_recordatorio(numero)
        enviar_manuales_completos(numero)
    return redirect(f"/panel?numero={numero}")


@app.route("/panel/responder", methods=["POST"])
def panel_responder():
    if not logueado():
        return redirect("/panel/login")
    numero = request.form.get("numero")
    texto = request.form.get("texto", "").strip()
    if numero and texto:
        desactivar_modo_ia(numero)  # ya lo está atendiendo un humano
        cancelar_recordatorio(numero)
        enviar_mensaje_texto(numero, texto)
    return redirect(f"/panel?numero={numero}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
