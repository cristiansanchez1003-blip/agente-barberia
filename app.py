import os
import json
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
import google.generativeai as genai
from google.generativeai import types
from dotenv import load_dotenv

# Cargar variables de entorno de Espíritu Digital
load_dotenv()

app = Flask(__name__)
CORS(app)  # Evita bloqueos de origen cuando enlaces el frontend de Vercel
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configurar credenciales desde variables de entorno para produccion en Render.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DATABASE_URL")
VOICE_API_URL = os.getenv("VOICE_API_URL")
VOICE_API_KEY = os.getenv("VOICE_API_KEY")
VOICE_ASSISTANT_ID = os.getenv("VOICE_ASSISTANT_ID")
CHILE_TZ = ZoneInfo("America/Santiago")
ESTADOS_CITA_VALIDOS = {"pendiente", "llamando", "confirmada", "cancelada", "finalizada", "no-contesta"}

def get_db_connection():
    """Establece una conexión limpia con Supabase (PostgreSQL)"""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL o SUPABASE_DATABASE_URL no esta configurada.")
    return psycopg2.connect(DATABASE_URL)

def es_confirmacion_asistencia(texto: str) -> bool:
    """Detecta respuestas cortas de confirmacion de asistencia."""
    limpio = texto.strip().lower().replace("í", "i")
    confirmaciones = {"si", "si voy", "si, voy", "confirmo", "voy", "alli estare", "ahi estare"}
    return limpio in confirmaciones or limpio.startswith("si voy")

def extraer_telefono_desde_historial(historial: list) -> str | None:
    """Busca el ultimo telefono chileno mencionado en la conversacion."""
    patron = re.compile(r"(?:\\+?56)?\\s*9\\s*\\d{4}\\s*\\d{4}")
    for msg in reversed(historial):
        contenido = str(msg.get("content", ""))
        coincidencias = patron.findall(contenido)
        if coincidencias:
            telefono = re.sub(r"\\s+", "", coincidencias[-1])
            if not telefono.startswith("+"):
                telefono = "+56" + telefono[-9:]
            return telefono
    return None

# ==========================================
# 🛠️ SKILLS / HERRAMIENTAS (NATIVAS EN PYTHON)
# ==========================================

def verificar_disponibilidad(fecha: str, barbero_id: int) -> dict:
    """
    Consulta las horas libres de un barbero para una fecha específica.
    Usa esta función cuando el cliente pregunte qué horas hay disponibles o si un barbero tiene espacio un día.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Consultar citas existentes para ese barbero y fecha en Supabase
        cur.execute(
            "SELECT hora FROM citas WHERE fecha = %s AND barbero_id = %s AND estado IN ('pendiente', 'llamando', 'confirmada', 'no-contesta')",
            (fecha, barbero_id)
        )
        citas_ocupadas = [str(r['hora'])[:5] for r in cur.fetchall()]
        
        # Bloques horarios estándar (10:00 a 19:00 hrs de 45 min)
        bloques_totales = ["10:00", "10:45", "11:30", "12:15", "13:00", "14:30", "15:15", "16:00", "16:45", "17:30", "18:15", "19:00"]
        bloques_libres = [b for b in bloques_totales if b not in citas_ocupadas]
        
        cur.close()
        conn.close()
        return {"fecha": fecha, "horas_disponibles": bloques_libres}
    except Exception as e:
        return {"error": str(e)}

def crear_reserva(nombre: str, telefono: str, barbero_id: int, servicio_id: int, fecha: str, hora: str) -> dict:
    """
    Registra una nueva cita en el sistema y le suma un sello de fidelidad automático al cliente.
    Usa esta función únicamente cuando el usuario confirme explícitamente que desea agendar la cita y tengas todos sus datos.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Insertar la Cita en la tabla correspondiente
        cur.execute(
            "INSERT INTO citas (cliente_nombre, cliente_telefono, barbero_id, servicio_id, fecha, hora, estado) VALUES (%s, %s, %s, %s, %s, %s, 'pendiente') RETURNING id",
            (nombre, telefono, barbero_id, servicio_id, fecha, hora)
        )
        cita_id = cur.fetchone()[0]
        
        # 2. Gestionar la tarjeta de fidelidad (Suma +1 sello, si llega a 5 se reinicia a 1)
        cur.execute(
            "INSERT INTO fidelidad (cliente_telefono, sellos_acumulados) VALUES (%s, 1) "
            "ON CONFLICT (cliente_telefono) DO UPDATE SET "
            "sellos_acumulados = CASE WHEN fidelidad.sellos_acumulados >= 5 THEN 1 ELSE fidelidad.sellos_acumulados + 1 END, "
            "actualizado_el = NOW() RETURNING sellos_acumulados",
            (telefono,)
        )
        sellos_actuales = cur.fetchone()[0]
        
        conn.commit()
        cur.close()
        conn.close()
        
        resultado = {
            "status": "success",
            "cita_id": cita_id,
            "estado": "pendiente",
            "sellos_totales": sellos_actuales,
            "mensaje": "Cita registrada con éxito en el sistema."
        }
        if sellos_actuales == 5:
            resultado["alerta_premio"] = "¡Espectacular! El cliente completó su 5to sello. Su próximo corte es totalmente gratis."
            
        return resultado
    except Exception as e:
        return {"error": str(e)}

def consultar_sellos(telefono: str) -> dict:
    """
    Revisa la cantidad de sellos acumulados en el club de fidelidad asociados a un número de teléfono.
    Usa esta función cuando el cliente te pida revisar sus puntos, sellos, visitas o estado de membresía.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT sellos_acumulados FROM fidelidad WHERE cliente_telefono = %s", (telefono,))
        resultado = cur.fetchone()
        cur.close()
        conn.close()
        
        if resultado:
            return {"telefono": telefono, "sellos": resultado['sellos_acumulados']}
        return {"telefono": telefono, "sellos": 0, "nota": "Cliente nuevo, no registra visitas previas."}
    except Exception as e:
        return {"error": str(e)}

def cambiar_estado_cita(cita_id: int, nuevo_estado: str) -> dict:
    """
    Cambia el estado de una cita existente.
    Usa esta funcion cuando el cliente confirme asistencia, cancele o cuando el equipo necesite actualizar el flujo operativo.
    """
    estado_normalizado = str(nuevo_estado).strip().lower()
    if estado_normalizado not in ESTADOS_CITA_VALIDOS:
        return {
            "error": "Estado invalido.",
            "estados_validos": sorted(ESTADOS_CITA_VALIDOS)
        }

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "UPDATE citas SET estado = %s WHERE id = %s RETURNING id, cliente_nombre, cliente_telefono, fecha, hora, estado",
            (estado_normalizado, cita_id)
        )
        cita = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        if not cita:
            return {"error": "No se encontro una cita con ese ID."}

        return {
            "status": "success",
            "cita": dict(cita),
            "mensaje": f"Cita {cita_id} actualizada a {estado_normalizado}."
        }
    except Exception as e:
        return {"error": str(e)}

def confirmar_ultima_cita_pendiente(telefono: str) -> dict:
    """
    Confirma automaticamente la cita pendiente mas proxima de un cliente por telefono.
    Usa esta funcion cuando el cliente responda afirmativamente que asistira, por ejemplo: 'si, voy'.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT id
            FROM citas
            WHERE cliente_telefono = %s
              AND estado = 'pendiente'
            ORDER BY fecha ASC, hora ASC, creado_el DESC
            LIMIT 1
            """,
            (telefono,)
        )
        cita = cur.fetchone()
        cur.close()
        conn.close()

        if not cita:
            return {"error": "No encontre citas pendientes para ese telefono."}

        return cambiar_estado_cita(cita["id"], "confirmada")
    except Exception as e:
        return {"error": str(e)}

def enviar_recordatorio_simulado(telefono: str, nombre_cliente: str, hora: str) -> str:
    """
    Simula el disparo de un recordatorio por WhatsApp para una cita pendiente.
    Usa esta funcion despues de crear una reserva pendiente o cuando se necesite recordar la asistencia al cliente.
    """
    return f"WhatsApp simulado enviado a {telefono}: Hola {nombre_cliente}, te recordamos tu cita en Standard Barber a las {hora}. Responde 'si, voy' para confirmarla."

# ==========================================
# OUTBOUND VOICE HELPERS
# ==========================================

def obtener_citas_pendientes_para_llamar() -> list[dict]:
    """Busca citas pendientes de hoy en Chile entre 90 y 120 minutos desde ahora."""
    ahora_chile = datetime.now(CHILE_TZ)
    inicio_ventana = ahora_chile.replace(second=0, microsecond=0)
    inicio_ventana = inicio_ventana + timedelta(minutes=90)
    fin_ventana = ahora_chile.replace(second=0, microsecond=0) + timedelta(minutes=120)

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        SELECT
            c.id,
            c.cliente_nombre,
            c.cliente_telefono,
            c.fecha,
            c.hora,
            c.barbero_id,
            c.servicio_id,
            b.nombre AS barbero_nombre,
            s.nombre AS servicio_nombre
        FROM citas c
        LEFT JOIN barberos b ON b.id = c.barbero_id
        LEFT JOIN servicios s ON s.id = c.servicio_id
        WHERE c.estado = 'pendiente'
          AND c.fecha = %s
          AND c.hora >= %s
          AND c.hora <= %s
        ORDER BY c.hora ASC
        """,
        (ahora_chile.date(), inicio_ventana.time(), fin_ventana.time())
    )
    citas = [dict(row) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return citas

def crear_payload_llamada(cita: dict) -> dict:
    """Construye el payload outbound compatible con plataformas de voz."""
    nombre_cliente = cita.get("cliente_nombre") or "cliente"
    nombre_barbero = cita.get("barbero_nombre") or "tu barbero"
    hora_hablada = hora_a_voz(str(cita.get("hora")))

    return {
        "phoneNumber": cita.get("cliente_telefono"),
        "assistantId": VOICE_ASSISTANT_ID,
        "customer": {"name": nombre_cliente},
        "squad": {
            "metadata": {"cita_id": cita.get("id")}
        },
        "assistantOverrides": {
            "firstMessage": (
                f"Hola {nombre_cliente}, te llamo de Standard Barber para confirmar tu cita "
                f"de hoy {hora_hablada} con {nombre_barbero}. ¿Asistes a tu turno?"
            )
        }
    }

def iniciar_llamada_outbound(cita: dict) -> dict:
    """Dispara una llamada outbound contra la API de voz configurada."""
    if not VOICE_API_URL or not VOICE_API_KEY or not VOICE_ASSISTANT_ID:
        raise RuntimeError("Faltan VOICE_API_URL, VOICE_API_KEY o VOICE_ASSISTANT_ID en el entorno.")

    headers = {
        "Authorization": f"Bearer {VOICE_API_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.post(
        VOICE_API_URL,
        headers=headers,
        json=crear_payload_llamada(cita),
        timeout=20
    )
    response.raise_for_status()
    try:
        return response.json()
    except ValueError:
        return {"status_code": response.status_code, "text": response.text}

def buscar_valor_recursivo(payload, nombres: set[str]):
    """Busca una clave dentro de dict/list anidados sin acoplarse a un proveedor de voz."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in nombres and value not in (None, ""):
                return value
            encontrado = buscar_valor_recursivo(value, nombres)
            if encontrado not in (None, ""):
                return encontrado
    elif isinstance(payload, list):
        for item in payload:
            encontrado = buscar_valor_recursivo(item, nombres)
            if encontrado not in (None, ""):
                return encontrado
    return None

def recolectar_textos_recursivo(payload) -> list[str]:
    """Recolecta valores de texto de un payload anidado para interpretar callbacks flexibles."""
    textos = []
    if isinstance(payload, dict):
        for value in payload.values():
            textos.extend(recolectar_textos_recursivo(value))
    elif isinstance(payload, list):
        for item in payload:
            textos.extend(recolectar_textos_recursivo(item))
    elif isinstance(payload, (str, int, float, bool)):
        textos.append(str(payload))
    return textos

def extraer_cita_id_callback(payload: dict) -> int | None:
    """Extrae cita_id desde metadata, squad metadata o analysis."""
    valor = buscar_valor_recursivo(payload, {"cita_id", "citaId", "appointment_id", "appointmentId"})
    try:
        return int(valor) if valor is not None else None
    except (TypeError, ValueError):
        return None

def extraer_resolucion_callback(payload: dict) -> str:
    """Normaliza la resolucion final de una llamada outbound."""
    valor = buscar_valor_recursivo(payload, {
        "customerResponse",
        "resolution",
        "resultado",
        "estado",
        "status",
        "callStatus",
        "endedReason"
    })
    textos = [str(valor or "")] + recolectar_textos_recursivo(payload.get("analysis", {})) + recolectar_textos_recursivo(payload.get("structuredOutputs", {}))
    texto = " ".join(textos).strip().lower()
    texto = texto.replace("ó", "o").replace("í", "i").replace("á", "a").replace("é", "e").replace("ú", "u")

    if any(palabra in texto for palabra in ["confirmado", "confirma", "confirmed", "si voy", "asiste"]):
        return "confirmada"
    if any(palabra in texto for palabra in ["cancelado", "cancela", "cancelled", "no voy", "rechaza"]):
        return "cancelada"
    if any(palabra in texto for palabra in ["no-answer", "no_answer", "no contesta", "busy", "ocupado", "voicemail", "failed"]):
        return "no-contesta"
    return "no-contesta"

# ==========================================
# VOICE / TTS HELPERS
# ==========================================

NUMEROS_VOZ = {
    0: "cero", 1: "uno", 2: "dos", 3: "tres", 4: "cuatro", 5: "cinco",
    6: "seis", 7: "siete", 8: "ocho", 9: "nueve", 10: "diez",
    11: "once", 12: "doce", 13: "trece", 14: "catorce", 15: "quince",
    16: "dieciseis", 17: "diecisiete", 18: "dieciocho", 19: "diecinueve",
    20: "veinte", 21: "veintiuno", 22: "veintidos", 23: "veintitres",
    24: "veinticuatro", 25: "veinticinco", 26: "veintiseis", 27: "veintisiete",
    28: "veintiocho", 29: "veintinueve", 30: "treinta"
}
DECENAS_VOZ = {
    40: "cuarenta", 50: "cincuenta", 60: "sesenta", 70: "setenta",
    80: "ochenta", 90: "noventa"
}
DIAS_VOZ = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
MESES_VOZ = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
]

def numero_a_voz(numero: int) -> str:
    """Convierte numeros pequenos a texto natural para TTS."""
    numero = int(numero)
    if numero in NUMEROS_VOZ:
        return NUMEROS_VOZ[numero]
    if numero < 100:
        decena = (numero // 10) * 10
        unidad = numero % 10
        return DECENAS_VOZ[decena] if unidad == 0 else f"{DECENAS_VOZ[decena]} y {NUMEROS_VOZ[unidad]}"
    if numero < 1000:
        centenas = {
            100: "cien", 200: "doscientos", 300: "trescientos", 400: "cuatrocientos",
            500: "quinientos", 600: "seiscientos", 700: "setecientos",
            800: "ochocientos", 900: "novecientos"
        }
        base = (numero // 100) * 100
        resto = numero % 100
        if numero == 100:
            return "cien"
        prefijo = "ciento" if base == 100 else centenas[base]
        return prefijo if resto == 0 else f"{prefijo} {numero_a_voz(resto)}"
    if numero < 1000000:
        miles = numero // 1000
        resto = numero % 1000
        prefijo = "mil" if miles == 1 else f"{numero_a_voz(miles)} mil"
        return prefijo if resto == 0 else f"{prefijo} {numero_a_voz(resto)}"
    return str(numero)

def precio_a_voz(precio: int | str | None) -> str:
    """Formatea precios como 'dieciocho mil pesos'."""
    if precio is None:
        return ""
    digitos = re.sub(r"\D", "", str(precio))
    if not digitos:
        return ""
    return f"{numero_a_voz(int(digitos))} pesos"

def fecha_a_voz(valor_fecha: str | date) -> str:
    """Formatea fechas ISO como 'domingo diecisiete de mayo'."""
    if isinstance(valor_fecha, datetime):
        fecha = valor_fecha.date()
    elif isinstance(valor_fecha, date):
        fecha = valor_fecha
    else:
        fecha = datetime.strptime(str(valor_fecha), "%Y-%m-%d").date()
    return f"{DIAS_VOZ[fecha.weekday()]} {numero_a_voz(fecha.day)} de {MESES_VOZ[fecha.month - 1]}"

def hora_a_voz(valor_hora: str) -> str:
    """Formatea horas para lectura fluida por voz."""
    hora_texto = str(valor_hora)[:5]
    horas, minutos = [int(parte) for parte in hora_texto.split(":")]
    if minutos == 0:
        periodo = "de la manana" if horas < 12 else "horas"
        return f"a las {numero_a_voz(horas)} {periodo}"
    if minutos == 30:
        return f"a las {numero_a_voz(horas)} y media"
    return f"a las {numero_a_voz(horas)} {numero_a_voz(minutos)}"

def lista_horas_a_voz(horas: list[str]) -> str:
    """Une bloques horarios con pausas naturales."""
    if not horas:
        return "no veo horas disponibles en ese dia"
    horas_formateadas = [hora_a_voz(hora) for hora in horas]
    if len(horas_formateadas) == 1:
        return horas_formateadas[0]
    return ", ".join(horas_formateadas[:-1]) + f", o {horas_formateadas[-1]}"

def normalizar_argumentos_tool(argumentos):
    """Acepta arguments como dict o como string JSON."""
    if argumentos is None:
        return {}
    if isinstance(argumentos, dict):
        return argumentos
    if isinstance(argumentos, str):
        try:
            return json.loads(argumentos)
        except json.JSONDecodeError:
            return {}
    return {}

def obtener_nombre_barbero(barbero_id: int) -> str:
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT nombre FROM barberos WHERE id = %s", (barbero_id,))
        barbero = cur.fetchone()
        cur.close()
        conn.close()
        return barbero["nombre"] if barbero else "tu barbero"
    except Exception:
        return "tu barbero"

def obtener_servicio_voz(servicio_id: int) -> str:
    """Devuelve nombre y precio del servicio en formato hablado."""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT nombre, precio FROM servicios WHERE id = %s", (servicio_id,))
        servicio = cur.fetchone()
        cur.close()
        conn.close()
        if not servicio:
            return ""
        precio_hablado = precio_a_voz(servicio.get("precio"))
        if precio_hablado:
            return f"Tu servicio es {servicio['nombre']}, por {precio_hablado}."
        return f"Tu servicio es {servicio['nombre']}."
    except Exception:
        return ""

def respuesta_voz_disponibilidad(argumentos: dict) -> str:
    resultado = verificar_disponibilidad(
        fecha=str(argumentos.get("fecha")),
        barbero_id=int(argumentos.get("barbero_id"))
    )
    if resultado.get("error"):
        return "Hubo un pequeno inconveniente al consultar la agenda, por favor indicame otra hora."
    fecha_hablada = fecha_a_voz(resultado["fecha"])
    horas_habladas = lista_horas_a_voz(resultado.get("horas_disponibles", []))
    nombre_barbero = obtener_nombre_barbero(int(argumentos.get("barbero_id")))
    return f"Para {nombre_barbero}, el {fecha_hablada}, tengo disponible {horas_habladas}."

def respuesta_voz_crear_reserva(argumentos: dict) -> str:
    resultado = crear_reserva(
        nombre=str(argumentos.get("nombre") or argumentos.get("cliente_nombre") or "").strip(),
        telefono=str(argumentos.get("telefono") or argumentos.get("cliente_telefono") or "").strip(),
        barbero_id=int(argumentos.get("barbero_id")),
        servicio_id=int(argumentos.get("servicio_id")),
        fecha=str(argumentos.get("fecha")),
        hora=str(argumentos.get("hora"))
    )
    if resultado.get("error"):
        return "Hubo un pequeno inconveniente al guardar la cita, por favor indicame otra hora."

    nombre_cliente = str(argumentos.get("nombre") or argumentos.get("cliente_nombre") or "").strip() or "listo"
    nombre_barbero = obtener_nombre_barbero(int(argumentos.get("barbero_id")))
    servicio_hablado = obtener_servicio_voz(int(argumentos.get("servicio_id")))
    fecha_hablada = fecha_a_voz(str(argumentos.get("fecha")))
    hora_hablada = hora_a_voz(str(argumentos.get("hora")))
    sellos = int(resultado.get("sellos_totales") or 0)
    return (
        f"Perfecto {nombre_cliente}, tu cita con {nombre_barbero} quedo agendada para "
        f"{fecha_hablada}, {hora_hablada}. {servicio_hablado} Te acabo de sumar un sello a tu tarjeta digital. "
        f"Ahora tienes {numero_a_voz(sellos)} de cinco sellos."
    )

def respuesta_voz_consultar_sellos(argumentos: dict) -> str:
    telefono = str(argumentos.get("telefono") or argumentos.get("cliente_telefono") or "").strip()
    resultado = consultar_sellos(telefono)
    if resultado.get("error"):
        return "Hubo un pequeno inconveniente al consultar tu tarjeta digital. Lo revisamos nuevamente en un momento."
    sellos = int(resultado.get("sellos") or 0)
    restantes = max(0, 5 - sellos)
    if restantes == 0:
        return "Registro que ya tienes cinco de cinco sellos acumulados. Tu proximo corte puede ser gratis."
    return (
        f"Registro que tienes {numero_a_voz(sellos)} de cinco sellos acumulados. "
        f"Estas a solo {numero_a_voz(restantes)} visitas de tu corte gratis."
    )

VOICE_TOOL_HANDLERS = {
    "verificar_disponibilidad": respuesta_voz_disponibilidad,
    "crear_reserva": respuesta_voz_crear_reserva,
    "consultar_sellos": respuesta_voz_consultar_sellos
}

# Diccionario utilitario para ejecutar las funciones según el llamado de Gemini
DICTIONARY_FUNCTIONS = {
    "verificar_disponibilidad": verificar_disponibilidad,
    "crear_reserva": crear_reserva,
    "consultar_sellos": consultar_sellos,
    "cambiar_estado_cita": cambiar_estado_cita,
    "confirmar_ultima_cita_pendiente": confirmar_ultima_cita_pendiente,
    "enviar_recordatorio_simulado": enviar_recordatorio_simulado
}

# ==========================================
# 🤖 CONFIGURACIÓN DEL MODELO DE GOOGLE
# ==========================================

model = genai.GenerativeModel(
    model_name='gemini-3.1-flash',  # Motor robusto con soporte nativo de Function Calling
    tools=[verificar_disponibilidad, crear_reserva, consultar_sellos],  # Inyección de las habilidades
    system_instruction=(
        "Eres Robot.ia, el concierge inteligente y exclusivo de Standard Barber, una aplicación diseñada por Espíritu Digital. "
        "Tu tono es pulcro, sumamente profesional pero con una calidez chilena muy elegante (puedes usar palabras como '¿te tinca?', 'al tiro' con moderación). "
        "Tu misión principal es ayudar al usuario a agendar citas y revisar su club de fidelidad. "
        "REGLA ESTRICTA DE OPERACIÓN: Si un cliente quiere agendar, debes recopilar obligatoriamente estos 5 datos: Nombre, Teléfono (con formato +569), Servicio deseado, Barbero preferido y Fecha. "
        "Para barbero_id usa: 1 para Mateo Silva y 2 para Carlos Vega. "
        "Para servicio_id usa: 1 para Corte Premium ($12.000), 2 para Perfilado de Barba ($8.000) y 3 para Combo Espíritu Real ($18.000). "
        "Si te falta información para ejecutar una herramienta, pídela amablemente. Jamás inventes horarios disponibles ni confirmes citas ficticias."
    )
)

# Reconfigura Robot.ia con las tools operativas de citas, estados y recordatorios.
model = genai.GenerativeModel(
    model_name='gemini-3.1-flash',
    tools=[
        verificar_disponibilidad,
        crear_reserva,
        consultar_sellos,
        cambiar_estado_cita,
        confirmar_ultima_cita_pendiente,
        enviar_recordatorio_simulado
    ],
    system_instruction=(
        "Eres Robot.ia, el concierge inteligente y exclusivo de Standard Barber, una aplicacion disenada por Espiritu Digital. "
        "Tu tono es pulcro, profesional y calido. Tu mision es ayudar a agendar citas, revisar fidelidad y confirmar asistencia. "
        "Si un cliente quiere agendar, debes recopilar obligatoriamente: Nombre, Telefono con formato +569, Servicio deseado, Barbero preferido, Fecha y Hora. "
        "Para barbero_id usa: 1 para Mateo Silva y 2 para Carlos Vega. "
        "Para servicio_id usa: 1 para Corte Premium ($12.000), 2 para Perfilado de Barba ($8.000) y 3 para Combo Espiritu Real ($18.000). "
        "Cuando agendes con crear_reserva, la cita siempre queda en estado 'pendiente'. Despues de crearla, usa enviar_recordatorio_simulado con telefono, nombre_cliente y hora para simular el WhatsApp de confirmacion. "
        "Si el cliente responde 'si, voy', 'sí, voy', 'confirmo', 'voy' o una afirmacion equivalente, confirma automaticamente su cita pendiente en Supabase usando confirmar_ultima_cita_pendiente si tienes el telefono; si solo tienes cita_id, usa cambiar_estado_cita con nuevo_estado='confirmada'. "
        "Si te falta informacion para ejecutar una herramienta, pidela amablemente. Jamas inventes horarios disponibles ni confirmes citas ficticias."
    )
)

# ==========================================
# 🚀 ENDPOINTS API REST
# ==========================================

@app.route('/', methods=['GET'])
def frontend_index():
    """Sirve la SPA principal junto al backend Flask."""
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/healthz', methods=['GET'])
def healthcheck():
    """Health check liviano para Render."""
    return jsonify({
        "status": "ok",
        "service": "standard-barber-robotia"
    }), 200

@app.route('/assets/<path:filename>', methods=['GET'])
def frontend_assets(filename):
    """Sirve assets locales del frontend, incluido el logotipo de Espiritu Digital."""
    return send_from_directory(os.path.join(BASE_DIR, 'assets'), filename)

@app.route('/api/citas/cambiar_estado', methods=['POST'])
def api_cambiar_estado_cita():
    """Cambia el estado operativo de una cita en Supabase."""
    datos = request.get_json(silent=True) or {}
    cita_id = datos.get('cita_id')
    nuevo_estado = datos.get('nuevo_estado') or datos.get('estado')

    if not cita_id or not nuevo_estado:
        return jsonify({
            "status": "error",
            "message": "Debes enviar cita_id y nuevo_estado."
        }), 400

    try:
        cita_id = int(cita_id)
    except (TypeError, ValueError):
        return jsonify({
            "status": "error",
            "message": "cita_id debe ser numerico."
        }), 400

    resultado = cambiar_estado_cita(cita_id, nuevo_estado)
    if resultado.get("error"):
        return jsonify({"status": "error", "message": resultado["error"], "details": resultado}), 400

    return jsonify(resultado)

@app.route('/api/citas', methods=['POST'])
def api_crear_cita():
    """Crea una cita pendiente desde el formulario visual y dispara el recordatorio simulado."""
    datos = request.get_json(silent=True) or {}
    campos_requeridos = ["nombre", "telefono", "barbero_id", "servicio_id", "fecha", "hora"]
    faltantes = [campo for campo in campos_requeridos if not datos.get(campo)]

    if faltantes:
        return jsonify({
            "status": "error",
            "message": "Faltan datos obligatorios.",
            "missing": faltantes
        }), 400

    try:
        resultado = crear_reserva(
            nombre=str(datos["nombre"]).strip(),
            telefono=str(datos["telefono"]).strip(),
            barbero_id=int(datos["barbero_id"]),
            servicio_id=int(datos["servicio_id"]),
            fecha=str(datos["fecha"]).strip(),
            hora=str(datos["hora"]).strip()
        )
    except (TypeError, ValueError):
        return jsonify({
            "status": "error",
            "message": "barbero_id y servicio_id deben ser numericos."
        }), 400

    if resultado.get("error"):
        return jsonify({
            "status": "error",
            "message": resultado["error"]
        }), 500

    recordatorio = enviar_recordatorio_simulado(
        telefono=str(datos["telefono"]).strip(),
        nombre_cliente=str(datos["nombre"]).strip(),
        hora=str(datos["hora"]).strip()
    )

    return jsonify({
        "status": "success",
        "cita_id": resultado["cita_id"],
        "estado": resultado.get("estado", "pendiente"),
        "sellos_totales": resultado.get("sellos_totales", 0),
        "recordatorio": recordatorio,
        "message": "Cita pendiente creada correctamente."
    })

@app.route('/api/voice/tools', methods=['POST'])
def api_voice_tools():
    """
    Webhook sincrono para plataformas de voz tipo Vapi o Retell.
    Recibe toolCalls, ejecuta Supabase y devuelve texto natural optimizado para TTS.
    """
    fallback_voz = "Hubo un pequeno inconveniente al consultar la agenda, por favor indicame otra hora."

    try:
        payload = request.get_json(silent=True) or {}
        tool_calls = payload.get("message", {}).get("toolCalls", [])

        if not tool_calls:
            return jsonify({
                "results": [
                    {
                        "toolCallId": "sin_tool_call",
                        "result": "No recibi una herramienta valida para ejecutar. Puedes repetir la solicitud, por favor."
                    }
                ]
            }), 200

        results = []
        for tool_call in tool_calls:
            tool_call_id = tool_call.get("id") or "sin_id"
            tool_name = tool_call.get("name") or tool_call.get("function", {}).get("name")
            argumentos = normalizar_argumentos_tool(
                tool_call.get("arguments") or tool_call.get("function", {}).get("arguments")
            )

            try:
                handler = VOICE_TOOL_HANDLERS.get(tool_name)
                if not handler:
                    texto = "Esa accion todavia no esta disponible por telefono. Puedo ayudarte con disponibilidad, reservas o sellos."
                else:
                    texto = handler(argumentos)
            except Exception as exc:
                app.logger.exception("Error procesando voice tool %s: %s", tool_name, exc)
                texto = fallback_voz

            results.append({
                "toolCallId": tool_call_id,
                "result": texto
            })

        return jsonify({"results": results}), 200

    except Exception as exc:
        app.logger.exception("Error general en /api/voice/tools: %s", exc)
        return jsonify({
            "results": [
                {
                    "toolCallId": "error_general",
                    "result": fallback_voz
                }
            ]
        }), 200

@app.route('/api/tasks/trigger-outbound-confirmations', methods=['GET'])
def trigger_outbound_confirmations():
    """
    Endpoint para Cron externo. Busca citas pendientes en Chile entre 90 y 120 minutos
    y dispara llamadas salientes de confirmacion.
    """
    try:
        citas = obtener_citas_pendientes_para_llamar()
        resultados = []

        for cita in citas:
            cita_id = cita["id"]
            try:
                respuesta_voz = iniciar_llamada_outbound(cita)
                cambio_estado = cambiar_estado_cita(cita_id, "llamando")

                if cambio_estado.get("error"):
                    app.logger.error("No se pudo marcar cita %s como llamando: %s", cita_id, cambio_estado["error"])

                resultados.append({
                    "cita_id": cita_id,
                    "status": "llamada_iniciada",
                    "estado_actualizado": not bool(cambio_estado.get("error")),
                    "voice_response": respuesta_voz
                })
            except requests.RequestException as exc:
                app.logger.exception("Error HTTP iniciando llamada para cita %s: %s", cita_id, exc)
                resultados.append({
                    "cita_id": cita_id,
                    "status": "error_voice_api",
                    "message": str(exc)
                })
            except Exception as exc:
                app.logger.exception("Error procesando outbound para cita %s: %s", cita_id, exc)
                resultados.append({
                    "cita_id": cita_id,
                    "status": "error",
                    "message": str(exc)
                })

        return jsonify({
            "status": "success",
            "timezone": "America/Santiago",
            "processed": len(resultados),
            "results": resultados
        }), 200

    except Exception as exc:
        app.logger.exception("Error general en trigger outbound: %s", exc)
        return jsonify({
            "status": "error",
            "message": "No se pudieron procesar las confirmaciones outbound en este ciclo."
        }), 500

@app.route('/api/voice/outbound-callback', methods=['POST'])
def outbound_voice_callback():
    """
    Webhook de retorno de la plataforma de voz. Actualiza la cita segun el resultado:
    confirmada, cancelada o no-contesta.
    """
    try:
        payload = request.get_json(silent=True) or {}
        cita_id = extraer_cita_id_callback(payload)
        nuevo_estado = extraer_resolucion_callback(payload)

        if not cita_id:
            app.logger.warning("Callback outbound sin cita_id: %s", payload)
            return jsonify({
                "status": "ignored",
                "message": "Callback recibido sin cita_id."
            }), 200

        resultado = cambiar_estado_cita(cita_id, nuevo_estado)
        if resultado.get("error"):
            app.logger.error("No se pudo actualizar cita %s desde callback: %s", cita_id, resultado["error"])
            return jsonify({
                "status": "error",
                "message": resultado["error"],
                "cita_id": cita_id
            }), 200

        return jsonify({
            "status": "success",
            "cita_id": cita_id,
            "estado": nuevo_estado,
            "message": f"Cita {cita_id} actualizada a {nuevo_estado}."
        }), 200

    except Exception as exc:
        app.logger.exception("Error general en outbound callback: %s", exc)
        return jsonify({
            "status": "error",
            "message": "Callback recibido, pero no se pudo actualizar la cita."
        }), 200

@app.route('/api/chat', methods=['POST'])
def chat_bot_ia():
    """Endpoint principal que procesa la conversación e interviene las llamadas de funciones de Supabase"""
    datos = request.json
    historial_recibido = datos.get('messages', [])

    ultimo_mensaje = next((msg for msg in reversed(historial_recibido) if msg.get('role') == 'user'), None)
    if ultimo_mensaje and es_confirmacion_asistencia(str(ultimo_mensaje.get('content', ''))):
        telefono = datos.get('telefono') or extraer_telefono_desde_historial(historial_recibido)
        if not telefono:
            return jsonify({
                "status": "success",
                "response": "Perfecto. Para confirmar al tiro, dime el telefono asociado a tu cita pendiente."
            })

        resultado_confirmacion = confirmar_ultima_cita_pendiente(telefono)
        if resultado_confirmacion.get("error"):
            return jsonify({
                "status": "success",
                "response": f"Recibi tu confirmacion, pero no encontre una cita pendiente para {telefono}. Puedes enviarme el telefono o el ID de la cita y lo reviso."
            })

        cita = resultado_confirmacion["cita"]
        return jsonify({
            "status": "success",
            "response": f"Confirmado. Tu cita #{cita['id']} quedo en estado confirmada para las {str(cita['hora'])[:5]}. Te esperamos en Standard Barber."
        })
    
    # Traducir el historial del formato del frontend al formato nativo de contenidos de Gemini
    contents = []
    for msg in historial_recibido:
        # El rol del sistema se maneja de forma aislada en la inicialización del modelo
        if msg['role'] == 'system':
            continue
        # Mapear roles estándar de API
        role = 'user' if msg['role'] == 'user' else 'model'
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg['content'])]))

    try:
        # Primera llamada al modelo para determinar si requiere llamar a una función
        response = model.generate_content(contents=contents)
        
        # Bucle de control en caso de que Gemini decida usar una herramienta de base de datos
        while response.function_calls:
            # Añadir la intención del modelo al historial de contenidos
            contents.append(response.candidates[0].content)
            
            for function_call in response.function_calls:
                nombre_funcion = function_call.name
                # Extraer argumentos estructurados
                args = {k: v for k, v in function_call.args.items()}
                
                # Ejecutar la lógica de Python y Supabase
                funcion_local = DICTIONARY_FUNCTIONS[nombre_funcion]
                resultado_db = funcion_local(**args)
                
                # Crear la respuesta de la herramienta estructurada para Gemini
                part_response = types.Part.from_function_response(
                    name=nombre_funcion,
                    response={"result": resultado_db}
                )
                contents.append(types.Content(role='user', parts=[part_response]))
            
            # Re-enviar todo el bloque con los datos de Supabase integrados para que genere la respuesta final
            response = model.generate_content(contents=contents)

        return jsonify({"status": "success", "response": response.text})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Endpoints auxiliares para poblar el frontend clásico
@app.route('/api/barberos', methods=['GET'])
def listado_barberos():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM barberos")
        data = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/servicios', methods=['GET'])
def listado_servicios():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM servicios")
        data = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)), debug=os.getenv("FLASK_DEBUG") == "1")
