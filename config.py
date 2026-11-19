# =====================================================================
#  CONFIG.PY — Todo lo que cambia de un negocio a otro va ACÁ.
#  ---------------------------------------------------------------
#  El archivo app.py es el "motor" del bot: recibe mensajes, manda
#  botones, guarda en la base, atiende el panel, maneja recordatorios,
#  IA de respaldo, etc. Eso NO se toca de un cliente a otro.
#
#  Este archivo, en cambio, es la "ficha" del negocio puntual: qué
#  vende, cómo se llama, cómo cobra, qué dice al saludar, etc.
#
#  Para armar un bot nuevo para otro negocio: copiás toda la carpeta,
#  reescribís SOLO este archivo de punta a punta, y listo.
# =====================================================================


import os

# ---------------------------------------------------------------------
# 1) DATOS GENERALES DEL NEGOCIO
# ---------------------------------------------------------------------
NOMBRE_NEGOCIO = "DROPLY | Biblioteca Digital"

# URL pública de tu propio servidor (Render), para poder alojar archivos
# propios en vez de depender de Google Drive. Si no configurás la
# variable de entorno BASE_URL en Render, usa este valor por defecto.
BASE_URL_ARCHIVOS = os.getenv("BASE_URL", "https://bot-whatsapp-ojza.onrender.com")

# Palabra "comodín" que la gente puede escribir para ver el menú de
# productos si el bot no entendió su mensaje (se muestra en el aviso de
# "no entendí tu mensaje").
PALABRA_CLAVE_MENU = "DROPLY"

# Mensaje de bienvenida que se manda junto con la lista de productos,
# la primera vez que alguien saluda ("hola", "buenas", etc.)
MENSAJE_BIENVENIDA_MENU = (
    "¡Hola! 👋 Bienvenido a DROPLY. Elegí el producto que te interesa:"
)

# Bienvenida SIN productos: se manda cuando alguien saluda ("hola", etc.) sin
# haber tocado un anuncio ni escrito el nombre de un producto. La lista de
# productos aparece recién cuando toca el botón.
MENSAJE_BIENVENIDA_SIMPLE = (
    "¡Hola{nombre}! 👋 ¿Cómo estás? Qué bueno que me escribiste. 😊\n\n"
    "Decime, ¿qué producto te interesa?\n\n"
    "👉 Podés elegirlo tocando el botón de abajo, o escribirme tu pregunta y te respondo. 👇"
)

# Si después del saludo la persona no toca el botón ni escribe nada, a los 3 minutos
# se le manda UN mensaje más (una sola vez). Poné SEGUNDOS_SEGUIMIENTO_BIENVENIDA = 0 para apagarlo.
SEGUNDOS_SEGUIMIENTO_BIENVENIDA = 180
MENSAJE_SEGUIMIENTO_BIENVENIDA = (
    "¡Hola{nombre}! 😊 Sigo por acá esperando.\n\n"
    "¿Cuál es el producto que te interesa? Tocá *📋 Ver productos* en el mensaje de arriba "
    "o escribime y te cuento todo. 🙌"
)
TEXTO_BOTON_LISTA = "📋 Ver productos"   # máx. 20 caracteres

# Número de respaldo al que el cliente puede escribir directamente con su
# comprobante si ya pagó y no obtuvo respuesta a tiempo. También se puede
# configurar por variable de entorno NUMERO_RESPALDO en Render (si está
# seteada ahí, tiene prioridad sobre este valor).
NUMERO_RESPALDO_DEFAULT = "5493487555205"

# Números a los que NO se les manda el seguimiento automático (avisos de 5 min y
# 1 hora). Es por prefijo de teléfono (código de país + área). Si escriben, el
# bot igual les responde y pueden comprar; solo se corta la insistencia.
#   "54911" / "5411"  -> CABA y Gran Buenos Aires (área 11)
# Si querés sumar ciudades de la provincia, agregá por ejemplo:
#   "549221" (La Plata), "549223" (Mar del Plata), "549291" (Bahía Blanca)
PREFIJOS_SIN_SEGUIMIENTO = ["54911", "5411"]

# Mensaje final de agradecimiento (se manda un rato después de entregar la compra).
# Pegá acá el link de tu página/Facebook/Instagram donde quieras el comentario.
# Si lo dejás vacío "", el mensaje sale igual pero sin link.
# Link de la publicación/anuncio donde el cliente deja su comentario. Se manda a los
# SEGUNDOS_PEDIR_COMENTARIO después de aprobar el pago (a todos los productos que no
# tengan su propio "mensaje_comentario"). Un producto puede tener su link propio con
# "link_comentario": "https://..." dentro de su bloque.
COMENTARIO_LINK = ""
# Segundos de espera entre cada mensaje cuando el cliente ve un producto (la imagen va primero).
# Cada producto puede tener la suya con "pausa": N dentro de su bloque.
PAUSA_MENSAJES = 10
# SEGUIMIENTO INTENSIVO a quien pide los datos de pago (COMPRAR / ALIAS) y no manda el comprobante.
# Cada paso es (segundos desde que pidió el alias, texto). Se repite hasta que manda el comprobante,
# escribe "no gracias" / "no me interesa", o pasan 23 horas (WhatsApp no deja mandar mensajes
# libres después de 24 h del último mensaje del cliente). No escribe de madrugada (0 a 8 hs).
# Variables en los textos: {nombre} {producto} {precio} {alias} {titular}. Lista vacía [] = apagado.
SEGUIMIENTO_ALIAS = [
    (600,
     "¡Hola{nombre}! 😊 ¿Cómo andás?\n\n"
     "Te escribo porque vi que pediste los datos para *{producto}* y quería saber si pudiste hacer la "
     "transferencia o si se te complicó algo 🤔\n\n"
     "A veces pasa: la app del banco no deja, el alias no aparece… ¡no te preocupes! Contame y te ayudo "
     "ahora mismo 🙌\n\n"
     "Por las dudas te dejo todo acá, a mano 👇\n\n"
     "👤 *Alias:* `{alias}`\n"
     "🏦 *Titular:* {titular}\n"
     "💰 *Total:* {precio}\n\n"
     "📩 Apenas pagues, mandame la foto del comprobante y en un ratito lo tenés en tu celular 🚀"),
    (3600,
     "¡Hola{nombre}! 💛\n\n"
     "Me quedé pensando en vos… ¿te imaginás ya teniendo *{producto}* en tu celular, listo para empezar hoy mismo? 🙌\n\n"
     "Es *pago único de {precio}*, sin cuotas ni vueltas, y apenas me mandes el comprobante te lo envío "
     "al instante por acá ⚡\n\n"
     "¿Te quedó alguna duda? Preguntame lo que quieras, sin ningún compromiso 😊\n\n"
     "👤 *Alias:* `{alias}`"),
    (3 * 3600,
     "¿Cómo va todo{nombre}? 😊\n\n"
     "Quería saber si pudiste avanzar con *{producto}*. Si algo te frenó (la transferencia, el alias, el monto, "
     "lo que sea) contámelo y lo resolvemos juntos 🤝\n\n"
     "Me encantaría que lo tengas ya en tus manos 🎁\n\n"
     "👤 *Alias:* `{alias}`\n"
     "💰 *Total:* {precio}\n\n"
     "Cuando pagues, mandame la foto del comprobante y listo 📲"),
    (8 * 3600,
     "¡Hola{nombre}! 👋\n\n"
     "Tu *{producto}* sigue guardado esperándote 🎁\n\n"
     "Sé que el día se complica y a veces las cosas quedan para después 😅 Pero si te interesa, hoy es un muy buen "
     "momento para dar el paso: pagás *{precio}* al alias `{alias}`, me mandás el comprobante y lo recibís en el momento ⚡\n\n"
     "Y si tenés cualquier duda, escribime que te respondo enseguida 🙌"),
    # ÚLTIMO mensaje (a las 23 h, antes de que se cierre la ventana de 24 h de WhatsApp): descuento del 30%.
    # El tercer valor es el % de descuento. Variables extra: {precio_descuento} {precio_normal} {descuento} {vence}
    (23 * 3600,
     "¡Última oportunidad{nombre}! 🎁🔥\n\n"
     "No quiero que te quedes sin *{producto}*, así que te dejo un regalo: *{descuento}% de DESCUENTO* solo para vos 🎉\n\n"
     "❌ ~{precio_normal}~\n"
     "✅ *{precio_descuento}*\n\n"
     "⏰ Válido hasta las *{vence} hs*.\n\n"
     "Para aprovecharlo, transferí al alias `{alias}` (titular: {titular}) y mandame el comprobante por acá. "
     "Lo recibís al instante 🚀\n\n"
     "Y si ya no te interesa, no pasa nada: escribime *\"no gracias\"* y no te molesto más 🙏😊",
     30),
]
# Horas que dura el descuento final (se cuenta desde que se manda el mensaje).
HORAS_VALIDEZ_DESCUENTO = 12
SEGUNDOS_PEDIR_COMENTARIO = 120   # cuánto espera después de entregar (120 = 2 minutos)


# ---------------------------------------------------------------------
# 2) DATOS DE COBRO (transferencia / Lemon)
# ---------------------------------------------------------------------
DATOS_TRANSFERENCIA = {
    "alias": "droply.ia",
    "cvu": "0000168300000023859803",
    "lemontag": "$emanuel.cristian",
    "titular": "Cristian Emanuel Chicchi Verbo",
}


# ---------------------------------------------------------------------
# 3) PROMPT PARA LA IA DE RESPALDO (Gemini / Groq)
#    Esto define cómo "habla" la IA cuando alguien pide hablar con un
#    asesor y todavía no lo atendió un humano.
# ---------------------------------------------------------------------
PROMPT_SISTEMA_IA = (
    "Sos un asistente de ventas por WhatsApp para DROPLY, un negocio que vende "
    "productos digitales. Entre sus productos están el PACK GAMER de 78 videojuegos para PC ($5.999, precio de oferta), el Kit Maestro de Arquitectura y "
    "Construcción (16 manuales técnicos en PDF, $5.500), la Colección de Libros de Artes Marciales (25 carpetas de disciplinas, más de 1 GB de material digital, $6.500), el Pack Retro Games (juegos clásicos para el celular, $3.000), TAPOUT XT, programa de entrenamiento desde casa en video ($8.999). "
    "Respondé breve, claro y amable en español. Si el cliente pregunta por algo que no "
    "sea un producto del catálogo, invitá a consultar el menú escribiendo DROPLY. "
    "Orientalo a escribir el nombre del producto (*kit maestro*, *retro games* o *canción*) para que el sistema le muestre la ficha completa."
)


# ---------------------------------------------------------------------
# 4) PALABRAS QUE ACTIVAN EL MENÚ GENERAL (saludos, etc.)
# ---------------------------------------------------------------------
PALABRAS_ACTIVADORAS = [
    "hola",
    "holaa",
    "buenas",
    "buen dia",
    "buenos dias",
    "buenas tardes",
    "buenas noches",
    "que tal",
    "quiero mas informacion",
    "quiero informacion",
    "mas informacion",
    "informacion",
    "kit maestro",
    "droply",
]


# ---------------------------------------------------------------------
# 4.1) FRASES DE ACCIÓN EN TEXTO LIBRE
#      ----------------------------------------------------------------
#      Mucha gente no toca los botones interactivos de WhatsApp y en
#      cambio escribe directamente lo que quiere. Estas listas funcionan
#      como una red de contención: si el mensaje contiene alguna de estas
#      frases, el bot hace LO MISMO que si hubiera tocado el botón
#      correspondiente (Ver qué incluye / Comprar / Hablar con asesor),
#      sin necesidad de que use los botones.
# ---------------------------------------------------------------------
FRASES_VER_QUE_INCLUYE = [
    "que incluye",
    "que trae",
    "los libros",
    "el contenido",
    "que tiene el pack",
    "los manuales",
    "que manuales son",
]

FRASES_COMPRAR = [
    "comprar",
    "quiero comprar",
    "como pago",
    "como hago para pagar",
    "cuanto sale",
    "el precio",
    "quiero pagar",
    "quiero adquirir",
    "como lo compro",
    "alias",
]

# ---------------------------------------------------------------------
# AVISOS POR TELEGRAM
#   Los comprobantes de pago SIEMPRE te llegan. Estas opciones controlan el resto.
#   TELEGRAM_AVISAR_TODO = False  -> NO te avisa cada mensaje ni cada botón (preguntas
#       sueltas como "cuánto cuesta?" las contesta el bot solo). Solo te llegan los
#       mensajes de quien pidió hablar con un asesor.
#   TELEGRAM_AVISAR_PIDE_ALIAS = True -> un aviso corto cuando alguien pide los datos de
#       pago (es el cliente más "caliente"). Poné False si tampoco lo querés.
#   Si ponés TELEGRAM_AVISAR_TODO = True, vuelve a avisar todo como antes.
# ---------------------------------------------------------------------
TELEGRAM_AVISAR_TODO = True  # True = te llega cada mensaje y cada botón que toque un cliente
TELEGRAM_AVISAR_PIDE_ALIAS = True


FRASES_ASESOR = [
    "hablar con un asesor",
    "hablar con alguien",
    "hablar con una persona",
    "hablar con un humano",
    "atencion al cliente",
    "quiero hablar con alguien",
]


# ---------------------------------------------------------------------
# 5) PRODUCTOS (packs) — agregá acá nuevos bloques y aparecen solos en
#    el menú del bot.
# ---------------------------------------------------------------------
# Link de la publicación/anuncio del kit de invitaciones, donde el cliente deja su comentario.
# PENDIENTE: pegar acá el link (entre las comillas).
LINK_ANUNCIO_INVITACIONES = ""

PRODUCTOS = {
    "kit_maestro": {
        "titulo": "Kit Maestro de Arquitectura y Construcción",
        "titulo_boton": "Kit Maestro",  # texto del botón en el menú (máx. 20 caracteres)
        # --- Ficha en modo "oferta de libros": saludo, oferta, cada libro con su
        # portada (título + autor), el regalo y el precio con botón de compra.
        "modo_oferta_libros": True,
        # A los 5 minutos sin comprar: mensaje de venta cálido con el adelanto de cada libro.
        "recordatorio_fuerte": {"segundos": 300},
        "saludo": (
            "¡Hola{nombre}! 👋 Qué bueno que me escribiste. Te cuento sobre el "
            "*Kit Maestro de Arquitectura y Construcción* 🏗️\n\n"
            "Es una biblioteca pensada para que proyectes, calcules y construyas con más seguridad, "
            "ya seas estudiante, profesional o estés levantando tu propia casa. 💪"
        ),
        "oferta_intro": (
            "Por solo *$5.500* te llevás estos *{n} libros* 🙌\n"
            "Mirá cuáles son 👇"
        ),
        "sin_botones_ficha": True,  # la ficha termina en el mensaje de ALIAS, sin botones
        # (sin promo "solo por hoy": este producto se vende siempre al precio normal)
        # (Mensaje alternativo de 20 min; solo se usa si se quita la promo de arriba.)
        "recordatorio_extra": {
            "segundos": 1200,
            "texto": (
                "¡Hola{nombre}! 😊 Te escribo para que te quedes tranquilo con la compra, "
                "así que te cuento cómo funciona:\n\n"
                "1️⃣ Me escribís *ALIAS* y te paso los datos para transferir.\n"
                "2️⃣ Transferís {precio} y me mandás la foto del comprobante.\n"
                "3️⃣ Apenas lo verifico, te llega el link de Drive con todo: los 16 libros y el plus sorpresa. 📂\n\n"
                "Lo abrís desde el celular o la compu y podés descargarlo para tenerlo siempre con vos. 💾\n\n"
                "Si tenés cualquier duda, escribime y te respondo enseguida. 🙌"
            ),
            "texto_alias": "✍️ ¿Arrancamos? Escribime *ALIAS* y te paso los datos. 👇",
        },
        "enviar_portadas": False,  # no manda una imagen por cada libro (queda solo el banner)
        "texto_vista_breve": "👀 *Y acá podés ver un adelanto de cada uno, sin compromiso:*",
        "texto_libros_regalo": "🎁 *Y no solo eso: además te llevás de REGALO estos {n} libros:*",
        "texto_regalo": "🎁 *Y para que arranques con todo, también te regalo:*",
        "texto_alias": "✍️ ¿Te sirve? Escribime *ALIAS* y te paso los datos para transferir. ¡Es rápido! 👇",
        "texto_botones": "O si preferís, tocá el botón 👇",
        "descripcion_corta": "16 manuales técnicos en PDF",
        "precio": "$5.500",
        "precio_oferta": "$5.500",
        "precio_valor": 5500,  # el mismo precio, pero como número (lo necesita Mercado Pago)
        "link_pago": "https://mpago.la/17uyqFK",
        "imagen": "https://i.ibb.co/1f2DYYpj/a722ab83-e521-4fef-b680-54e6a8b847b7.png",
        "imagen_oferta": "https://i.ibb.co/1f2DYYpj/a722ab83-e521-4fef-b680-54e6a8b847b7.png",
        # Carpeta de Google Drive con TODOS los manuales completos. Se manda
        # este único link cuando se confirma el pago (en vez de los links
        # individuales de cada manual, que son solo para "ver adelanto").
        "link_carpeta_final": "https://drive.google.com/drive/folders/1YwPEiA5UWOl60GIg_8YYxxVpWaaO6MSw?usp=sharing",
        # 2ª carpeta con los libros 8 al 16 (Ching). Se manda junto a la primera después del pago.
        "link_carpeta_extra": "https://drive.google.com/drive/folders/1ZmcDD6CkFwADoZZY3hceP_2yJ7tnnBse?usp=sharing",
        # Regalo y mensaje de precio con apuro, SIN fecha de vencimiento.
        "regalo_sorpresa": ["Un plus único y sorpresa que te va a ayudar en el mundo de la construcción"],
        "mensaje_precio": (
            "💰 *Todo por $5.500*  (precio normal ~$6.000~)\n"
            "Es un pago único: lo pagás una sola vez y es tuyo.\n\n"
            "Es el precio que tenemos ahora y puede subir más adelante, así que si te sirve, aprovechalo. 😉"
        ),
        # --- PROMO DE LOS 5 MINUTOS (bonus) ---
        # Si alguien ve la ficha y a los 5 minutos no avanzó, el bot le manda
        # esta oferta: "si comprás hoy, te llevás de regalo ...". Al aprobar el
        # pago (hasta 24 h después de la oferta) el bot le manda el regalo.
        # IMPORTANTE: la promo SOLO se activa si "link" tiene el link de Drive
        # del regalo completo. Mientras esté vacío, no se manda nada.
        "bonus_promo_DESACTIVADO": {
            "titulo": "Guía gráfica de Diseño Residencial (eBook de Luis Furushio)",
            "link": "https://drive.google.com/file/d/17516DKeXpsCORRvP4W1LjZfv3BdpPLoL/view?usp=sharing",  # eBook COMPLETO (se entrega después del pago)
            "password": "Orange-Black-Sky9",  # contraseña del PDF (se le manda al cliente junto con el regalo)
            "imagen": "https://i.ibb.co/wZYFYJmY/image.png",  # portada del regalo, se manda arriba del mensaje de los 5 min
            "imagen_recordatorio": "https://i.ibb.co/p6cn10qW/image.png",  # 2ª imagen, solo en el aviso de los 10 min
            "link_adelanto": "https://drive.google.com/file/d/1jP-ZFbKMh2lekFUwax2ElYHNTG942WVC/view?usp=sharing",  # adelanto breve (opcional)
            "segundos": 180,      # 5 minutos
            "segundos_recordatorio": 600,  # 10 minutos: segundo aviso si todavía no compró
        },
        "manuales": [
            {"titulo": "Cómo se proyecta una Vivienda", "imagen": "https://i.ibb.co/Zp0bL2Gm/image.png", "autor": "J.L. Moia",
             "link": "https://drive.google.com/file/d/114PXZLc-QRsfuEF3eSVSMlWEq_ICbJgQ/view?usp=sharing"},
            {"titulo": "Manual de Instalaciones Hidráulicas, Sanitarias, Aire, Gas y Vapor", "imagen": "https://i.ibb.co/GfpG5xQK/image.png", "autor": "Ing. Sergio Zepeda C.",
             "link": "https://drive.google.com/file/d/1ooDTnZyEAWwz_SeKjRxgps9N7FhwWiPS/view?usp=sharing"},
            {"titulo": "Método práctico para la elaboración de presupuestos de construcción", "imagen": "https://i.ibb.co/V0j8grhY/image.png", "autor": "Arq. William García",
             "link": "https://drive.google.com/file/d/1kfJe0vmQtXBl3p_mJ39kkU0GU-OwUDst/view?usp=sharing"},
            {"titulo": "Manual de Autoconstrucción", "imagen": "https://i.ibb.co/qMrRY3Gh/image.png", "autor": "Carlos Rodríguez",
             "link": "https://drive.google.com/file/d/1sbUe7XD2FRM5A-f2I6opXDoMF9y2gO1Q/view?usp=sharing"},
            {"titulo": "Manual del Arquitecto Descalzo", "autor": "Johan van Lengen",
             "link": "https://drive.google.com/file/d/1MhPK80rcTAnvZwbo2wv1wXAyxsrAgTFb/view?usp=sharing"},
            {"titulo": "Curso Básico de Instalaciones Eléctricas", "autor": "Juan Carlos Calloni",
             "link": "https://drive.google.com/file/d/1ETqTBa_nxWLigyHmQY8mvoeqqS49AIH3/view?usp=sharing"},
            {"titulo": "Instalaciones Sanitarias", "autor": "Jorge Ortíz",
             "link": "https://drive.google.com/file/d/1rd-tAxh3Qk8wcp-6TlFmzpjwzs25SEdA/view?usp=sharing"},
            {"titulo": "Arquitectura: Forma, espacio y orden", "autor": "Francis D.K. Ching", "regalo": True},  # de regalo, sin adelanto
            {"titulo": "Diccionario visual de arquitectura", "autor": "Francis D.K. Ching", "regalo": True},  # de regalo, sin adelanto
            {"titulo": "Diseño de interiores: Un manual", "autor": "Francis D.K. Ching", "regalo": True},  # de regalo, sin adelanto
            {"titulo": "Manual de dibujo arquitectónico", "autor": "Francis D.K. Ching", "regalo": True},  # de regalo, sin adelanto
            {"titulo": "Design Drawing, 2nd Ed (ePub, en inglés)", "autor": "Francis D.K. Ching", "regalo": True},  # de regalo, sin adelanto
            {"titulo": "Guía de Construcción Ilustrada", "autor": "Francis D.K. Ching", "regalo": True},  # de regalo, sin adelanto
            {"titulo": "Manual de estructuras ilustrado", "autor": "Francis D.K. Ching", "regalo": True},  # de regalo, sin adelanto
            {"titulo": "Historia global de la arquitectura", "autor": "Francis D.K. Ching y Mark Jarzombek", "regalo": True},  # de regalo, sin adelanto
            {"titulo": "Arquitectura ecológica: Un manual ilustrado", "autor": "Francis D.K. Ching e Ian M. Shapiro", "regalo": True},  # de regalo, sin adelanto
        ],
    },
    "pack_retro_games": {
        "titulo": "Pack Retro Games — Juegos Clásicos para tu Celular",
        "titulo_boton": "Pack Retro Games",
        "descripcion_corta": "Arcade y consolas clásicas, listos para jugar",
        "precio": "$3.000",
        "precio_oferta": "$3.000",
        "precio_valor": 3000,
        "imagen": "https://i.ibb.co/chHf0R6Q/cf1c03b1-1b60-4da4-a90e-ecdebe5ccf99-1.png",
        "imagen_oferta": "https://i.ibb.co/chHf0R6Q/cf1c03b1-1b60-4da4-a90e-ecdebe5ccf99-1.png",
        "emoji_ficha": "🎮",
        "saludo": (
            "¡Hola{nombre}! 👋 Qué bueno que me escribiste. Te cuento sobre el "
            "*Pack Retro Games* 🎮\n\n"
            "Son los juegos clásicos con los que crecimos, para que los vuelvas a jugar directo en tu celular. "
            "Mirá qué incluye 👇"
        ),
        "mensaje_precio": (
            "💰 *Todo por $3.000* (pago único: lo pagás una sola vez y es tuyo)\n\n"
            "¿Te sirve? Escribime *ALIAS* y te paso los datos para transferir. ¡Es rápido! 👇"
        ),
        # Carpeta de Drive con todo el pack. Se manda este link único cuando
        # se confirma el pago.
        "link_carpeta_final": "https://drive.google.com/drive/folders/1_LnUPbe7YTVMEZDkXP4vpWgAJVNIp5h4?usp=sharing",
        "que_incluye": [
            "Juegos clásicos de arcade y consolas retro para revivir la infancia",
            "Emulador incluido, con control táctil en pantalla",
            "Jugás directo en tu celular, sin cables ni consola",
            "Funciona en todo tipo de dispositivos",
            "Instrucciones paso a paso para instalarlo",
            "Acceso inmediato después de confirmar el pago",
        ],
        "manuales": [],  # este producto no usa manuales/PDFs
    },
    "artes_marciales": {
        "titulo": "Colección de Libros de Artes Marciales",
        "titulo_boton": "Artes Marciales",  # máx. 20 caracteres
        "descripcion_corta": "25 carpetas · más de 1 GB de material",
        "precio": "$6.500",
        "precio_oferta": "$6.500",
        "precio_valor": 6500,
        "imagen": "https://i.ibb.co/bRzGx6NH/1-1.png",
        "imagen_oferta": "https://i.ibb.co/bRzGx6NH/1-1.png",
        "emoji_ficha": "🥋",
        # (sin promo "solo por hoy": este producto se vende siempre al precio normal)
        "sin_recordatorio_corto": True,  # no manda nada a los 3 minutos
        "saludo": (
            "¡Hola{nombre}! 👋 Qué bueno que me escribiste. Te cuento sobre la "
            "*Colección de Libros de Artes Marciales* 🥋\n\n"
            "Es una biblioteca digital pensada para los que viven las artes marciales, ya sea que recién empiecen, "
            "entrenen hace años o enseñen. 💪 Mirá todo lo que incluye 👇"
        ),
        # Carpeta de Drive con todo el contenido. Se manda cuando se confirma el pago.
        "link_carpeta_final": "https://drive.google.com/drive/folders/1BwKeFXnaS_ZKkmLMtEgUGCTk9Nk3piMv?usp=sharing",
        "que_incluye": [
            "Más de 1 GB de material digital, en 25 carpetas por disciplina",
            "Boxeo, Muay Thai, Krav Maga, Defensa Personal, Lucha y Combate Militar",
            "Judo, Karate, Kyokushin, Aikido, Kendo, Jiujutsu y Ninjutsu",
            "Taekwondo, Hapkido, Kung Fu, Wushu, Chi Kung y Tai Chi",
            "Armas (Kobudo y Nunchaku), filosofía marcial y estrategia",
            "Acondicionamiento físico, anatomía, psicomotricidad y Kyusho",
            "Una carpeta completa de Bruce Lee",
            "Libros sueltos como la colección Aprendiendo Budo Taijutsu",
            "Entrega inmediata por Google Drive después de confirmar el pago",
            "Pago único, sin suscripciones",
        ],
        "texto_incluye": (
            "🥋 *Esto es lo que incluye la colección*\n"
            "Más de *1 GB* de material digital, ordenado en *25 carpetas* por disciplina 👇\n\n"
            "🥊 *Combate y deportes de contacto*\n"
            "Boxeo · Muay Thai · Lucha · Krav Maga · Lima Lama · Kenpo Kajukenbo · Combate Militar · Defensa Personal\n\n"
            "🇯🇵 *Artes marciales japonesas*\n"
            "Judo · Karate · Kyokushin · Aikido · Kendo · Jiujutsu · Ninjutsu y Shinobi Jutsu\n\n"
            "🇰🇷🇨🇳 *Coreanas y chinas*\n"
            "Taekwondo · Hapkido · Kung Fu · Wushu · Chi Kung · Tai Chi\n\n"
            "⚔️ *Armas, filosofía y estrategia*\n"
            "Kobudo y Nunchaku · Filosofía marcial y estrategia\n\n"
            "💪 *Cuerpo y preparación*\n"
            "Acondicionamiento físico · Anatomía y fisiología · Psicomotricidad · Kyusho y acupuntura\n\n"
            "🐉 *Bruce Lee*\n"
            "Una carpeta dedicada\n\n"
            "📘 *Y además, libros sueltos* como la colección Aprendiendo Budo Taijutsu, "
            "Antiguas y modernas artes marciales de Corea y Armas de combate callejero\n\n"
            "⚡ Entrega inmediata por Google Drive\n"
            "📱 Se abre en celular, tablet y computadora\n"
            "✅ Pago único, sin suscripciones"
        ),
        "mensaje_precio": (
            "💰 *Todo por $6.500* (pago único: lo pagás una sola vez y es tuyo)\n\n"
            "¿Te sirve? Escribime *ALIAS* y te paso los datos para transferir. ¡Es rápido! 👇"
        ),
        "manuales": [],  # este producto no usa lista de libros
    },
    "influir_masas": {
        "titulo": "Influir en las masas (eBook)",
        "titulo_boton": "Influir en las masas",  # máx. 20 caracteres
        "descripcion_corta": "eBook de psicología · 113 páginas",
        "precio": "$2.500",
        "precio_oferta": "$2.500",
        "precio_valor": 2500,
        "imagen": "",  # PENDIENTE: pegar el "Direct link" de imgbb (i.ibb.co/...) de la portada
        "imagen_oferta": "",
        "emoji_ficha": "🐺",
        # (sin promo "solo por hoy": este producto se vende siempre al precio normal)
        "sin_recordatorio_corto": True,
        "descripcion_entrega": "tu libro *Influir en las masas*, listo para leer y descargar",
        "saludo": (
            "¡Hola{nombre}! 👋 Qué bueno que me escribiste. Te cuento sobre *Influir en las masas* 🐺\n\n"
            "Es un libro que explica cómo un puñado de personas aprendió a mover la opinión de millones, "
            "y cómo reconocerlo para que no te lo hagan a vos. 🧠 Mirá de qué trata 👇"
        ),
        # Link de Drive con el PDF. Se manda al confirmar el pago.
        "link_carpeta_final": "https://drive.google.com/file/d/1B9KlUu6JAVj_WAz_4S-R8TKU9H5jQGoj/view?usp=sharing",
        "que_incluye": [
            "eBook completo en PDF, 113 páginas",
            "Cómo nació la propaganda moderna: Le Bon, Bernays y Lippmann",
            "Las 10 reglas de oro y los 5 filtros de la manipulación",
            "Marketing, redes y algoritmos como propaganda actual",
            "Las señales del manipulador y cómo defenderte",
            "Glosario de términos y cronología esencial",
            "Entrega inmediata por Google Drive",
            "Pago único, sin suscripciones",
        ],
        "texto_incluye": (
            "🐺 *Esto es lo que vas a aprender*\n"
            "Un libro de *113 páginas*, en 12 capítulos 👇\n\n"
            "📜 *La historia*\n"
            "Gustave Le Bon y la psicología de las multitudes · Edward Bernays, el sobrino de Freud que inventó las \"relaciones públicas\" · Walter Lippmann y el pseudoambiente\n\n"
            "🧠 *Las técnicas*\n"
            "Los lobos que llevamos dentro · Las diez reglas de oro · Los cinco filtros\n\n"
            "📱 *Hoy*\n"
            "El marketing como propaganda con traje y corbata · El algoritmo como el nuevo Bernays\n\n"
            "🛡️ *Cómo defenderte*\n"
            "Las señales del manipulador · La higiene mental del ciudadano · Sobrevivir al siglo XXI despierto\n\n"
            "📚 *Extras:* glosario de términos clave y cronología esencial\n\n"
            "⚡ Entrega inmediata por Google Drive\n"
            "📱 Se lee en celular, tablet y computadora\n"
            "✅ Pago único, sin suscripciones"
        ),
        "mensaje_precio": (
            "💰 *Todo por $2.500* (pago único: lo pagás una sola vez y es tuyo)\n\n"
            "¿Te sirve? Escribime *ALIAS* y te paso los datos para transferir. ¡Es rápido! 👇"
        ),
        "manuales": [],
    },
    "kit_invitaciones": {
        "titulo": "Kit Premium de Invitaciones Digitales",
        "titulo_boton": "Kit Invitaciones",  # máx. 20 caracteres
        "titulo_boton_compra": "✅ QUIERO",  # texto del botón de compra (máx. 20)
        "descripcion_corta": "+120 plantillas en Canva · 4 bonos",
        "precio": "$5.500",
        "precio_oferta": "$5.500",
        "precio_valor": 5500,
        "imagen": "https://i.ibb.co/hFxjKLPD/image.png",
        "imagen_oferta": "https://i.ibb.co/hFxjKLPD/image.png",
        "emoji_ficha": "💌",
        # Si no compra en 15 min: precio especial SOLO HASTA LAS 23:59 DE HOY (una sola vez por cliente).
        "promo_hoy": {"segundos": 900, "precio": "$3.900", "precio_valor": 3900},
        "sin_recordatorio_corto": True,
        # PDF que se manda como archivo adjunto al pagar. Está en la carpeta archivos/ del repo.
        "pdf_entrega": "Kit_Invitaciones_Digitales.pdf",
        # Pedido de comentario (reemplaza al genérico). Llega 5 minutos después de la entrega.
        # Si el cliente manda una imagen después, el bot la toma como la CAPTURA del comentario (no como pago).
        "segundos_comentario": 300,
        "mensaje_comentario": (
            "CON GUSTO! 😊\n"
            "Si eres tan amable de dejarnos tu comentario en nuestro anuncio sobre el kit de invitaciones "
            "te lo agradecería mucho!\n\n"
            "Puedes hacerlo aquí:\n"
            "👇👇👇\n"
            + (LINK_ANUNCIO_INVITACIONES + "\n" if LINK_ANUNCIO_INVITACIONES else "")
            + "👆👆👆\n\n"
            "Por tu ayuda te iremos regalando un Bono sorpresa por adelantado, "
            "por favor aguardo tu comentario en el anuncio 😁\n\n"
            "🎁 *Tu bono sorpresa por adelantado:* una plantilla de invitación de boda para editar en Canva 👇\n"
            "https://www.canva.com/design/DAG6cgJGF9c/p03QS0g32taRaSLluc3sBA/view?utm_content=DAG6cgJGF9c&utm_campaign=designshare&utm_medium=link&utm_source=publishsharelink&mode=preview\n\n"
            "✅ Me envías una captura de tu comentario por favor\n"
            "☑️ Muchas gracias de antemano por tu comentario 👍\n\n"
            "Bendiciones 🙏"
        ),
        # Mensaje que recibe al pagar (cuando vos aprobás). Después del mensaje se manda el PDF.
        "mensaje_entrega": (
            "🎉 *¡FELICITACIONES POR TU COMPRA!* 🎉\n\n"
            "Gracias por confiar en nosotros. Ya tenés en tus manos todo lo que necesitás para "
            "empezar tu negocio de invitaciones digitales. 💌✨\n\n"
            "📄 Te mando abajo la *guía de acceso*, con todo el material ordenado en 3 módulos. "
            "También la podés abrir desde Drive:\n{link}\n\n"
            "🎓 *Módulo 1 – Tutoriales en video*\n"
            "Aprendés paso a paso a editar, agregar cuenta regresiva y entregar en formato video o sitio web. "
            "Empezá por el primero: *Presentación del contenido*.\n\n"
            "🎨 *Módulo 2 – Biblioteca de plantillas*\n"
            "Tus kits de *Bodas* y *XV Años*, listos para editar en Canva.\n\n"
            "💰 *Módulo 3 – Cómo vender tus invitaciones*\n"
            "Más tus *4 bonos*: ganar dinero con invitaciones, cerrar ventas por WhatsApp, "
            "conseguir tus primeros clientes y portadas para redes.\n\n"
            "🎁 *Regalo extra:* curso de Canva para que domines la edición desde cero:\n"
            "https://drive.google.com/drive/folders/1TgPLl9iSsrZWTZ7KsNJyUHA2yzsATjYd?usp=sharing\n\n"
            "Cualquier duda, escribime por acá. 🙌"
        ),
        "saludo": (
            "¡Hola{nombre}! 👋 Qué bueno que me escribiste.\n\n"
            "Emprendé desde casa creando invitaciones bonitas, modernas y listas para vender 💵✨\n\n"
            "Con el *Kit Premium* vas a poder crear:\n"
            "✨ Invitaciones digitales para bodas y 15 años\n"
            "🎥 Invitaciones en video\n"
            "🌐 Invitaciones tipo web interactivas\n"
            "📍 Con ubicación\n"
            "✅ Confirmación de asistencia\n"
            "⏳ Contador regresivo\n"
            "💌 Save the Date\n"
            "🎵 Podés agregar música, fotos y diseño personalizado según el evento.\n\n"
            "Con las plantillas no tenés que diseñar desde cero: es solamente editar. 🙌"
        ),
        # Link de Drive del mismo PDF: respaldo por si falla el envío del archivo adjunto.
        "link_carpeta_final": "https://drive.google.com/file/d/1O1Kel_7Akn1_HTnRXgn_TOJR9YZjJRRl/view?usp=sharing",
        "que_incluye": [
            "Más de 120 plantillas editables en Canva",
            "Videoaulas cortas paso a paso",
            "Invitaciones en formato video y tipo web",
            "Save the Date",
            "Botones de ubicación y confirmación",
            "4 bonos de regalo",
        ],
        "texto_incluye": (
            "💌 *¿Qué recibís dentro del kit?*\n\n"
            "✅ Más de *120 plantillas editables en Canva*, listas para usar\n"
            "✅ Videoaulas cortas, paso a paso\n"
            "✅ Invitaciones en formato video\n"
            "✅ Invitaciones tipo web\n"
            "✅ Save the Date\n"
            "✅ Botones de ubicación y confirmación\n\n"
            "📂 Todo está en Drive, ordenado para que avances sin complicarte.\n\n"
            "🎁 *Y además, 4 BONOS DE REGALO:*\n"
            "🎁 Bono 1: Guía para ganar dinero vendiendo invitaciones\n"
            "🎁 Bono 2: Guía para cerrar ventas por WhatsApp\n"
            "🎁 Bono 3: Guía para conseguir tus primeros clientes\n"
            "🎁 Bono 4: Portadas editables para redes sociales\n\n"
            "Con estos bonos tenés todo para arrancar tu negocio. 🚀"
        ),
        "mensaje_precio": (
            "🇦🇷 *Precio OFERTA: $5.500*\n\n"
            "✅ Pago único y de por vida\n"
            "📚 Los archivos son digitales, te los envío por acá mismo.\n\n"
            "📲 Tocá *QUIERO* (o escribilo) y te paso el ALIAS 👇"
        ),
        "manuales": [],
    },
    "pack_gamer_pc": {
        "titulo": "PACK GAMER — 78 VIDEOJUEGOS CLÁSICOS PARA PC",
        "titulo_boton": "🎮 Pack Gamer PC",
        "titulo_boton_compra": "🛒 Comprar ahora",
        "descripcion_corta": "78 juegos clásicos · Entrega digital",
        # (sin promo "solo por hoy": este producto se vende siempre al precio normal)
        "precio": "$5.999",
        "precio_oferta": "$5.999",
        "precio_valor": 5999,
        "imagen": "https://i.ibb.co/V1HcNMh/018467ac-a5a7-4c5c-a336-4d4f26313206.png",
        "manuales": [],
        "que_incluye": ["78 videojuegos y ediciones para PC", "Entrega digital por TeraBox tras aprobar el pago"],
        "texto_entrega": "el enlace digital del PACK GAMER",
        "descripcion_entrega": "el PACK GAMER — 78 videojuegos para PC",
        "link_carpeta_final": "https://www.1024tera.com/spanish/sharing/link?surl=VHEDjhXw_J7mb5qF02usvA",
        "mensaje_entrega": "🎉 *¡PAGO CONFIRMADO!*\n\n🎮 ¡Gracias por comprar el *PACK GAMER*!\n\n📦 Tu colección de 78 videojuegos y ediciones para PC está lista.\n\n🔗 *ENLACE DE ENTREGA:*\n{link}\n\n💻 Accedé al enlace para consultar y descargar los archivos.\n\n🙌 ¡Gracias por confiar en DROPLY!",
        "saludo": "¡Hola! 👋🎮 ¡Gracias por tu interés en nuestro *PACK GAMER — 78 VIDEOJUEGOS CLÁSICOS PARA PC*!\n\n🕹️ Reviví los grandes clásicos que marcaron generaciones. Acción, aventura, estrategia, carreras, terror y mucho más.\n\n👇 ¡Mirá algunos de los juegos que incluye!",
        "texto_incluye": "🎮 *ALGUNOS DE LOS JUEGOS DEL PACK*\n\n🏙️ GTA San Andreas\n🔫 Counter-Strike 1.6\n⚔️ Age of Empires I, II y III\n🧟 Resident Evil\n🏎️ Need for Speed Underground 2\n💥 Call of Duty\n🕹️ Half-Life y Half-Life 2\n🏡 The Sims\n🌻 Plants vs. Zombies\n\n🔥 ¡Y muchos títulos más!\n\n💻 *Para PC*\n📚 *78 videojuegos y ediciones en el catálogo.*",
        "mensaje_precio": "🎮 *¡VOLVÉ A VIVIR LOS GRANDES CLÁSICOS!*\n\n🕹️ GTA San Andreas, Counter-Strike, Age of Empires, Need for Speed y muchos más te están esperando. 🔥\n\n💻 *PACK GAMER PARA PC*\n🎮 78 videojuegos y ediciones en el catálogo.\n\n💰 *PRECIO DE OFERTA: $5.999 ARS*\n\n✅ Un solo pago, sin suscripciones.\n📂 Entrega digital por TeraBox después de confirmar el pago.\n\n🚀 *¡Tu próxima aventura gamer empieza acá!*\n\n👇 Tocá el botón *COMPRAR AHORA*.\n\n✍️ O si preferís, escribí *ALIAS* y te paso los datos para que puedas realizar el pago. 🙌",
        "catalogo_juegos": [
            'Age of Empires Gold',
            'Age of Empires II',
            'Age of Empires III',
            'Alice: Madness Returns',
            'Aliens versus Predator Classic',
            'Batman: Vengeance',
            'Battlefield 1942',
            'Battlefield: Bad Company',
            'Call of Duty 2',
            'Call of Duty: World at War',
            'Castle Crashers',
            'Castlevania Advance Collection',
            'Cold Fear',
            'Contra Anniversary Collection',
            'Counter-Strike 1.6',
            'Cuphead',
            'Day of Defeat: Source',
            'DELTARUNE',
            'DOOM + DOOM II Enhanced',
            'DOOM 64',
            "Don't Starve",
            "Don't Starve Together",
            'F.E.A.R. Platinum',
            'F.E.A.R. 2: Project Origin',
            'Fallout 3: Game of the Year Edition',
            'Grand Theft Auto: San Andreas',
            'Grand Theft Auto (versión por identificar)',
            'Half-Life',
            'Half-Life 2: The Orange Box',
            'Halo: Combat Evolved',
            'Hitman: Codename 47',
            'Hitman 2: Silent Assassin',
            'Just Cause',
            'Just Cause 2',
            'Land of the Dead',
            'Mafia: The City of Lost Heaven',
            'Mafia II',
            'Max Payne',
            'Medal of Honor: Allied Assault',
            'Metal Slug PC',
            'Mortal Kombat',
            'Need for Speed: Underground 2',
            'Noita',
            'Penumbra Collection',
            'Plants vs. Zombies GOTY',
            'Plague Inc: Evolved',
            'Portal',
            'Portal 2',
            'Postal 2',
            'Pro Evolution Soccer 6 (PES 6)',
            'Pro Evolution Soccer 2013 (PES 2013)',
            'Quake III: Gold Edition',
            'Quake 4',
            'Rayman Origins',
            'Resident Evil 2 HD',
            'Resident Evil 3 HD',
            'Resident Evil 4',
            'Resident Evil HD Remaster',
            'RimWorld',
            "Saint Seiya: Soldiers' Soul",
            'Scooby-Doo! First Frights',
            'SimCity 4 Deluxe Edition',
            'Splinter Cell: Chaos Theory',
            'StarCraft Remastered',
            'Star Wars Jedi Knight II: Jedi Outcast',
            'Terraria',
            'The Binding of Isaac: Rebirth',
            'The Golden Compass',
            'The Lord of the Rings: The Return of the King',
            'The Sims 1 Legacy Collection',
            'The Sims 2 Legacy Collection',
            'Tomb Raider 1 + 2 + 3',
            'Ultimate Spider-Man',
            'Unreal Tournament 1999',
            'Unreal Tournament 2004',
            'Warcraft III: Reign of Chaos',
            'Warcraft III: The Frozen Throne',
            'Yu-Gi-Oh! Power of Chaos',
        ],
        "requisitos_pc": "💻 *REQUISITOS MÍNIMOS — PACK GAMER*\n\n🎮 *Configuración orientativa para juegos clásicos:*\n\n🖥️ Sistema operativo: Windows 10 u 11.\n⚙️ Procesador: Intel Core i3 o equivalente.\n🧠 Memoria RAM: 4 GB como referencia inicial.\n🎨 Gráficos: compatibles con los requisitos de cada juego.\n💾 Almacenamiento: espacio disponible según el videojuego.\n\n🎓 *¿TENÉS UNA NETBOOK DEL GOBIERNO?*\n\n🎮 ¡También podés disfrutar de muchos de los clásicos del PACK GAMER!\n\n✅ Una gran cantidad de juegos clásicos pueden funcionar sin problemas en determinadas netbooks del Gobierno.\n\n💻 La compatibilidad depende del modelo de tu computadora y de los requisitos de cada videojuego.\n\n🔥 ¡Reviví tus juegos favoritos y disfrutá horas de diversión!\n\n⚠️ Estos requisitos son orientativos y no garantizan compatibilidad con los 78 juegos.",
    },
    "entrenamiento_xt2": {
        "titulo": "TAPOUT XT — Programa de Entrenamiento",
        "titulo_boton": "TAPOUT XT",  # máx. 20 caracteres
        "titulo_boton_compra": "✅ QUIERO",
        "descripcion_corta": "Entrená desde casa · en video",
        "precio": "$8.999",
        "precio_oferta": "$8.999",
        "precio_valor": 8999,
        "imagen": "",  # PENDIENTE: "Direct link" de imgbb (i.ibb.co/...) de una portada propia
        "imagen_oferta": "",
        "imagen_muestra": "https://i.ibb.co/vCBXW7qt/A-A.png",  # foto de muestra, se manda antes del precio
        "emoji_ficha": "💪",
        # PROMO "solo por hoy": todavía sin definir (a pedido, con el precio nuevo de $8.999).
        "sin_recordatorio_corto": True,
        "saludo": (
            "🥊 ¡Hola{nombre}! 👋 Bienvenido a *TAPOUT XT*.\n\n"
            "🔥 ¿Te gustaría entrenar desde casa con un programa que combina movimientos de "
            "artes marciales, fuerza y resistencia?\n\n"
            "Con *TAPOUT XT* podés seguir entrenamientos organizados desde tu celular, "
            "computadora o TV compatible.\n\n"
            "📲 Es 100% digital, con acceso mediante Google Drive.\n\n"
            "💪 ¿Querés conocer todo lo que incluye el programa? 👇"
        ),
        "link_carpeta_final": "https://drive.google.com/drive/folders/1-Qn0B2zDcroVxC5Wa1lD0GJlVR0I7LTi?usp=sharing",
        "que_incluye": [
            "Entrenamientos guiados en video",
            "Rutinas para diferentes grupos musculares",
            "Ejercicios cardiovasculares y de acondicionamiento",
            "Material de planificación de entrenamientos",
            "Guías de alimentación y material complementario",
            "Plan de entrenamiento (PDF)",
            "Plan de alimentación (PDF)",
            "Guía de adelgazamiento de 10 días (PDF)",
            "Pago único, sin cuotas mensuales",
        ],
        "texto_incluye": (
            "🔥 *TAPOUT XT — ENTRENÁ DESDE CASA* 🥊\n"
            "Es un programa de acondicionamiento físico inspirado en las artes marciales, "
            "que combina ejercicios de fuerza, resistencia, coordinación y cardio.\n\n"
            "📦 *¿Qué encontrás en el pack?*\n"
            "🥊 Entrenamientos guiados en video.\n"
            "💪 Rutinas para trabajar diferentes grupos musculares.\n"
            "🔥 Ejercicios cardiovasculares y de acondicionamiento físico.\n"
            "📋 Material de planificación de entrenamientos.\n"
            "🥗 Guías de alimentación y material complementario.\n"
            "📲 Todo organizado digitalmente para que puedas seguirlo desde casa.\n\n"
            "🎁 *Y además te llevás, aparte:*\n"
            "📋 *Plan de entrenamiento* (PDF)\n"
            "🥗 *Plan de alimentación* (PDF)\n"
            "🔥 *Guía de adelgazamiento de 10 días* (PDF)\n\n"
            "✅ Pago único, sin cuotas mensuales.\n"
            "💰 *Pack completo: $8.999 ARS.*"
        ),
        "mensaje_precio": (
            "🎬 *Mirá 3 muestras del programa, para que veas cómo se entrena:*\n\n"
            "1️⃣ *Abdominales extremas* 🔥\n"
            "https://drive.google.com/file/d/1z9Jg_pp3ihwSl8Bw9fNG84x-DOFbbeoP/view?usp=sharing\n\n"
            "2️⃣ *Boxeo thailandés* 🥊\n"
            "https://drive.google.com/file/d/1gSALtUQkB9Yb9t4At6Z4Gu4tAmm3ZKYG/view?usp=sharing\n\n"
            "3️⃣ *Rutina de cardio* 💪\n"
            "https://drive.google.com/file/d/1Xn3cqmfbXJ7096vOQm_pP6YEkXJZf2t_/view?usp=sharing\n\n"
            "📲 Tocá *QUIERO* (o escribilo) y te cuento cómo recibís el acceso y te paso el ALIAS 👇"
        ),
        "mensaje_entrega": (
            "✅ *¡Pago confirmado!* 🥊\n\n"
            "Acá tenés tu *TAPOUT XT*, con todo el material listo para ver:\n"
            "{link}\n\n"
            "📂 *Adentro vas a encontrar:*\n"
            "🎥 Los entrenamientos en video\n"
            "📁 La carpeta *TAPOUT XT PDF*, con tus 3 extras:\n"
            "   📋 Plan de entrenamiento\n"
            "   🥗 Plan de alimentación\n"
            "   🔥 Guía de adelgazamiento de 10 días\n\n"
            "¡Gracias por tu compra y a entrenar! 💪🙌"
        ),
        "manuales": [],
    },
}


# ---------------------------------------------------------------------
# 5.1) PROMOS POR TIEMPO LIMITADO
#      ----------------------------------------------------------------
#      Mientras la promo está vigente, el bot usa el precio de la promo y
#      muestra el regalo sorpresa. Cuando pasa la fecha "hasta" (inclusive,
#      hora de Argentina), vuelve SOLO al precio normal de PRODUCTOS.
#      Para terminar la promo antes: borrá el bloque o poné una fecha pasada.
#      OJO: el regalo tiene que estar de verdad dentro de la carpeta de
#      entrega del producto.
# ---------------------------------------------------------------------
PROMOS = {
    # Vacío: ya no hay promos con vencimiento. Para una promo con fecha, agregá acá
    # un bloque como el de abajo (ejemplo, no está activo):
    # "kit_maestro": {"hasta": "2026-12-31", "precio": "$5.000", "precio_valor": 5000,
    #                 "precio_normal": "$5.500", "regalo": "...", "aviso": "⏰ Promo hasta el 31/12"},
}


# ---------------------------------------------------------------------
# 6) ⭐ PALABRAS CLAVE POR PRODUCTO ⭐
#    ACÁ ES DONDE TENÉS QUE EDITAR CUANDO QUIERAS CAMBIAR O AGREGAR
#    PALABRAS.
#
#    Esto sirve para 2 casos:
#     1) Cuando alguien entra desde un anuncio de Facebook/Instagram (el
#        texto pre-cargado del anuncio, ej: "Hola, quiero más información
#        sobre el pack arquitectura y construcción").
#     2) Cuando alguien escribe directamente ese mismo tipo de frase sin
#        venir de un anuncio.
#
#    En ambos casos, si el texto contiene alguna de estas palabras, el
#    bot manda DIRECTO la ficha de ESE producto (no la lista completa).
#
#    Reglas simples:
#     - La clave (a la izquierda, ej: "kit_maestro") tiene que ser
#       EXACTAMENTE igual a la clave que usaste arriba en PRODUCTOS.
#     - Podés poner tantas palabras/frases como quieras por producto.
#     - No hace falta poner tildes ni mayúsculas.
#     - Cuando agregues un producto nuevo en PRODUCTOS, agregá acá
#       también su lista de palabras clave.
# ---------------------------------------------------------------------
PALABRAS_POR_PRODUCTO = {
    "pack_gamer_pc": ["pack gamer", "pack gamer pc", "78 juegos", "juegos para pc", "videojuegos clasicos"],
    "entrenamiento_xt2": [
        "tapout",
        "xt2",
        "programa de entrenamiento",
        "entrenamiento en casa",
        "entrena desde casa",
        "entrenar desde casa",
        "rutinas de ejercicio",
        "ejercicios en casa",
    ],
    "kit_maestro": [
        "arquitectura",
        "construccion",
        "kit maestro",
        "pack arquitectura",
        "manuales de construccion",
        "arquitectura y construccion",
    ],
    "pack_retro_games": [
        "retro",
        "retro games",
        "pack retro",
        "juegos retro",
        "juegos clasicos",
        "arcade",
        "emulador",
        "juegos para el celular",
    ],
    "artes_marciales": [
        "artes marciales",
        "libros de artes marciales",
        "coleccion de artes marciales",
        "karate",
        "judo",
        "taekwondo",
        "kung fu",
        "krav maga",
        "muay thai",
        "defensa personal",
    ],
    "influir_masas": [
        "influir en las masas",
        "influir masas",
        "klaus brenner",
        "propaganda",
        "manipulacion",
        "psicologia de masas",
    ],
    "kit_invitaciones": [
        "invitaciones",
        "invitaciones digitales",
        "kit premium",
        "kit de invitaciones",
        "plantillas canva",
        "invitaciones para bodas",
        "invitaciones 15 anos",
    ],
}
