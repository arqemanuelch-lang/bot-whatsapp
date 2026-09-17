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

# Número de respaldo al que el cliente puede escribir directamente con su
# comprobante si ya pagó y no obtuvo respuesta a tiempo. También se puede
# configurar por variable de entorno NUMERO_RESPALDO en Render (si está
# seteada ahí, tiene prioridad sobre este valor).
NUMERO_RESPALDO_DEFAULT = "+54 9 11 5143-9788"


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
    "productos digitales en PDF: manuales técnicos de construcción y arquitectura "
    "(Kit Maestro), y libros de desarrollo personal (33 Días de Manifestación). "
    "Respondé breve, claro y amable en español. Si no sabés bien qué producto le "
    "interesa al cliente, preguntale directamente. Orientalo a escribir el nombre "
    "del producto que le interesa para que el sistema le muestre la ficha completa."
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
        "descripcion_corta": "8 manuales técnicos en PDF",
        "precio": "$5.500",
        "precio_oferta": "$5.500",
        "precio_valor": 5500,  # el mismo precio, pero como número (lo necesita Mercado Pago)
        "link_pago": "https://mpago.la/17uyqFK",
        "imagen": "https://i.ibb.co/R40sSbHt/Sin-t-tulo-1080-1920-px-1080-x-1080-px-1080-x-1920-px-1080-x-1350-px-1.png",
        "imagen_oferta": "https://i.ibb.co/Xxj34Py5/bdb49a96-6a16-459f-bde7-bf4ceedb98db.jpg",
        # Carpeta de Google Drive con TODOS los manuales completos. Se manda
        # este único link cuando se confirma el pago (en vez de los 8 links
        # individuales de cada manual, que son solo para "ver adelanto").
        "link_carpeta_final": "https://drive.google.com/drive/folders/1YwPEiA5UWOl60GIg_8YYxxVpWaaO6MSw?usp=sharing",
        "manuales": [
            {"titulo": "Cómo se proyecta una Vivienda", "autor": "J.L. Moia",
             "link": "https://drive.google.com/file/d/12MHAHdQZ7Bm7RTBTD1SVdd0XxDXNO54L/view?usp=sharing"},
            {"titulo": "Curso básico de instalaciones eléctricas", "autor": "Calloni Rodrigues",
             "link": "https://drive.google.com/file/d/1XTeI93qPpw0BT2J0l7qhiY_MJKd1iXHD/view?usp=sharing"},
            {"titulo": "Instalaciones Eléctricas Monofásicas", "autor": "Ing. César Anibal Rey",
             "link": "https://drive.google.com/file/d/19TKBsowVtj4Q0w5OSOaZ7AeS7aBEs_Kw/view?usp=sharing"},
            {"titulo": "Manual para el Técnico Instalador Electricista Domiciliario", "autor": "Levy",
             "link": "https://drive.google.com/file/d/19TKBsowVtj4Q0w5OSOaZ7AeS7aBEs_Kw/view?usp=sharing"},
            {"titulo": "Manual Práctico de la Construcción", "autor": "Jaime Nisnovich",
             "link": "https://drive.google.com/file/d/1kKYvLhGcKLHqmit32kLVuiX3swnBGKGv/view?usp=sharing"},
            {"titulo": "Manual Práctico de Instalaciones Sanitarias: Tomo 1", "autor": "Nisnovich, Castro, Lázaro",
             "link": "https://drive.google.com/file/d/1oHuKcqXp2SFBAyYSbmqByJFjyn7i7yuY/view?usp=sharing"},
            {"titulo": "Manual Práctico de Instalaciones Sanitarias: Tomo 2", "autor": "Nisnovich, Castro, Lázaro",
             "link": "https://drive.google.com/file/d/1dQQC9-GfUjkS-GTAfzL8x1_G4A15k1GO/view?usp=sharing"},
            {"titulo": "Manual Práctico para Proyectar Buenas Viviendas", "autor": "Jaime Nisnovich",
             "link": "https://drive.google.com/file/d/1_YZf_GexbX-nE-PK4fBWlv05Ygu1iVw5/view?usp=sharing"},
        ],
    },
    "manifestacion_33_dias": {
        "titulo": "Pack Manifestación Premium (3 Libros + Regalos)",
        "descripcion_corta": "3 libros + 2 de regalo, en PDF/epub",
        "precio": "$5.500",
        "precio_oferta": "$5.500",
        "precio_valor": 5500,
        "imagen": "https://i.ibb.co/Ngkpy6Lp/f21261a8-0358-4b93-88b6-6049d2a83ee8.jpg",
        "imagen_oferta": "https://i.ibb.co/DfQc5Yr2/333.png",
        "mostrar_dos_imagenes": True,  # este producto manda las 2 imágenes juntas en la ficha inicial
        # Carpeta con los 5 archivos (los 3 principales + los 2 de regalo).
        # Se manda este link único cuando se confirma el pago.
        "link_carpeta_final": "https://drive.google.com/drive/folders/1UEKFVOzt_hYG7p2a7UVfBhC0-SfVbOYI?usp=sharing",
        # Los 3 libros que SÍ se publicitan, cada uno con su link de
        # adelanto (vista previa antes de comprar).
        "manuales": [
            {"titulo": "33 Días de Manifestación: Manual para la Creación", "autor": "Ulises Sampe",
             "link": "https://drive.google.com/file/d/10Rg9SZuh9oY02LRV16wUO3jqMh19QaDG/view?usp=sharing"},
            {"titulo": "Imaginaria", "autor": "Kristopher Rodas",
             "link": "https://drive.google.com/file/d/1cfvnHMHzZrIMOEpGPPIa43H-djx5i1Fs/view?usp=sharing"},
            {"titulo": "Realifestación", "autor": "Catalina Luz Navarro",
             "link": "https://drive.google.com/file/d/1Am14bDNYv67nGHg0qB0ezY1_uPwSPDfa/view?usp=sharing"},
        ],
        # Los 2 libros de REGALO: NO se mencionan en la publicidad, son la
        # sorpresa que se descubre acá, cuando el bot muestra el detalle
        # del pack (no tienen link de adelanto individual, solo título y
        # autor — se entregan completos junto con todo lo demás al pagar).
        "regalo_sorpresa": [
            "El Poder del Pensamiento Positivo — Norman Vincent Peale",
            "El Secreto — Rhonda Byrne",
        ],
        "emoji_ficha": "✨",
    },
    "cuenta_gemini_ai_pro": {
        "titulo": "Gemini AI Pro — Suscripción 18 meses",
        "descripcion_corta": "Cuenta con 5 TB de almacenamiento",
        "precio": "$15.990",
        "precio_oferta": "$15.990",
        "precio_valor": 15990,
        "imagen": "https://i.ibb.co/ymjhb3TF/Sin-t-tulo-1080-x-1920-px-1080-x-1080-px-1.png",
        # Mensajes personalizados (con más gancho/urgencia) para este
        # producto, en vez de usar la plantilla genérica.
        "saludo": (
            "🎉 ¡Genial que quieras aprovechar la oferta de *Gemini AI Pro*! "
            "Ya diste el primer paso para tener la IA más avanzada de Google "
            "trabajando para vos. Te cuento todo lo que te llevás 👇"
        ),
        "mensaje_precio": (
            "💰 *Precio:* $15.990 (pago único, sin mensualidades)\n"
            "🛡️ Con garantía durante los 18 meses de tu suscripción.\n\n"
            "⏰ Cupos limitados — activamos tu cuenta el mismo día que "
            "confirmamos el pago.\n\n"
            "Si querés asegurar la tuya, escribí *ALIAS* y te paso los datos "
            "para transferir. 👇"
        ),
        # Este producto se entrega A MANO (usuario/contraseña por WhatsApp),
        # no tiene link de Drive ni carpeta. "entrega_manual" le avisa al
        # motor (bot.py) que, al aprobar el pago, mande el mensaje de abajo
        # en vez de buscar un link_carpeta_final.
        "entrega_manual": True,
        "mensaje_entrega_manual": (
            "✅ *¡Pago confirmado!* Estamos activando tu cuenta de Gemini AI Pro. "
            "En breve (dentro de las próximas horas) te vamos a enviar tu usuario "
            "y contraseña acá mismo. ¡Gracias por tu compra! 🙌"
        ),
        # Este producto no tiene "manuales" (archivos PDF), así que en vez
        # de forzarlo en ese formato, usa su propia lista de beneficios.
        "que_incluye": [
            "Modelo Gemini más avanzado, con límites de uso ampliados y una ventana de contexto de hasta 1 millón de tokens",
            "Herramientas de investigación profunda (Deep Research) para analizar temas complejos en detalle",
            "Agente de programación Jules, para asistencia en tareas de código",
            "Generación de video con inteligencia artificial",
            "Integración directa dentro de Gmail, Documentos, Presentaciones y Vids de Google Workspace",
            "Hasta 5 TB de almacenamiento en Google One, compartido entre Drive, Gmail y Google Fotos",
        ],
        "emoji_ficha": "🤖",
        "manuales": [],  # se deja vacío: este producto no usa manuales/PDFs
    },
    "mega_pack_medicina": {
        "titulo": "Mega Pack Medicina",
        "descripcion_corta": "Anatomía, farmacología, +20 manuales y más",
        "precio": "$14.999",
        "precio_oferta": "$14.999",
        "precio_valor": 14999,
        "imagen": "https://i.ibb.co/Vpr3Wm2W/1.jpg",
        # Galería de 10 capturas reales del contenido, se mandan todas en
        # secuencia en la ficha (en vez de una sola imagen de portada).
        "galeria": [
            "https://i.ibb.co/Vpr3Wm2W/1.jpg",
            "https://i.ibb.co/8gNS081J/2.jpg",
            "https://i.ibb.co/5hCHKfnN/3.jpg",
            "https://i.ibb.co/d4VJL1j4/4.jpg",
            "https://i.ibb.co/mFgpHswY/5.jpg",
            "https://i.ibb.co/MTB6n1s/6.jpg",
            "https://i.ibb.co/CSr0Nm4/7.jpg",
            "https://i.ibb.co/rNhCGgy/8.jpg",
            "https://i.ibb.co/FbhtbvfP/9.jpg",
            "https://i.ibb.co/21mVNZBG/11.jpg",
        ],
        # Carpeta con todo el contenido (esquemas, libros, atlas, flashcards).
        # Se manda este link único cuando se confirma el pago.
        "link_carpeta_final": "https://drive.google.com/drive/folders/1tXkVWZ4Z6sMYf0QFBKBVOlfZ0AuVNJZd?usp=sharing",
        "que_incluye": [
            "Más de 1.100 esquemas ilustrados de las principales áreas médicas",
            "Más de 1.000 libros de medicina en PDF",
            "Atlas médicos ilustrados y manuales prácticos",
            "Resúmenes clínicos organizados por sistemas",
            "Guías farmacológicas por área y sketches premium",
            "Flashcards interactivas para repasar rápido",
            "Contenido base: Anatomía, Bioquímica, Cirugía, Farmacología y Fisiología",
            "20 manuales completos: Cardiología, Cirugía General, Dermatología, "
            "Endocrinología, Gastroenterología, Geriatría, Ginecología y Obstetricia, "
            "Hematología, Infectología, Manejo Avanzado en Trauma, Nefrología, "
            "Neumología y Cirugía Torácica, Neurología, Oftalmología, "
            "Otorrinolaringología, Pediatría, Psiquiatría, Reumatología, "
            "Traumatología y Ortopedia, y Urología",
        ],
        "emoji_ficha": "⚕️",
        "manuales": [],  # se deja vacío: este producto usa "que_incluye" en vez de manuales con preview
    },
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
    "manifestacion_33_dias": [
        "33 dias",
        "manifestacion",
        "manual de creacion",
        "manual para la creacion",
        "pack manifestacion",
        "imaginaria",
        "realifestacion",
    ],
    "cuenta_gemini_ai_pro": [
        "gemini",
        "gemini ai pro",
        "cuenta gemini",
        "gemini pro",
        "ai pro",
    ],
    "mega_pack_medicina": [
        "medicina",
        "mega pack medicina",
        "kit de medicina",
        "kit medicina",
        "anatomia",
        "manuales de medicina",
        "medicina digital",
    ],
}
