import os
import hmac
import hashlib
import re
import sqlite3
import threading
import time
import unicodedata
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, redirect, session, send_from_directory

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
    FRASES_VER_QUE_INCLUYE,
    FRASES_COMPRAR,
    FRASES_ASESOR,
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

# --- Mercado Pago (pago automático, opcional) ---
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN")
# BASE_URL: la URL pública de tu bot en Render, ej: https://bot-whatsapp-ojza.onrender.com (sin / al final)
BASE_URL = os.getenv("BASE_URL")
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "cambiar_esta_clave")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "cambiar_esta_clave_tambien")

# Dónde vive la base de datos. Por defecto se guarda en la carpeta de la
# app (que en Render se borra en cada redeploy/reinicio, en el plan
# gratuito). Si configurás la variable de entorno DB_PATH apuntando a un
# disco persistente de Render (por ejemplo "/var/data/mensajes.db"), los
# datos van a sobrevivir a los redeploys y reinicios.
DB_PATH = os.getenv("DB_PATH", "mensajes.db")

# Si la ruta incluye una carpeta que todavía no existe (por ejemplo la
# primera vez que se monta el disco), la creamos para que sqlite no falle.
if os.path.dirname(DB_PATH):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ---------------------------------------------------------------------
# Recordatorio automático de compra: si le mandamos la ficha de un producto
# a alguien y no toca NINGÚN botón, le mandamos hasta DOS recordatorios:
# uno a los 3 minutos, y otro (más urgente) a la hora si todavía no
# interactuó. Ambos se cancelan apenas la persona toca cualquier botón,
# manda un comprobante, o si un humano le responde/aprueba el pago desde
# el panel.
#
# NOTA IMPORTANTE: esto usa threading.Timer en memoria. Funciona bien
# mientras la app corra en UN SOLO proceso/worker (lo normal en Render para
# un bot chico). Si en el futuro escalás a varios workers, esto habría que
# migrarlo a algo persistente (una tabla en la base + un cron/scheduler).
# =====================================================================
SEGUNDOS_RECORDATORIO_CORTO = float(os.getenv("SEGUNDOS_RECORDATORIO_CORTO", "180"))  # 3 minutos
SEGUNDOS_RECORDATORIO_LARGO = float(os.getenv("SEGUNDOS_RECORDATORIO_LARGO", "3600"))  # 1 hora
RECORDATORIOS_PENDIENTES = {}  # numero -> threading.Timer (el de 3 minutos)
RECORDATORIOS_PENDIENTES_LARGO = {}  # numero -> threading.Timer (el de 1 hora)
ULTIMA_INTERACCION = {}  # numero -> timestamp (time.time()) de la última acción del usuario
PRODUCTO_ACTUAL = {}  # numero -> clave del último producto que le mostramos (para "alias", "que incluye", etc.)


def marcar_interaccion(numero):
    """Registra que este número acaba de interactuar (mandó un mensaje o tocó
    un botón). Se usa para evitar que un recordatorio se dispare justo en el
    instante en que la persona ya está actuando (carrera de tiempos entre
    'cancelar el aviso' y 'el aviso ya se estaba mandando')."""
    ULTIMA_INTERACCION[numero] = time.time()


def cancelar_recordatorio(numero):
    """Cancela CUALQUIER recordatorio pendiente para este número (tanto el
    de 3 minutos como el de 1 hora, si estuvieran programados)."""
    timer_corto = RECORDATORIOS_PENDIENTES.pop(numero, None)
    if timer_corto:
        timer_corto.cancel()
    timer_largo = RECORDATORIOS_PENDIENTES_LARGO.pop(numero, None)
    if timer_largo:
        timer_largo.cancel()


def _armar_recordatorio(numero, clave, texto_mensaje):
    """Función interna que arma el 'chequeo de seguridad' (para no mandar el
    aviso si la persona interactuó hace muy poquito) y manda el mensaje +
    los botones. La usan tanto el recordatorio corto como el largo."""
    ultima = ULTIMA_INTERACCION.get(numero, 0)
    if time.time() - ultima < 10:
        return  # la persona ya está activa en la conversación, no la molestamos
    producto = PRODUCTOS.get(clave)
    if not producto:
        return
    enviar_mensaje_texto(numero, texto_mensaje)
    enviar_botones_pack(numero, clave, texto="¿Cómo querés avanzar?", incluir_ver=True)


def programar_recordatorio_compra(numero, clave):
    """Programa los dos recordatorios (3 minutos y 1 hora) para este número.
    Si ya había recordatorios pendientes, los reemplaza (reinicia el conteo)."""
    cancelar_recordatorio(numero)

    def _recordatorio_corto():
        RECORDATORIOS_PENDIENTES.pop(numero, None)
        producto = PRODUCTOS.get(clave)
        if not producto:
            return
        cantidad_m = len(producto["manuales"])
        completo_s = "completo" if cantidad_m == 1 else "completos"
        listo_s = "listo" if cantidad_m == 1 else "listos"
        _armar_recordatorio(
            numero, clave,
            f"👋 ¿Seguís pensando en el *{producto['titulo']}*?\n\n"
            f"Te lo dejamos por solo *{producto['precio']}*: "
            f"{_texto_cantidad_manuales(producto)} {completo_s}, {listo_s} para descargar. 📚\n\n"
            "Cuando quieras avanzar, tocá el botón de abajo 👇",
        )

    def _recordatorio_largo():
        RECORDATORIOS_PENDIENTES_LARGO.pop(numero, None)

        # Mismo chequeo de seguridad que _armar_recordatorio: si la persona
        # interactuó hace muy poquito, no la molestamos.
        ultima = ULTIMA_INTERACCION.get(numero, 0)
        if time.time() - ultima < 10:
            return

        producto = PRODUCTOS.get(clave)
        if not producto:
            return

        # A la hora, sin haber tocado nada, le mandamos la secuencia completa
        # con la oferta especial (imagen + $5.500 + libros + datos de pago).
        _enviar_flujo_compra(numero, clave)

    timer_corto = threading.Timer(SEGUNDOS_RECORDATORIO_CORTO, _recordatorio_corto)
    timer_corto.daemon = True
    RECORDATORIOS_PENDIENTES[numero] = timer_corto
    timer_corto.start()

    timer_largo = threading.Timer(SEGUNDOS_RECORDATORIO_LARGO, _recordatorio_largo)
    timer_largo.daemon = True
    RECORDATORIOS_PENDIENTES_LARGO[numero] = timer_largo
    timer_largo.start()

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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pagos_mp_procesados (
            payment_id TEXT PRIMARY KEY,
            fecha TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def pago_mp_ya_procesado(payment_id):
    """Evita procesar el mismo pago de Mercado Pago dos veces (por si
    llega el mismo aviso repetido)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO pagos_mp_procesados (payment_id, fecha) VALUES (?, ?)",
            (str(payment_id), datetime.utcnow().strftime("%d/%m %H:%M:%S")),
        )
        conn.commit()
        return False  # se pudo insertar => es la primera vez que lo vemos
    except sqlite3.IntegrityError:
        return True  # ya existía => es un duplicado
    finally:
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


def obtener_nombre_contacto(numero):
    """Devuelve el nombre guardado del contacto, o el número si no hay
    nombre disponible (por ejemplo, si todavía no mandó su perfil)."""
    conn = sqlite3.connect(DB_PATH)
    fila = conn.execute("SELECT nombre FROM contactos WHERE numero = ?", (numero,)).fetchone()
    conn.close()
    if fila and fila[0]:
        return fila[0]
    return numero


def _escapar_html(texto):
    """Escapa los caracteres especiales de HTML para que Telegram no rompa
    el formato si el mensaje del cliente trae &, < o >."""
    return (
        str(texto)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ---------------------------------------------------------------------
# Respuestas rápidas organizadas en CATEGORÍAS: al tocar una categoría en
# Telegram, se despliegan sus opciones específicas (sub-botones). Al
# tocar una opción, se le manda ese texto al cliente por WhatsApp y se
# vuelve al menú de categorías. El botón de link "Hablar personalmente"
# siempre está arriba de todo, en cualquier nivel del menú.
#
# Para agregar/cambiar categorías u opciones, se edita este diccionario.
# Las claves (ej: "pago", "pago1") son internas, no se ven.
# ---------------------------------------------------------------------
CATEGORIAS_RESPUESTAS = {
    "pago": {
        "titulo": "💰 Pago",
        "opciones": {
            "pago1": ("✅ Ya enviamos", "¡Listo! Ya te enviamos los manuales, cualquier duda escribinos."),
            "pago2": ("📸 Reenviar comprobante", "¿Podés reenviar el comprobante? No lo pudimos ver bien."),
            "pago3": ("⏳ Dame minutos", "Dame unos minutos que ya te atiendo."),
        },
    },
    "producto": {
        "titulo": "📦 Producto",
        "opciones": {
            "prod1": ("📚 Qué incluye", "Te paso el detalle de qué incluye en un toque, dame un segundo."),
            "prod2": ("💵 Precio", "El precio depende del pack — contame cuál te interesa y te confirmo."),
            "prod3": ("🕐 Cuándo llega", "Apenas confirmemos tu pago, te mando el archivo al instante por acá mismo."),
        },
    },
    "otro": {
        "titulo": "💬 Otro",
        "opciones": {
            "otro1": ("🙏 Gracias compra", "¡Gracias por tu compra! Cualquier consulta, escribí."),
            "otro2": ("💬 Otra cosa", "Gracias por tu mensaje, ya te respondo."),
        },
    },
    "guiar": {
        "titulo": "🔄 Guiar",
        "opciones": {
            "guiar1": ("📝 Escribí DROPLY", "Si querés ver todo de nuevo, escribí *DROPLY* y te muestro el pack completo. 😊"),
            "guiar2": ("❓ Qué buscás", "¿Qué tipo de información te gustaría? Contame y te ayudo directo. 😊"),
            "guiar3": ("📦 Ver el pack", "Escribí *arquitectura y construcción* y te mando toda la info del pack de nuevo."),
        },
    },
}


def _teclado_categorias(numero):
    """Menú principal: el link para hablar personalmente + una fila por
    categoría."""
    filas = [
        [{"text": "📱 Hablar personalmente", "url": f"https://wa.me/{numero}"}],
    ]
    for cat_id, categoria in CATEGORIAS_RESPUESTAS.items():
        filas.append([{"text": categoria["titulo"], "callback_data": f"cat:{cat_id}:{numero}"}])
    return {"inline_keyboard": filas}


def _teclado_subrespuestas(cat_id, numero):
    """Sub-menú de una categoría puntual, con botón para volver atrás."""
    filas = [
        [{"text": "📱 Hablar personalmente", "url": f"https://wa.me/{numero}"}],
    ]
    categoria = CATEGORIAS_RESPUESTAS.get(cat_id)
    if categoria:
        for opt_id, (titulo_boton, _) in categoria["opciones"].items():
            filas.append([{"text": titulo_boton, "callback_data": f"resp:{cat_id}:{opt_id}:{numero}"}])
    filas.append([{"text": "⬅️ Volver", "callback_data": f"back:{numero}"}])
    return {"inline_keyboard": filas}


def _editar_teclado_telegram(chat_id, message_id, teclado):
    """Cambia los botones de un mensaje de Telegram ya enviado (para
    navegar entre el menú de categorías y sus sub-opciones)."""
    if not TELEGRAM_BOT_TOKEN or not chat_id or not message_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageReplyMarkup",
            json={"chat_id": chat_id, "message_id": message_id, "reply_markup": teclado},
            timeout=10,
        )
    except Exception as e:
        print("Error editando teclado de Telegram:", e)


def enviar_notificacion_telegram(numero, resumen_texto):
    """Le avisa al dueño del negocio por Telegram que llegó un mensaje nuevo,
    con un formato prolijo (nombre, número, hora, y el mensaje entre
    comillas), más los botones de respuesta rápida. Si en vez de tocar un
    botón responde a ESE mensaje de Telegram (con la función 'responder'),
    el bot también sabe a qué número de WhatsApp reenviarle esa respuesta
    (ver /telegram_webhook)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return  # Telegram no está configurado, no hacemos nada
    try:
        nombre = obtener_nombre_contacto(numero)
        hora = datetime.utcnow().strftime("%H:%M")

        # Si el nombre y el número son distintos, mostramos los dos; si no
        # hay nombre guardado, mostramos solo el número.
        if nombre != numero:
            encabezado = f"👤 <b>{_escapar_html(nombre)}</b>  ·  <code>{_escapar_html(numero)}</code>"
        else:
            encabezado = f"👤 <b>{_escapar_html(numero)}</b>"

        texto_formateado = (
            f"📲 <b>WhatsApp — {_escapar_html(NOMBRE_NEGOCIO)}</b>\n"
            f"{encabezado}\n"
            f"🕒 {hora}\n"
            f"\n"
            f"<i>“{_escapar_html(resumen_texto)}”</i>\n"
            f"\n"
            f"↩️ <i>Respondé a este mensaje para contestarle por WhatsApp, "
            f"o tocá un botón de respuesta rápida.</i>"
        )

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": texto_formateado,
            "parse_mode": "HTML",
            "reply_markup": _teclado_categorias(numero),
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


def enviar_notificacion_telegram_comprobante(numero, comprobante_id, clave="kit_maestro"):
    """Notificación especial cuando llega un comprobante de pago: en vez
    del menú de categorías normal, incluye un botón para aprobar el pago
    y mandar la carpeta de manuales al instante, sin pasar por el panel."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        nombre = obtener_nombre_contacto(numero)
        hora = datetime.utcnow().strftime("%H:%M")
        encabezado = (
            f"👤 <b>{_escapar_html(nombre)}</b>  ·  <code>{_escapar_html(numero)}</code>"
            if nombre != numero
            else f"👤 <b>{_escapar_html(numero)}</b>"
        )
        texto_formateado = (
            f"📎 <b>Comprobante de pago — {_escapar_html(NOMBRE_NEGOCIO)}</b>\n"
            f"{encabezado}\n"
            f"🕒 {hora}\n\n"
            "Mandó un comprobante. Revisalo en el panel, o tocá el botón para "
            "aprobarlo y mandarle la carpeta de manuales al instante."
        )
        teclado = {
            "inline_keyboard": [
                [{"text": "📱 Hablar personalmente", "url": f"https://wa.me/{numero}"}],
                [{"text": "✅ Aprobar y enviar carpeta", "callback_data": f"aprobar:{comprobante_id}:{clave}:{numero}"}],
            ]
        }
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": texto_formateado,
                "parse_mode": "HTML",
                "reply_markup": teclado,
            },
            timeout=10,
        )
        if resp.status_code >= 400:
            print("Error notificando comprobante a Telegram:", resp.text)
            return
        data = resp.json()
        telegram_message_id = data.get("result", {}).get("message_id")
        if telegram_message_id:
            registrar_mapeo_telegram(telegram_message_id, numero)
    except Exception as e:
        print("Error notificando comprobante a Telegram:", e)


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


# =====================================================================
#  Backup automático de la base de datos por Telegram
#  ----------------------------------------------------------------
#  El plan gratuito de Render puede borrar el archivo de la base de datos
#  en cada redeploy/reinicio. Como respaldo (gratis), le mandamos el
#  archivo completo por Telegram cada cierta cantidad de horas, así
#  siempre queda una copia reciente a salvo en tu chat de Telegram.
# =====================================================================
BACKUP_INTERVALO_HORAS = float(os.getenv("BACKUP_INTERVALO_HORAS", "24"))


def enviar_backup_telegram():
    """Manda el archivo actual de la base de datos (mensajes.db) a Telegram
    como documento adjunto."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    if not os.path.exists(DB_PATH):
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
        fecha_legible = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")
        with open(DB_PATH, "rb") as archivo:
            resp = requests.post(
                url,
                data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "caption": f"🗄️ Backup automático de la base de datos — {fecha_legible}",
                },
                files={"document": (os.path.basename(DB_PATH), archivo)},
                timeout=30,
            )
        if resp.status_code >= 400:
            print("Error mandando backup a Telegram:", resp.text)
    except Exception as e:
        print("Error mandando backup a Telegram:", e)


def iniciar_backups_automaticos():
    """Arranca un hilo en segundo plano que manda el backup cada
    BACKUP_INTERVALO_HORAS horas, para siempre, mientras la app esté viva."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    def _loop():
        while True:
            time.sleep(BACKUP_INTERVALO_HORAS * 3600)
            enviar_backup_telegram()

    hilo = threading.Thread(target=_loop, daemon=True)
    hilo.start()


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
    cursor = conn.execute(
        "INSERT INTO comprobantes (numero, media_id, mime_type, estado, fecha) VALUES (?, ?, ?, 'pendiente', ?)",
        (numero, media_id, mime_type, datetime.utcnow().strftime("%d/%m %H:%M:%S")),
    )
    conn.commit()
    comprobante_id = cursor.lastrowid
    conn.close()
    return comprobante_id


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
iniciar_backups_automaticos()


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
                comprobante_id = guardar_comprobante(from_number, media_id, mime_type)
                cancelar_recordatorio(from_number)
                guardar_mensaje(
                    from_number, "entrante", "📎 Comprobante recibido (pendiente de aprobación)"
                )
                # Usamos el producto que realmente le mostramos a este
                # cliente (no siempre "kit_maestro"), para que el botón de
                # aprobar en Telegram mande el archivo correcto.
                clave_producto_actual = PRODUCTO_ACTUAL.get(from_number, next(iter(PRODUCTOS)))
                enviar_notificacion_telegram_comprobante(from_number, comprobante_id, clave_producto_actual)
                producto_actual = PRODUCTOS.get(clave_producto_actual, {})
                texto_cantidad = _texto_cantidad_manuales(producto_actual) if producto_actual else "los manuales"
                enviar_mensaje_texto(
                    from_number,
                    "¡Recibimos tu comprobante! 📎 En breve lo revisamos y te enviamos "
                    f"{texto_cantidad}. Gracias por tu paciencia.",
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

        # --- Botones (llegan como "callback_query", no como un mensaje
        #     normal). Pueden ser: "cat:..." (entrar a una categoría),
        #     "back:..." (volver al menú principal), o "resp:..." (mandar
        #     la respuesta puntual elegida). ---
        callback = data.get("callback_query")
        if callback:
            callback_id = callback.get("id")
            callback_data = callback.get("data", "")
            mensaje_cb = callback.get("message", {})
            chat_id_cb = mensaje_cb.get("chat", {}).get("id")
            message_id_cb = mensaje_cb.get("message_id")

            partes = callback_data.split(":")
            accion_cb = partes[0] if partes else ""
            aviso_popup = "OK"

            if accion_cb == "cat" and len(partes) == 3:
                _, cat_id, numero = partes
                _editar_teclado_telegram(chat_id_cb, message_id_cb, _teclado_subrespuestas(cat_id, numero))
                aviso_popup = "Elegí una opción 👇"

            elif accion_cb == "back" and len(partes) == 2:
                _, numero = partes
                _editar_teclado_telegram(chat_id_cb, message_id_cb, _teclado_categorias(numero))
                aviso_popup = "Volviendo al menú"

            elif accion_cb == "resp" and len(partes) == 4:
                _, cat_id, opt_id, numero = partes
                categoria = CATEGORIAS_RESPUESTAS.get(cat_id, {})
                opcion = categoria.get("opciones", {}).get(opt_id)
                if opcion:
                    _, texto_a_enviar = opcion
                    desactivar_modo_ia(numero)
                    cancelar_recordatorio(numero)
                    enviar_mensaje_texto(numero, texto_a_enviar)
                    aviso_popup = "Enviado ✅"
                    # Volvemos al menú principal después de responder.
                    _editar_teclado_telegram(chat_id_cb, message_id_cb, _teclado_categorias(numero))
                else:
                    aviso_popup = "No se pudo enviar"

            elif accion_cb == "aprobar" and len(partes) == 4:
                _, comprobante_id, clave, numero = partes
                marcar_comprobante_aprobado(comprobante_id)
                desactivar_modo_ia(numero)
                cancelar_recordatorio(numero)
                enviar_manuales_completos(numero, clave)
                aviso_popup = "✅ Aprobado, carpeta enviada"
                # Reemplazamos el botón de aprobar por un aviso de que ya se procesó.
                _editar_teclado_telegram(
                    chat_id_cb,
                    message_id_cb,
                    {
                        "inline_keyboard": [
                            [{"text": "📱 Hablar personalmente", "url": f"https://wa.me/{numero}"}],
                            [{"text": "✅ Ya aprobado", "callback_data": f"back:{numero}"}],
                        ]
                    },
                )

            # Hay que "contestarle" a Telegram el callback, si no el botón
            # se queda cargando (girando) en la app del usuario.
            if TELEGRAM_BOT_TOKEN and callback_id:
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
                    json={"callback_query_id": callback_id, "text": aviso_popup},
                    timeout=10,
                )
            return jsonify({"status": "callback_procesado"}), 200

        mensaje_telegram = data.get("message") or data.get("edited_message")
        if not mensaje_telegram:
            return jsonify({"status": "ignorado"}), 200

        texto_admin = (mensaje_telegram.get("text") or "").strip()
        respondido_a = mensaje_telegram.get("reply_to_message")

        # Comando manual: escribiendo /backup (sin responder a nada en
        # particular), mandamos el archivo de la base de datos al toque.
        if texto_admin.lower() == "/backup":
            enviar_backup_telegram()
            return jsonify({"status": "backup_enviado"}), 200

        if not texto_admin or not respondido_a:
            return jsonify({"status": "ignorado"}), 200

        telegram_message_id = respondido_a.get("message_id")
        numero = obtener_numero_por_mensaje_telegram(telegram_message_id)

        if not numero:
            # Respaldo: si la base de datos perdió esta referencia (por
            # ejemplo, si el servidor se reinició entre que llegó la
            # notificación y que la respondiste), tratamos de sacar el
            # número directo del texto del mensaje original al que
            # respondiste (ahí siempre aparece el número de teléfono).
            texto_original = respondido_a.get("text", "")
            match = re.search(r"\d{10,15}", texto_original)
            if match:
                numero = match.group(0)

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


@app.route("/webhook/mercadopago", methods=["POST", "GET"])
def mercadopago_webhook():
    """Mercado Pago avisa acá cada vez que hay novedades de un pago. Si el
    pago está aprobado y todavía no lo procesamos, le mandamos los
    manuales al cliente automáticamente, sin que nadie tenga que aprobar
    nada a mano."""
    if not MP_ACCESS_TOKEN:
        return jsonify({"status": "mercadopago_no_configurado"}), 200

    # Mercado Pago puede mandar el aviso como JSON en el body, o como query
    # params, según cómo esté configurada la cuenta. Contemplamos las dos.
    data = request.get_json(silent=True) or {}
    payment_id = (data.get("data") or {}).get("id") or request.args.get("data.id") or request.args.get("id")

    if not payment_id:
        return jsonify({"status": "ignorado"}), 200

    try:
        resp = requests.get(
            f"https://api.mercadopago.com/v1/payments/{payment_id}",
            headers={"Authorization": f"Bearer {MP_ACCESS_TOKEN}"},
            timeout=15,
        )
        pago = resp.json()
    except Exception as e:
        print("Error consultando el pago en Mercado Pago:", repr(e))
        return jsonify({"status": "error"}), 200

    if pago.get("status") == "approved" and not pago_mp_ya_procesado(payment_id):
        external_reference = pago.get("external_reference", "")
        if "|" in external_reference:
            numero, clave = external_reference.split("|", 1)
            confirmar_pago_automatico_mp(numero, clave)

    return jsonify({"status": "ok"}), 200


# =====================================================================
#  Lógica del Bot (Kit Maestro)
# =====================================================================
def _texto_cantidad_manuales(producto):
    """Devuelve 'el manual' si el pack tiene uno solo, o 'los N manuales'
    si tiene varios (para que los mensajes se lean bien en los dos casos)."""
    cantidad = len(producto.get("manuales", []))
    return "el manual" if cantidad == 1 else f"los {cantidad} manuales"


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
    #    ("hola", "informacion", etc.):
    #    - Si hay UN SOLO producto cargado, vamos directo a su ficha (sin
    #      pasar por ningún menú/lista, para no obligar a tocar nada).
    #    - Si hay VARIOS productos, ahí sí mandamos el menú para que elija.
    #    También tiene prioridad sobre el modo IA.
    if any(palabra in msg_normalizado for palabra in PALABRAS_ACTIVADORAS):
        desactivar_modo_ia(from_number)
        if len(PRODUCTOS) == 1:
            enviar_ficha_producto(from_number, next(iter(PRODUCTOS)))
        else:
            enviar_menu_productos(from_number)
        return

    # 1.5) Red de contención para gente que no toca los botones y escribe
    #      directamente lo que quiere ("quiero comprar", "que incluye",
    #      "hablar con alguien"). Si matchea alguna de estas frases, hacemos
    #      LO MISMO que si hubiera tocado el botón correspondiente, sobre el
    #      ÚLTIMO producto que le mostramos a este número (o el primero
    #      configurado, si todavía no le mostramos ninguno).
    if PRODUCTOS:
        clave_default = PRODUCTO_ACTUAL.get(from_number, next(iter(PRODUCTOS)))
        if any(frase in msg_normalizado for frase in FRASES_COMPRAR):
            manejar_boton(from_number, f"comprar_pack:{clave_default}")
            return
        if any(frase in msg_normalizado for frase in FRASES_VER_QUE_INCLUYE):
            manejar_boton(from_number, f"ver_resena:{clave_default}")
            return
        if any(frase in msg_normalizado for frase in FRASES_ASESOR):
            manejar_boton(from_number, "hablar_vendedor")
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


def _enviar_flujo_compra(numero, clave):
    """Manda toda la secuencia de compra (imagen + 3 mensajes + botón), con
    una pausa corta entre cada uno para que no se sienta tan robótico/
    instantáneo. Corre en un hilo aparte para no atrasar la respuesta del
    webhook a Meta."""
    producto = PRODUCTOS.get(clave)
    if not producto:
        return

    PAUSA_ENTRE_MENSAJES = 5  # segundos

    # La imagen del banner de oferta va PRIMERO que todo (sin caption: el
    # texto va aparte, así si la imagen falla, los mensajes igual llegan).
    imagen_oferta = producto.get("imagen_oferta")
    if imagen_oferta:
        enviar_imagen(numero, imagen_oferta)
        time.sleep(PAUSA_ENTRE_MENSAJES)

    # Mensaje 1: la oferta con la urgencia de 1 hora (precio de oferta,
    # distinto del precio "normal" que se muestra en la ficha inicial).
    precio_oferta = producto.get("precio_oferta", producto["precio"])
    cantidad_m1 = len(producto["manuales"])
    tecnico_s = "técnico" if cantidad_m1 == 1 else "técnicos"
    enviar_mensaje_texto(
        numero,
        "🔥 *¡Oferta imperdible por 1 hora!* 🔥\n\n"
        f"El *{producto['titulo']}* completo, con {_texto_cantidad_manuales(producto)} "
        f"{tecnico_s}, hoy te sale solo *{precio_oferta}*.\n\n"
        "Esta promo vence en 1 hora, así que si te interesa, aprovechala ahora. 👇",
    )
    time.sleep(PAUSA_ENTRE_MENSAJES)

    # Mensaje 2: la lista de los libros que incluye.
    lineas_libros = [f"📚 *Esto es lo que te llevás:*\n"]
    for i, manual in enumerate(producto["manuales"], start=1):
        lineas_libros.append(f"{i}️⃣ {manual['titulo']} ({manual['autor']})")
    enviar_mensaje_texto(numero, "\n".join(lineas_libros))
    time.sleep(PAUSA_ENTRE_MENSAJES)

    # Mensaje 3: los datos para transferir.
    enviar_mensaje_texto(
        numero,
        "💸 *Podés abonar por transferencia o Lemon:*\n\n"
        f"👉 *Alias:* `{DATOS_TRANSFERENCIA['alias']}`\n"
        f"👉 *CVU:* `{DATOS_TRANSFERENCIA['cvu']}`\n"
        f"👉 *Lemontag:* `{DATOS_TRANSFERENCIA['lemontag']}`\n"
        f"👤 *Titular:* {DATOS_TRANSFERENCIA['titular']}\n\n"
        "📩 Una vez realizado el pago, enviame el comprobante (foto o PDF) acá mismo "
        "en el chat y te mando los manuales al instante.",
    )
    time.sleep(PAUSA_ENTRE_MENSAJES)

    # Botón para que el cliente avise que ya pagó.
    payload_ya_pague = {
        "messaging_product": "whatsapp",
        "to": numero,
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
    _enviar_interactivo(numero, payload_ya_pague, "Cuando termines de pagar, tocá el botón 👇")


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

        # Si Mercado Pago está configurado, generamos un link de pago único
        # para este cliente. Es una opción ADEMÁS de la transferencia, no en
        # vez de ella: si paga por acá, el bot le manda los manuales solo,
        # sin que nadie tenga que aprobar nada a mano.
        link_mp = crear_preferencia_pago(from_number, clave)
        seccion_mp = ""
        cierre_mp = ""
        if link_mp:
            seccion_mp = (
                "💳 *Pago con Mercado Pago (acreditación automática):*\n"
                f"{link_mp}\n\n"
            )
            cierre_mp = " Si pagás por Mercado Pago, te los mando automático apenas se acredite. ✅"

        # Mensaje directo y simple con los datos de pago (precio normal),
        # sin imagen. La secuencia con imagen/banner queda reservada para
        # el recordatorio automático de 1 hora, si la persona no compra en
        # ese tiempo (ver programar_recordatorio_compra).
        cantidad = len(producto["manuales"])
        texto_cantidad = "el manual" if cantidad == 1 else f"los {cantidad} manuales"
        enviar_mensaje_texto(
            from_number,
            "🎉 ¡Excelente decisión! Podés abonar por "
            + ("cualquiera de estas dos opciones" if link_mp else "transferencia o Lemon")
            + ":\n\n"
            f"{seccion_mp}"
            "👉 *Transferencia o Lemon:*\n"
            f"*Alias:* `{DATOS_TRANSFERENCIA['alias']}`\n"
            f"*CVU:* `{DATOS_TRANSFERENCIA['cvu']}`\n"
            f"*Lemontag:* `{DATOS_TRANSFERENCIA['lemontag']}`\n"
            f"*Titular:* {DATOS_TRANSFERENCIA['titular']}\n\n"
            f"💰 *Total:* {producto['precio']}\n\n"
            "📩 Si pagás por transferencia, enviame el comprobante (foto o PDF) acá mismo "
            f"y te mando {texto_cantidad} al instante."
            f"{cierre_mp}\n\n"
            f"📌 Si tenés cualquier inconveniente, escribime directo a mi número "
            f"personal: *{NUMERO_RESPALDO}*",
        )
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
    En vez de un mensaje con botones, manda una secuencia de mensajes de
    texto (imagen + saludo + contenido + instrucción para comprar), con
    pausas cortas entre cada uno para que no se sienta tan robótico.
    Corre en un hilo aparte para no atrasar la respuesta del webhook."""
    threading.Thread(target=_enviar_secuencia_ficha, args=(to, clave), daemon=True).start()


def _enviar_secuencia_ficha(to, clave):
    producto = PRODUCTOS.get(clave)
    if not producto:
        return

    PRODUCTO_ACTUAL[to] = clave  # recordamos qué producto le mostramos a este número

    PAUSA = 4  # segundos entre mensaje y mensaje

    # Por defecto, cada producto manda UNA sola imagen en la ficha (prioriza
    # la de oferta si existe, si no la de portada) — así se comportaba el
    # Kit Maestro desde el principio y no lo tocamos.
    # Si un producto puntual tiene "mostrar_dos_imagenes": True en su config,
    # ahí sí mandamos las dos, una atrás de la otra.
    if producto.get("mostrar_dos_imagenes"):
        imagen_portada = producto.get("imagen")
        imagen_oferta = producto.get("imagen_oferta")

        if imagen_portada:
            enviar_imagen(to, imagen_portada)
            time.sleep(PAUSA)

        if imagen_oferta and imagen_oferta != imagen_portada:
            enviar_imagen(to, imagen_oferta)
            time.sleep(PAUSA)
    else:
        imagen_url = producto.get("imagen_oferta") or producto.get("imagen")
        if imagen_url:
            enviar_imagen(to, imagen_url)
            time.sleep(PAUSA)

    # Mensaje 1: saludo, agradeciendo el interés.
    enviar_mensaje_texto(
        to,
        f"¡Hola! 👋 Gracias por tu interés en nuestro *{producto['titulo']}* 🏗️\n\n"
        "¡Excelente elección! Te cuento todo lo que incluye.",
    )
    time.sleep(PAUSA)

    # Mensaje 2: lo que incluye (los manuales, con su link de adelanto,
    # separados con un espacio para que se distinga bien uno de otro).
    lineas = [f"📚 *Esto es lo que te llevás:*\n"]
    for i, manual in enumerate(producto["manuales"], start=1):
        lineas.append(f"{i}️⃣ *{manual['titulo']}* ({manual['autor']})")
        lineas.append(f"👉 {manual['link']}\n")
    enviar_mensaje_texto(to, "\n".join(lineas))
    time.sleep(PAUSA)

    # Mensaje 3: precio + instrucción para comprar escribiendo "ALIAS".
    enviar_mensaje_texto(
        to,
        f"💰 *Precio:* {producto['precio']}\n\n"
        "Si querés adquirir el pack, escribí *ALIAS* y te paso todos los datos "
        "para transferir. 👇",
    )

    # Si en 3 minutos / 1 hora no escribe nada más, le mandamos un recordatorio.
    programar_recordatorio_compra(to, clave)




def enviar_imagen(to, imagen_url, caption=""):
    """Manda una imagen por WhatsApp. Reintenta una vez más si el primer
    intento falla (a veces Meta tarda en descargar la imagen y da timeout,
    sobre todo justo después de que el servidor estuvo inactivo)."""
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

    exito = _post_a_meta(url, headers, payload)
    if not exito:
        print("Primer intento de mandar imagen falló, reintentando en 2 segundos...")
        time.sleep(2)
        exito = _post_a_meta(url, headers, payload)
        if not exito:
            print("Segundo intento de mandar imagen también falló, se omite la imagen.")

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
    producto = PRODUCTOS[clave]
    link_carpeta = producto.get("link_carpeta_final")
    cantidad = len(producto["manuales"])

    if link_carpeta:
        if cantidad == 1:
            descripcion_entrega = "tu archivo, listo para descargar"
        else:
            descripcion_entrega = f"tu carpeta con los {cantidad} manuales completos, listos para descargar"
        enviar_mensaje_texto(
            to,
            f"✅ *¡Pago confirmado!* Acá tenés {descripcion_entrega}:\n\n"
            f"{link_carpeta}\n\n"
            "¡Gracias por tu compra! 🙌",
        )
    else:
        # Respaldo: si no hay carpeta configurada, mandamos los links
        # individuales de cada manual (como se hacía antes).
        encabezado = "tu manual completo" if cantidad == 1 else f"tus {cantidad} manuales completos"
        lineas = [f"✅ *¡Pago confirmado! Acá tenés {encabezado}:*\n"]
        for i, manual in enumerate(producto["manuales"], start=1):
            lineas.append(f"{i}️⃣ *{manual['titulo']}* ({manual['autor']})\n👉 {manual['link']}\n")
        lineas.append("¡Gracias por tu compra! 🙌")
        enviar_mensaje_texto(to, "\n".join(lineas))


# =====================================================================
#  Mercado Pago — pago automático (opcional)
#  ----------------------------------------------------------------
#  Esto es una opción ADICIONAL a la transferencia por alias: el cliente
#  puede pagar con Mercado Pago y, apenas se acredita, el bot le manda los
#  manuales solo, sin que nadie tenga que aprobar nada a mano. Si no
#  configurás MP_ACCESS_TOKEN y BASE_URL, esta parte simplemente no se usa
#  y todo sigue funcionando con la transferencia por alias como siempre.
# =====================================================================
def crear_preferencia_pago(numero, clave):
    """Genera un link de pago único de Mercado Pago para este cliente y
    este producto. Devuelve el link, o None si algo falla."""
    if not MP_ACCESS_TOKEN or not BASE_URL:
        return None
    producto = PRODUCTOS.get(clave)
    if not producto:
        return None

    url = "https://api.mercadopago.com/checkout/preferences"
    headers = {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "items": [
            {
                "title": producto["titulo"],
                "quantity": 1,
                "unit_price": float(producto.get("precio_valor", 0)),
                "currency_id": "ARS",
            }
        ],
        # external_reference es la clave: acá "marcamos" de quién y de qué
        # producto es este pago, para reconocerlo cuando llegue la
        # confirmación en /webhook/mercadopago.
        "external_reference": f"{numero}|{clave}",
        "notification_url": f"{BASE_URL}/webhook/mercadopago",
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("init_point")
    except Exception as e:
        print("Error creando preferencia de Mercado Pago:", repr(e))
        return None


def confirmar_pago_automatico_mp(numero, clave):
    """Se llama cuando Mercado Pago confirma que un pago fue aprobado. Le
    manda los manuales directo, sin necesitar aprobación manual, y avisa
    por Telegram para que quede registrado."""
    desactivar_modo_ia(numero)
    cancelar_recordatorio(numero)
    enviar_manuales_completos(numero, clave)
    enviar_notificacion_telegram(
        numero,
        "💳 Pago automático confirmado por Mercado Pago. Los manuales ya se le mandaron solos, no hace falta que hagas nada.",
    )


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
    """Hace el POST a la API de Meta. Devuelve True si salió bien (200-299),
    False si falló (por error de Meta o de conexión)."""
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code >= 400:
            print("Error de Meta al enviar mensaje:", response.status_code, response.text)
            return False
        return True
    except requests.exceptions.RequestException as e:
        print("Error al llamar a la API de Meta:", e)
        return False


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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --tinta: #1B2430;
      --acento: #B85C38;
      --papel: #FAF8F5;
      --borde: #E4DFD6;
    }
    * { box-sizing: border-box; }
    body {
      font-family: 'Inter', system-ui, sans-serif;
      background: var(--tinta);
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh; margin: 0; padding: 24px;
    }
    .caja {
      background: var(--papel);
      padding: 32px 28px;
      border-radius: 16px;
      box-shadow: 0 20px 60px rgba(0,0,0,.35);
      width: 100%; max-width: 340px;
    }
    .marca {
      font-size: 13px; font-weight: 600; letter-spacing: .02em;
      color: var(--acento); margin: 0 0 4px;
    }
    h1 {
      font-size: 20px; font-weight: 700; color: var(--tinta);
      margin: 0 0 24px; line-height: 1.3;
    }
    input {
      width: 100%; padding: 12px 14px; margin-bottom: 12px;
      border: 1.5px solid var(--borde); border-radius: 10px;
      font-size: 15px; font-family: inherit; box-sizing: border-box;
      background: white;
    }
    input:focus { outline: none; border-color: var(--acento); }
    button {
      width: 100%; padding: 12px; background: var(--acento); color: white;
      border: none; border-radius: 10px; font-size: 15px; font-weight: 600;
      font-family: inherit; cursor: pointer;
    }
    button:hover { filter: brightness(1.08); }
    .error {
      color: #A33; font-size: 13px; margin: 12px 0 0; padding: 10px 12px;
      background: #FBEAEA; border-radius: 8px;
    }
  </style>
</head>
<body>
  <div class="caja">
    <p class="marca">{{ nombre_negocio }}</p>
    <h1>Ingresá para ver tus conversaciones</h1>
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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --tinta: #1B2430;
      --tinta-suave: #2A3646;
      --acento: #B85C38;
      --aprobar: #2F6B4F;
      --pendiente: #B8862F;
      --papel: #FAF8F5;
      --borde: #E4DFD6;
      --texto-claro: #6B6459;
    }
    * { box-sizing: border-box; }
    body {
      font-family: 'Inter', system-ui, sans-serif;
      background: var(--papel); margin: 0; padding: 0;
      display: flex; height: 100vh; overflow: hidden;
      color: var(--tinta);
    }

    /* ---------- Barra lateral (lista de conversaciones) ---------- */
    .lista {
      width: 100%; max-width: 320px; background: var(--tinta);
      display: flex; flex-direction: column; flex-shrink: 0;
    }
    .lista-header {
      padding: 18px 16px 12px; display: flex; align-items: center;
      justify-content: space-between;
    }
    .lista-header .marca { color: white; font-weight: 700; font-size: 15px; margin: 0; }
    .salir {
      font-size: 12px; color: #B8B2A6; text-decoration: none; font-weight: 500;
    }
    .salir:hover { color: white; }
    .buscador { padding: 0 16px 12px; }
    .buscador input {
      width: 100%; padding: 9px 12px; border-radius: 8px; border: none;
      background: var(--tinta-suave); color: white; font-size: 14px; font-family: inherit;
    }
    .buscador input::placeholder { color: #8B8578; }
    .buscador input:focus { outline: 1.5px solid var(--acento); }
    .conversaciones { flex: 1; overflow-y: auto; }
    .fila {
      display: flex; align-items: center; gap: 10px;
      padding: 11px 16px; text-decoration: none; color: #E8E4DC;
      border-left: 3px solid transparent;
    }
    .fila:hover { background: var(--tinta-suave); }
    .fila.activo { background: var(--tinta-suave); border-left-color: var(--acento); }
    .avatar {
      width: 36px; height: 36px; border-radius: 50%; flex-shrink: 0;
      color: white; display: flex; align-items: center; justify-content: center;
      font-size: 14px; font-weight: 600;
    }
    .fila-texto { min-width: 0; flex: 1; }
    .fila-nombre {
      font-size: 14px; font-weight: 600; color: white;
      display: flex; align-items: center; gap: 6px;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .fila-preview {
      font-size: 12.5px; color: #9B9483; margin-top: 2px;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .badge-pendiente {
      background: var(--pendiente); color: white; font-size: 10.5px; font-weight: 600;
      padding: 2px 7px; border-radius: 20px; flex-shrink: 0;
    }
    .lista-vacia { padding: 24px 16px; color: #9B9483; font-size: 13.5px; line-height: 1.5; }

    /* ---------- Panel de conversación ---------- */
    .chat { flex: 1; display: flex; flex-direction: column; min-width: 0; background: var(--papel); }
    .chat-header {
      padding: 16px 22px; background: white; border-bottom: 1px solid var(--borde);
      display: flex; align-items: center; gap: 12px;
    }
    .chat-header .avatar { width: 40px; height: 40px; font-size: 15px; }
    .chat-header-info .nombre { font-weight: 700; font-size: 15.5px; }
    .chat-header-info .numero { font-size: 12.5px; color: var(--texto-claro); }
    .volver { display: none; color: var(--tinta); text-decoration: none; font-size: 20px; margin-right: 2px; }

    .comprobante {
      background: #FCF3E3; border-left: 3px solid var(--pendiente);
      border-radius: 10px; padding: 14px 16px; margin: 16px 22px 0; font-size: 14px;
    }
    .comprobante strong { display: block; margin-bottom: 8px; font-size: 13.5px; }
    .comprobante img { max-width: 100%; border-radius: 8px; margin: 8px 0; display: block; }
    .comprobante a.ver { color: var(--acento); font-size: 13px; font-weight: 600; }
    .btn-aprobar {
      background: var(--aprobar); color: white; border: none; padding: 9px 16px;
      border-radius: 8px; cursor: pointer; font-size: 13.5px; font-weight: 600;
      font-family: inherit; margin-top: 10px;
    }
    .btn-aprobar:hover { filter: brightness(1.1); }

    .mensajes { flex: 1; overflow-y: auto; padding: 20px 22px; display: flex; flex-direction: column; gap: 3px; }
    .fila-msg { display: flex; }
    .fila-msg.saliente { justify-content: flex-end; }
    .msg {
      padding: 9px 13px; border-radius: 12px; margin: 3px 0; max-width: 68%;
      font-size: 14.5px; line-height: 1.4; box-shadow: 0 1px 2px rgba(0,0,0,.04);
    }
    .entrante { background: white; border: 1px solid var(--borde); }
    .saliente { background: var(--acento); color: white; }
    .fecha { font-size: 10.5px; margin-top: 4px; opacity: .65; }
    .entrante .fecha { color: var(--texto-claro); }
    .saliente .fecha { color: rgba(255,255,255,.8); }

    /* Eventos del sistema (menú enviado, opción elegida, etc.) — no son
       mensajes de chat reales, van como una etiqueta centrada discreta. */
    .evento {
      align-self: center; font-size: 11.5px; color: var(--texto-claro);
      background: #EFEAE1; padding: 4px 12px; border-radius: 20px; margin: 6px 0;
    }

    form.responder {
      display: flex; gap: 10px; padding: 14px 22px; background: white;
      border-top: 1px solid var(--borde);
    }
    form.responder input {
      flex: 1; padding: 11px 14px; border: 1.5px solid var(--borde);
      border-radius: 10px; font-size: 14.5px; font-family: inherit;
    }
    form.responder input:focus { outline: none; border-color: var(--acento); }
    form.responder button {
      padding: 11px 18px; background: var(--acento); color: white; border: none;
      border-radius: 10px; font-weight: 600; font-size: 14px; font-family: inherit; cursor: pointer;
    }
    form.responder button:hover { filter: brightness(1.08); }

    .chat-vacio {
      flex: 1; display: flex; align-items: center; justify-content: center;
      color: var(--texto-claro); font-size: 14.5px; text-align: center; padding: 24px;
    }

    /* ---------- Mobile: una vista a la vez ---------- */
    @media (max-width: 720px) {
      .lista { max-width: none; }
      body.chat-abierto .lista { display: none; }
      body:not(.chat-abierto) .chat { display: none; }
      .volver { display: inline-block; }
    }
  </style>
</head>
<body class="{{ 'chat-abierto' if numero_activo and conversaciones.get(numero_activo) else '' }}">
  <div class="lista">
    <div class="lista-header">
      <p class="marca">{{ nombre_negocio }}</p>
      <a href="/panel/logout" class="salir">Salir</a>
    </div>
    <div class="buscador">
      <input type="text" id="buscar" placeholder="Buscar conversación..." oninput="filtrar()">
    </div>
    <div class="conversaciones" id="lista-conversaciones">
      {% for numero, datos in conversaciones.items() %}
        <a href="/panel?numero={{ numero }}" class="fila {{ 'activo' if numero == numero_activo else '' }}" data-nombre="{{ datos.nombre|lower }}">
          <span class="avatar" style="background:{{ datos.color }};">{{ datos.inicial }}</span>
          <span class="fila-texto">
            <span class="fila-nombre">
              {{ datos.nombre }}
              {% if numero in comprobantes_pendientes %}<span class="badge-pendiente">📎 pago</span>{% endif %}
            </span>
            <span class="fila-preview">{{ datos.ultimo_texto }}</span>
          </span>
        </a>
      {% else %}
        <p class="lista-vacia">Todavía no te escribió nadie. En cuanto llegue el primer mensaje, va a aparecer acá.</p>
      {% endfor %}
    </div>
  </div>
  <div class="chat">
    {% if numero_activo and conversaciones.get(numero_activo) %}
      {% set datos = conversaciones[numero_activo] %}
      <div class="chat-header">
        <a href="/panel" class="volver">←</a>
        <span class="avatar" style="background:{{ datos.color }};">{{ datos.inicial }}</span>
        <span class="chat-header-info">
          <span class="nombre">{{ datos.nombre }}</span><br>
          <span class="numero">{{ numero_activo }}</span>
        </span>
      </div>
      {% if numero_activo in comprobantes_pendientes %}
        {% set comp = comprobantes_pendientes[numero_activo] %}
        <div class="comprobante">
          <strong>📎 Comprobante pendiente de aprobación · {{ comp.fecha }}</strong>
          {% if comp.mime_type.startswith('image') %}
            <img src="/panel/media/{{ comp.id }}" alt="Comprobante">
          {% else %}
            <a class="ver" href="/panel/media/{{ comp.id }}" target="_blank">📄 Ver archivo adjunto</a>
          {% endif %}
          <form method="POST" action="/panel/aprobar">
            <input type="hidden" name="numero" value="{{ numero_activo }}">
            <input type="hidden" name="comprobante_id" value="{{ comp.id }}">
            <button type="submit" class="btn-aprobar">✅ Aprobar y enviar manuales</button>
          </form>
        </div>
      {% endif %}
      <div class="mensajes">
        {% for direccion, texto, fecha in datos.mensajes %}
          {% if texto.startswith('[') and texto.endswith(']') %}
            <div class="evento">{{ texto[1:-1] }} · {{ fecha }}</div>
          {% else %}
            <div class="fila-msg {{ 'saliente' if direccion == 'saliente' else '' }}">
              <div class="msg {{ 'entrante' if direccion == 'entrante' else 'saliente' }}">
                {{ texto }}
                <div class="fecha">{{ fecha }}</div>
              </div>
            </div>
          {% endif %}
        {% endfor %}
      </div>
      <form class="responder" method="POST" action="/panel/responder">
        <input type="hidden" name="numero" value="{{ numero_activo }}">
        <input type="text" name="texto" placeholder="Escribí una respuesta..." required autocomplete="off">
        <button type="submit">Enviar</button>
      </form>
    {% else %}
      <div class="chat-vacio">Elegí una conversación de la lista para ver los mensajes.</div>
    {% endif %}
  </div>
  <script>
    function filtrar() {
      var q = document.getElementById('buscar').value.toLowerCase();
      document.querySelectorAll('#lista-conversaciones .fila').forEach(function(fila) {
        fila.style.display = fila.dataset.nombre.includes(q) ? '' : 'none';
      });
    }
  </script>
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


# =====================================================================
#  Archivos propios: para productos (PDFs, etc.) que preferís alojar en
#  tu propio servidor en vez de depender de Google Drive u otro tercero.
#  Subí el archivo a la carpeta "archivos/" en tu repositorio, y va a
#  quedar disponible en: https://TU-APP.onrender.com/archivos/nombre.pdf
# =====================================================================
CARPETA_ARCHIVOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archivos")


@app.route("/archivos/<path:nombre_archivo>")
def servir_archivo(nombre_archivo):
    return send_from_directory(CARPETA_ARCHIVOS, nombre_archivo, as_attachment=False)


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

    # Paleta de colores para los avatares. Cada contacto siempre recibe el
    # mismo color (calculado a partir de su número), para que sea fácil
    # reconocerlo de un vistazo en la lista.
    PALETA_AVATARES = ["#B85C38", "#3F6E71", "#6B5B95", "#4C7A4C", "#A8763E", "#48577A"]

    conversaciones = {}
    for numero, direccion, texto, fecha in filas:
        if numero not in conversaciones:
            nombre = nombres.get(numero, numero)
            conversaciones[numero] = {
                "nombre": nombre,
                "inicial": nombre[0].upper() if nombre else "?",
                "color": PALETA_AVATARES[sum(numero.encode()) % len(PALETA_AVATARES)],
                "mensajes": [],
                "ultimo_texto": "",
                "ultima_fecha": "",
            }
        conversaciones[numero]["mensajes"].append((direccion, texto, fecha))
        # Vista previa: mostramos el último mensaje real (no un evento entre
        # corchetes, como "[Menú de packs enviado]"), para que la lista sea útil.
        if not (texto.startswith("[") and texto.endswith("]")):
            conversaciones[numero]["ultimo_texto"] = texto
        conversaciones[numero]["ultima_fecha"] = fecha

    # Ordenamos la lista de conversaciones por la más reciente primero.
    conversaciones = dict(
        sorted(conversaciones.items(), key=lambda item: item[1]["mensajes"][-1][2], reverse=True)
    )

    numero_activo = request.args.get("numero")
    if not numero_activo and conversaciones:
        numero_activo = list(conversaciones.keys())[0]

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
        # Usamos el producto que realmente le mostramos a este cliente, no
        # siempre "kit_maestro" (si no, se manda el archivo equivocado).
        clave_producto_actual = PRODUCTO_ACTUAL.get(numero, next(iter(PRODUCTOS)))
        enviar_manuales_completos(numero, clave_producto_actual)
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
