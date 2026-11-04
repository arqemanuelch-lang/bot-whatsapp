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
NOMBRE_NEGOCIO = "Droply IA"

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
    "¡Hola! 👋 Bienvenido a Droply IA. Elegí el producto que te interesa:"
)

# Bienvenida SIN productos: se manda cuando alguien saluda ("hola", etc.) sin
# haber tocado un anuncio ni escrito el nombre de un producto. La lista de
# productos aparece recién cuando toca el botón.
MENSAJE_BIENVENIDA_SIMPLE = (
    "¡Hola! 👋 Bienvenido a Droply IA. Estamos para ayudarte. "
    "Tocá el botón de abajo para ver lo que tenemos disponible 👇"
)
TEXTO_BOTON_LISTA = "📋 Ver productos"   # máx. 20 caracteres

# Número de respaldo al que el cliente puede escribir directamente con su
# comprobante si ya pagó y no obtuvo respuesta a tiempo. También se puede
# configurar por variable de entorno NUMERO_RESPALDO en Render (si está
# seteada ahí, tiene prioridad sobre este valor).
NUMERO_RESPALDO_DEFAULT = "+54 9 11 5143-9788"

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
COMENTARIO_LINK = ""
SEGUNDOS_PEDIR_COMENTARIO = 120   # cuánto espera después de entregar


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
    "Sos un asistente de ventas por WhatsApp para Droply IA, un negocio que vende "
    "productos digitales. Hoy vende: el Kit Maestro de Arquitectura y "
    "Construcción (16 manuales técnicos en PDF, $5.500), la Colección de Libros de Artes Marciales (25 carpetas de disciplinas, más de 1 GB de material digital, $6.500), el Pack Retro Games (juegos clásicos para el celular, $3.000). "
    "Respondé breve, claro y amable en español. Si el cliente pregunta por algo que no "
    "sea uno de esos tres productos, decile que por ahora solo están esos tres. "
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
PRODUCTOS = {
    "kit_maestro": {
        "titulo": "Kit Maestro de Arquitectura y Construcción",
        "titulo_boton": "Kit Maestro",  # texto del botón en el menú (máx. 20 caracteres)
        # --- Ficha en modo "oferta de libros": saludo, oferta, cada libro con su
        # portada (título + autor), el regalo y el precio con botón de compra.
        "modo_oferta_libros": True,
        # A los 5 minutos sin comprar: mensaje de venta directo con el adelanto de cada libro.
        "recordatorio_fuerte": {"segundos": 300},
        "saludo": (
            "¡Hola! 👋 Gracias por tu interés en el *Kit Maestro de Arquitectura y Construcción* 🏗️\n\n"
            "Te cuento qué te llevás 👇"
        ),
        "oferta_intro": (
            "🔥 *OFERTA ÚNICA* 🔥\n\n"
            "Llevate estos libros por solo *$5.500*:"
        ),
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
            "💰 *Precio:* $5.500  (precio normal ~$6.000~)\n"
            "🎁 Y de regalo: un plus único y sorpresa que te va a ayudar en el mundo de la construcción\n\n"
            "⚡ Es el precio vigente ahora y puede subir sin aviso, y el regalo es "
            "por tiempo limitado. Si te interesa, aprovechalo hoy."
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
            {"titulo": "Arquitectura: Forma, espacio y orden", "autor": "Francis D.K. Ching"},  # solo en lista, sin adelanto
            {"titulo": "Diccionario visual de arquitectura", "autor": "Francis D.K. Ching"},  # solo en lista, sin adelanto
            {"titulo": "Diseño de interiores: Un manual", "autor": "Francis D.K. Ching"},  # solo en lista, sin adelanto
            {"titulo": "Manual de dibujo arquitectónico", "autor": "Francis D.K. Ching"},  # solo en lista, sin adelanto
            {"titulo": "Design Drawing, 2nd Ed (ePub, en inglés)", "autor": "Francis D.K. Ching"},  # solo en lista, sin adelanto
            {"titulo": "Guía de Construcción Ilustrada", "autor": "Francis D.K. Ching"},  # solo en lista, sin adelanto
            {"titulo": "Manual de estructuras ilustrado", "autor": "Francis D.K. Ching"},  # solo en lista, sin adelanto
            {"titulo": "Historia global de la arquitectura", "autor": "Francis D.K. Ching y Mark Jarzombek"},  # solo en lista, sin adelanto
            {"titulo": "Arquitectura ecológica: Un manual ilustrado", "autor": "Francis D.K. Ching e Ian M. Shapiro"},  # solo en lista, sin adelanto
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
        # Si no compra en 15 min, se le ofrece este precio SOLO HASTA LAS 23:59 DE HOY
        # (el bot lo respeta de verdad: pasada la medianoche vuelve al precio normal).
        # Se ofrece una sola vez por cliente.
        "promo_hoy": {"segundos": 900, "precio": "$4.500", "precio_valor": 4500,
                      "imagen": "https://i.ibb.co/7db2hyg6/image.png"},  # flyer que va junto con el mensaje
        "sin_recordatorio_corto": True,  # no manda nada a los 3 minutos
        "saludo": (
            "¡Hola! 👋 Gracias por tu interés en la *Colección de Libros de Artes Marciales* 🥋\n\n"
            "Una biblioteca digital para los apasionados de las artes marciales. Te cuento qué incluye 👇"
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
            "💰 *Precio:* $6.500 (pago único)\n\n"
            "Escribí *ALIAS* y te paso todos los datos para transferir. 👇"
        ),
        "manuales": [],  # este producto no usa lista de libros
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
}
