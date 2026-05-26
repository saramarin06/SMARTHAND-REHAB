import json
import os
import threading
import time
from collections import deque

import matplotlib.pyplot as plt
import requests
import serial
from matplotlib.animation import FuncAnimation

import collector

# =========================
# CONFIGURACION PUERTO SERIAL
# =========================
PUERTO_SERIAL = "COM4"
BAUDIOS = 115200

# Si no defines PACIENTE como variable de entorno, se pedira al iniciar.
PACIENTE = os.getenv("PACIENTE", "").strip()

# =========================
# CONFIGURACION SESION
# =========================
sesion_activa = False
sesion = []
inicio_sesion = None
estado_envio = "Esperando SESSION_START"


# =========================
# VARIABLES PARA GRAFICA
# =========================
max_puntos = 50

angulo1_hist = deque([0] * max_puntos, maxlen=max_puntos)
rom1_hist = deque([0] * max_puntos, maxlen=max_puntos)

angulo2_hist = deque([0] * max_puntos, maxlen=max_puntos)
rom2_hist = deque([0] * max_puntos, maxlen=max_puntos)

angulo3_hist = deque([0] * max_puntos, maxlen=max_puntos)
rom3_hist = deque([0] * max_puntos, maxlen=max_puntos)

reps1, reps2, reps3 = 0, 0, 0
dedo_en_matriz = 1


# =========================
# CONFIGURACION FIGURA
# =========================
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 10))

linea1, = ax1.plot(angulo1_hist, label="Angulo Dedo 1", color="blue")
linea_rom1, = ax1.plot(rom1_hist, label="ROM Dedo 1", color="orange")

linea2, = ax2.plot(angulo2_hist, label="Angulo Dedo 2", color="green")
linea_rom2, = ax2.plot(rom2_hist, label="ROM Dedo 2", color="red")

linea3, = ax3.plot(angulo3_hist, label="Angulo Dedo 3", color="purple")
linea_rom3, = ax3.plot(rom3_hist, label="ROM Dedo 3", color="brown")

for ax, titulo in zip([ax1, ax2, ax3], ["Dedo 1", "Dedo 2", "Dedo 3"]):
    ax.set_ylim(0, 100)
    ax.set_xlim(0, max_puntos)
    ax.set_title(titulo)
    ax.set_xlabel("Muestras")
    ax.set_ylabel("Angulo / ROM")
    ax.legend(loc="upper right")
    ax.grid(True)

texto_info = fig.text(
    0.5,
    0.02,
    "",
    ha="center",
    fontsize=11,
    bbox=dict(facecolor="lightgray", alpha=0.7),
)

plt.tight_layout(rect=[0, 0.10, 1, 1], h_pad=3.0)


# =========================
# ENVIO EN SEGUNDO PLANO
# =========================
def enviar_resumen_en_segundo_plano(resumen):
    global estado_envio

    try:
        collector.enviar_a_webhook(resumen)
        collector.guardar_en_historial_local(resumen)
        estado_envio = "Resumen enviado a n8n y guardado localmente"
        print("Resumen enviado a n8n y guardado en historial local.")
    except requests.RequestException as error:
        estado_envio = "Error enviando resumen a n8n"
        print(f"No se pudo enviar el resumen a n8n: {error}")


def finalizar_sesion():
    global sesion_activa, sesion, inicio_sesion, estado_envio

    if not sesion_activa:
        estado_envio = "SESSION_END recibido sin sesion activa"
        print("SESSION_END recibido sin sesion activa. Se ignora.")
        return

    fin_sesion = time.time()
    sesion_activa = False
    resumen = collector.calcular_resumen_sesion(sesion, inicio_sesion, fin_sesion)

    if resumen is None:
        estado_envio = "Sesion finalizada sin muestras validas"
        print("Sesion finalizada sin muestras validas.")
        return

    estado_envio = "Sesion finalizada. Enviando resumen a n8n..."
    print("Sesion finalizada. Resumen generado:")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))

    hilo = threading.Thread(
        target=enviar_resumen_en_segundo_plano,
        args=(resumen,),
        daemon=True,
    )
    hilo.start()


# =========================
# LECTURA SERIAL COMPARTIDA
# =========================
def procesar_linea(linea):
    global sesion_activa, sesion, inicio_sesion, estado_envio
    global reps1, reps2, reps3, dedo_en_matriz

    if linea == "SESSION_START":
        sesion_activa = True
        sesion = []
        inicio_sesion = time.time()
        estado_envio = "Sesion activa"
        print("Sesion iniciada.")
        return None

    if linea == "SESSION_END":
        finalizar_sesion()
        return None

    muestra = collector.parsear_muestra(linea)
    if not muestra:
        return None

    if sesion_activa:
        sesion.append(muestra)

    reps1 = muestra["d1_reps"]
    reps2 = muestra["d2_reps"]
    reps3 = muestra["d3_reps"]
    dedo_en_matriz = muestra["viendo_dedo"]

    return muestra


def actualizar_grafica(muestra):
    angulo1_hist.append(muestra["d1_angulo"])
    rom1_hist.append(muestra["d1_rom"])
    angulo2_hist.append(muestra["d2_angulo"])
    rom2_hist.append(muestra["d2_rom"])
    angulo3_hist.append(muestra["d3_angulo"])
    rom3_hist.append(muestra["d3_rom"])

    linea1.set_ydata(angulo1_hist)
    linea_rom1.set_ydata(rom1_hist)
    linea2.set_ydata(angulo2_hist)
    linea_rom2.set_ydata(rom2_hist)
    linea3.set_ydata(angulo3_hist)
    linea_rom3.set_ydata(rom3_hist)

    estado = "ACTIVA" if sesion_activa else "INACTIVA"
    info_str = (
        f"Dedo 1 | Repeticiones: {reps1} | ROM: {muestra['d1_rom']:.1f} deg   ---   "
        f"Dedo 2 | Repeticiones: {reps2} | ROM: {muestra['d2_rom']:.1f} deg   ---   "
        f"Dedo 3 | Repeticiones: {reps3} | ROM: {muestra['d3_rom']:.1f} deg\n"
        f"Sesion: {estado} | Mostrando en Matriz LED Fisica: DEDO {dedo_en_matriz} | {estado_envio}"
    )
    texto_info.set_text(info_str)


def crear_actualizador(ser):
    def actualizar(frame):
        ultima_muestra = None

        try:
            # Procesa todas las lineas para no perder SESSION_START/SESSION_END.
            # La grafica se actualiza con la ultima muestra valida recibida.
            while ser.in_waiting > 0:
                linea = ser.readline().decode("utf-8", errors="ignore").strip()
                if not linea:
                    continue
                muestra = procesar_linea(linea)
                if muestra:
                    ultima_muestra = muestra

            if ultima_muestra:
                actualizar_grafica(ultima_muestra)

        except Exception as error:
            print(f"Error de lectura serial: {error}")

        return linea1, linea_rom1, linea2, linea_rom2, linea3, linea_rom3, texto_info

    return actualizar


# =========================
# PROGRAMA PRINCIPAL
# =========================
def main():
    global PACIENTE

    if not PACIENTE:
        PACIENTE = input("Nombre del paciente: ").strip()

    if not PACIENTE:
        print("Debes ingresar un nombre de paciente para iniciar.")
        return

    collector.PACIENTE = PACIENTE

    print(f"Conectando a {PUERTO_SERIAL} a {BAUDIOS} baudios...")

    with serial.Serial(PUERTO_SERIAL, BAUDIOS, timeout=0) as ser:
        print("Monitor + collector listo. Esperando SESSION_START...")
        ani = FuncAnimation(
            fig,
            crear_actualizador(ser),
            interval=20,
            cache_frame_data=False,
        )
        plt.show()


if __name__ == "__main__":
    main()
