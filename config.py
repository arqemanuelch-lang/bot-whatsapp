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
    "productos digitales. Hoy vende: el Kit Maestro de Arquitectura y "
    "Construcción (7 manuales técnicos en PDF, $6.000) y el Pack Retro Games (juegos clásicos para el celular, $3.000). "
    "Respondé breve, claro y amable en español. Si el cliente pregunta por algo que no "
    "sea uno de esos dos productos, decile que por ahora solo están esos dos. "
    "Orientalo a escribir el nombre del producto (*kit maestro* o *retro games*) para que el sistema le muestre la ficha completa."
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
        "descripcion_corta": "7 manuales técnicos en PDF",
        "precio": "$6.000",
        "precio_oferta": "$6.000",
        "precio_valor": 6000,  # el mismo precio, pero como número (lo necesita Mercado Pago)
        "link_pago": "https://mpago.la/17uyqFK",
        "imagen": "https://i.ibb.co/zTd7PcQJ/a722ab83-e521-4fef-b680-54e6a8b847b7.png",
        "imagen_oferta": "https://i.ibb.co/zTd7PcQJ/a722ab83-e521-4fef-b680-54e6a8b847b7.png",
        # Carpeta de Google Drive con TODOS los manuales completos. Se manda
        # este único link cuando se confirma el pago (en vez de los links
        # individuales de cada manual, que son solo para "ver adelanto").
        "link_carpeta_final": "https://drive.google.com/drive/folders/1YwPEiA5UWOl60GIg_8YYxxVpWaaO6MSw?usp=sharing",
        "manuales": [
            {"titulo": "Cómo se proyecta una Vivienda", "autor": "J.L. Moia",
             "link": "https://drive.google.com/file/d/114PXZLc-QRsfuEF3eSVSMlWEq_ICbJgQ/view?usp=sharing"},
            {"titulo": "Manual de Instalaciones Hidráulicas, Sanitarias, Aire, Gas y Vapor", "autor": "Ing. Sergio Zepeda C.",
             "link": "https://drive.google.com/file/d/1ooDTnZyEAWwz_SeKjRxgps9N7FhwWiPS/view?usp=sharing"},
            {"titulo": "Método práctico para la elaboración de presupuestos de construcción", "autor": "Arq. William García",
             "link": "https://drive.google.com/file/d/1kfJe0vmQtXBl3p_mJ39kkU0GU-OwUDst/view?usp=sharing"},
            {"titulo": "Manual de Autoconstrucción", "autor": "Carlos Rodríguez",
             "link": "https://drive.google.com/file/d/1sbUe7XD2FRM5A-f2I6opXDoMF9y2gO1Q/view?usp=sharing"},
            {"titulo": "Manual del Arquitecto Descalzo", "autor": "Johan van Lengen",
             "link": "https://drive.google.com/file/d/1MhPK80rcTAnvZwbo2wv1wXAyxsrAgTFb/view?usp=sharing"},
            {"titulo": "Curso Básico de Instalaciones Eléctricas", "autor": "Juan Carlos Calloni",
             "link": "https://drive.google.com/file/d/1ETqTBa_nxWLigyHmQY8mvoeqqS49AIH3/view?usp=sharing"},
            {"titulo": "Instalaciones Sanitarias", "autor": "Jorge Ortíz",
             "link": "https://drive.google.com/file/d/1rd-tAxh3Qk8wcp-6TlFmzpjwzs25SEdA/view?usp=sharing"},
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
    "kit_maestro": {
        "hasta": "2026-10-22",          # formato AAAA-MM-DD, vale hasta las 23:59
        "precio": "$5.500",
        "precio_valor": 5500,
        "precio_normal": "$6.000",      # se muestra tachado como referencia
        "regalo": "Un plus sorpresa que descubrís al recibir tu pack",
        "aviso": "⏰ Promo válida solo hoy",
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
}
