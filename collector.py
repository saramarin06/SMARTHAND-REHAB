import json
import os
import time
from datetime import datetime

import requests
import serial

# =========================
# CONFIGURACION GENERAL
# =========================
PUERTO_SERIAL = "COM4"
BAUDIOS = 115200
PACIENTE = os.getenv("PACIENTE", "").strip()

# Reemplaza esta URL por la URL de produccion del Webhook de n8n Cloud.
WEBHOOK_URL = os.getenv(
    "WEBHOOK_URL",
    "https://saramaring06.app.n8n.cloud/webhook-test/guante-rehabilitacion",
)

# Archivo local opcional para comparar contra la sesion anterior.
HISTORIAL_LOCAL = "sesiones_locales.json"


# =========================
# PARSEO DEL FORMATO SERIAL ACTUAL
# =========================
def parsear_muestra(linea):
    """
    Convierte una linea serial del ESP32 en un diccionario.
    Mantiene compatibilidad con:
    D1,angulo1,rom1,repeticiones1,voltaje1,val1,
    D2,angulo2,rom2,repeticiones2,voltaje2,val2,
    D3,angulo3,rom3,repeticiones3,voltaje3,val3,
    VIENDO_DEDO,1
    """
    datos = linea.strip().split(",")

    if len(datos) < 20 or datos[0] != "D1" or datos[6] != "D2" or datos[12] != "D3":
        return None

    return {
        "d1_angulo": float(datos[1]),
        "d1_rom": float(datos[2]),
        "d1_reps": int(float(datos[3])),
        "d1_voltaje": float(datos[4]),
        "d1_adc": int(float(datos[5])),
        "d2_angulo": float(datos[7]),
        "d2_rom": float(datos[8]),
        "d2_reps": int(float(datos[9])),
        "d2_voltaje": float(datos[10]),
        "d2_adc": int(float(datos[11])),
        "d3_angulo": float(datos[13]),
        "d3_rom": float(datos[14]),
        "d3_reps": int(float(datos[15])),
        "d3_voltaje": float(datos[16]),
        "d3_adc": int(float(datos[17])),
        "viendo_dedo": int(float(datos[19])),
    }


# =========================
# RESUMEN DE APOYO NO DIAGNOSTICO
# =========================
def generar_resumen_ia(resumen, sesion_anterior=None):
    """
    Genera texto observacional para Telegram/Sheets.
    No emite diagnosticos ni conclusiones clinicas definitivas.
    """
    roms = {
        "dedo 1": resumen["d1_rom"],
        "dedo 2": resumen["d2_rom"],
        "dedo 3": resumen["d3_rom"],
    }
    dedo_mayor = max(roms, key=roms.get)
    dedo_menor = min(roms, key=roms.get)

    texto = (
        f"Se observo una sesion con ROM promedio de {resumen['rom_promedio']:.1f}°. "
        f"El {dedo_mayor} presento mayor amplitud de movimiento y el {dedo_menor} "
        "mostro menor movilidad relativa durante el registro."
    )

    if sesion_anterior and sesion_anterior.get("rom_promedio"):
        anterior = float(sesion_anterior["rom_promedio"])
        if anterior > 0:
            cambio = ((resumen["rom_promedio"] - anterior) / anterior) * 100
            if cambio > 0:
                texto += f" Se evidencia una mejora observada de {cambio:.1f}% respecto a la sesion anterior."
            elif cambio < 0:
                texto += f" Se observa una variacion de {cambio:.1f}% respecto a la sesion anterior."
            else:
                texto += " El ROM promedio se mantuvo estable respecto a la sesion anterior."

    return texto


# =========================
# HISTORIAL LOCAL
# =========================
def cargar_historial_local():
    if not os.path.exists(HISTORIAL_LOCAL):
        return []

    try:
        with open(HISTORIAL_LOCAL, "r", encoding="utf-8") as archivo:
            return json.load(archivo)
    except (OSError, json.JSONDecodeError):
        return []


def guardar_en_historial_local(resumen):
    historial = cargar_historial_local()
    historial.append(resumen)

    with open(HISTORIAL_LOCAL, "w", encoding="utf-8") as archivo:
        json.dump(historial[-50:], archivo, ensure_ascii=False, indent=2)


# =========================
# CALCULO DE SESION
# =========================
def calcular_resumen_sesion(sesion, inicio_sesion, fin_sesion):
    if not sesion:
        return None

    d1_rom = max(muestra["d1_rom"] for muestra in sesion)
    d2_rom = max(muestra["d2_rom"] for muestra in sesion)
    d3_rom = max(muestra["d3_rom"] for muestra in sesion)

    # Las repeticiones se reinician en SESSION_START, por eso el maximo equivale
    # al conteo final alcanzado durante la sesion.
    d1_reps = max(muestra["d1_reps"] for muestra in sesion)
    d2_reps = max(muestra["d2_reps"] for muestra in sesion)
    d3_reps = max(muestra["d3_reps"] for muestra in sesion)

    rom_promedio = round((d1_rom + d2_rom + d3_rom) / 3, 1)
    reps_totales = d1_reps + d2_reps + d3_reps

    resumen = {
        "paciente": PACIENTE,
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "duracion": int(fin_sesion - inicio_sesion),
        "d1_rom": round(d1_rom, 1),
        "d1_reps": d1_reps,
        "d2_rom": round(d2_rom, 1),
        "d2_reps": d2_reps,
        "d3_rom": round(d3_rom, 1),
        "d3_reps": d3_reps,
        "rom_promedio": rom_promedio,
        "reps_totales": reps_totales,
    }

    historial = cargar_historial_local()
    sesion_anterior = historial[-1] if historial else None
    resumen["resumen_ia"] = generar_resumen_ia(resumen, sesion_anterior)

    return resumen


# =========================
# ENVIO A N8N
# =========================
def enviar_a_webhook(resumen):
    respuesta = requests.post(WEBHOOK_URL, json=resumen, timeout=30)
    respuesta.raise_for_status()
    return respuesta


# =========================
# BUCLE PRINCIPAL
# =========================
def main():
    global PACIENTE

    if not PACIENTE:
        PACIENTE = input("Nombre del paciente: ").strip()

    if not PACIENTE:
        print("Debes ingresar un nombre de paciente para iniciar el collector.")
        return

    sesion_activa = False
    sesion = []
    inicio_sesion = None

    print(f"Conectando a {PUERTO_SERIAL} a {BAUDIOS} baudios...")

    with serial.Serial(PUERTO_SERIAL, BAUDIOS, timeout=1) as ser:
        print("Collector listo. Esperando SESSION_START...")

        while True:
            linea = ser.readline().decode("utf-8", errors="ignore").strip()

            if not linea:
                continue

            if linea == "SESSION_START":
                sesion_activa = True
                sesion = []
                inicio_sesion = time.time()
                print("Sesion iniciada.")
                continue

            if linea == "SESSION_END":
                if not sesion_activa:
                    print("SESSION_END recibido sin sesion activa. Se ignora.")
                    continue

                fin_sesion = time.time()
                sesion_activa = False
                resumen = calcular_resumen_sesion(sesion, inicio_sesion, fin_sesion)

                if resumen is None:
                    print("Sesion finalizada sin muestras validas.")
                    continue

                print("Sesion finalizada. Resumen generado:")
                print(json.dumps(resumen, ensure_ascii=False, indent=2))

                try:
                    enviar_a_webhook(resumen)
                    guardar_en_historial_local(resumen)
                    print("Resumen enviado a n8n y guardado en historial local.")
                except requests.RequestException as error:
                    print(f"No se pudo enviar el resumen a n8n: {error}")

                continue

            if sesion_activa:
                muestra = parsear_muestra(linea)
                if muestra:
                    sesion.append(muestra)


if __name__ == "__main__":
    main()
