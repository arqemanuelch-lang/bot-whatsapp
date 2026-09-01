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


# ---------------------------------------------------------------------
# 1) DATOS GENERALES DEL NEGOCIO
# ---------------------------------------------------------------------
NOMBRE_NEGOCIO = "Droply IA"

# Palabra "comodín" que la gente puede escribir para ver el menú de
# productos si el bot no entendió su mensaje (se muestra en el aviso de
# "no entendí tu mensaje").
PALABRA_CLAVE_MENU = "DROPLY"

# Mensaje de bienvenida que se manda junto con la lista de productos,
# la primera vez que alguien saluda ("hola", "buenas", etc.)
MENSAJE_BIENVENIDA_MENU = (
    "¡Hola! 👋 Bienvenido a nuestro espacio de manuales técnicos de "
    "construcción y arquitectura. Elegí el pack que te interesa:"
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
    "Sos un asistente de ventas por WhatsApp para un negocio de manuales "
    "técnicos de construcción y arquitectura. Respondé breve, claro y "
    "amable en español, orientando siempre a que compren el Kit Maestro "
    "(escribiendo 'kit maestro')."
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
# 5) PRODUCTOS (packs) — agregá acá nuevos bloques y aparecen solos en
#    el menú del bot.
# ---------------------------------------------------------------------
PRODUCTOS = {
    "kit_maestro": {
        "titulo": "Kit Maestro de Arquitectura y Construcción",
        "descripcion_corta": "8 manuales técnicos en PDF",
        "precio": "$8.000",
        "link_pago": "https://mpago.la/17uyqFK",
        "imagen": "https://i.ibb.co/R40sSbHt/Sin-t-tulo-1080-1920-px-1080-x-1080-px-1080-x-1920-px-1080-x-1350-px-1.png",
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
    # Ejemplo de cómo se vería un segundo pack (descomentalo y completalo cuando lo tengas):
    # "kit_electricidad": {
    #     "titulo": "Kit de Electricidad Avanzada",
    #     "descripcion_corta": "5 manuales de instalaciones eléctricas",
    #     "precio": "$5.000",
    #     "link_pago": "https://mpago.la/OTRO-LINK",
    #     "imagen": "https://i.ibb.co/xxxxxxx/portada.png",
    #     "manuales": [
    #         {"titulo": "...", "autor": "...", "link": "..."},
    #     ],
    # },
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
    # Ejemplo para cuando agregues el segundo pack (descomentalo y completalo):
    # "kit_electricidad": [
    #     "electricidad",
    #     "instalaciones electricas",
    #     "kit electricidad",
    # ],
}
