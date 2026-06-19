import json
import os
import threading
import time
import tkinter as tk
from collections import deque
from tkinter import messagebox

import requests
import serial
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import collector

# =========================
# CONFIGURACION PUERTO SERIAL
# =========================
PUERTO_SERIAL = "COM4"
BAUDIOS = 115200
PACIENTE = os.getenv("PACIENTE", "").strip()


# =========================
# ESTADO DE SESION
# =========================
ser = None
sesion_activa = False
sesion = []
inicio_sesion = None
estado_envio = "Esperando inicio"


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
# INTERFAZ TKINTER
# =========================
root = tk.Tk()
root.title("Guante de rehabilitacion - Monitor y sesion")
root.geometry("1100x850")

panel_superior = tk.Frame(root, padx=10, pady=10)
panel_superior.pack(fill=tk.X)

tk.Label(panel_superior, text="Paciente:").pack(side=tk.LEFT)
entrada_paciente = tk.Entry(panel_superior, width=28)
entrada_paciente.insert(0, PACIENTE)
entrada_paciente.pack(side=tk.LEFT, padx=(6, 14))

boton_inicio = tk.Button(panel_superior, text="Iniciar sesion", width=16)
boton_fin = tk.Button(panel_superior, text="Finalizar sesion", width=16, state=tk.DISABLED)
boton_inicio.pack(side=tk.LEFT, padx=4)
boton_fin.pack(side=tk.LEFT, padx=4)

estado_var = tk.StringVar(value="Conectando...")
tk.Label(panel_superior, textvariable=estado_var, anchor="w").pack(side=tk.LEFT, padx=14)

fig = Figure(figsize=(10, 8), dpi=100)
ax1 = fig.add_subplot(311)
ax2 = fig.add_subplot(312)
ax3 = fig.add_subplot(313)

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

fig.tight_layout()
canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

texto_info = tk.StringVar(value="Esperando datos del ESP32")
tk.Label(root, textvariable=texto_info, padx=10, pady=8).pack(fill=tk.X)


# =========================
# FUNCIONES DE SESION
# =========================
def actualizar_estado_interfaz():
    estado = "ACTIVA" if sesion_activa else "INACTIVA"
    estado_var.set(f"Sesion: {estado} | {estado_envio}")
    boton_inicio.config(state=tk.DISABLED if sesion_activa else tk.NORMAL)
    boton_fin.config(state=tk.NORMAL if sesion_activa else tk.DISABLED)


def enviar_comando_esp32(comando):
    if ser is None or not ser.is_open:
        messagebox.showerror("Serial", "El puerto serial no esta abierto.")
        return

    ser.write((comando + "\n").encode("utf-8"))


def iniciar_desde_tkinter():
    global PACIENTE

    PACIENTE = entrada_paciente.get().strip()
    if not PACIENTE:
        messagebox.showwarning("Paciente", "Ingresa el nombre del paciente antes de iniciar.")
        return

    collector.PACIENTE = PACIENTE
    enviar_comando_esp32("START_SESSION")


def finalizar_desde_tkinter():
    enviar_comando_esp32("END_SESSION")


boton_inicio.config(command=iniciar_desde_tkinter)
boton_fin.config(command=finalizar_desde_tkinter)


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

    root.after(0, actualizar_estado_interfaz)


def finalizar_sesion_local():
    global sesion_activa, sesion, inicio_sesion, estado_envio

    if not sesion_activa:
        estado_envio = "SESSION_END recibido sin sesion activa"
        print("SESSION_END recibido sin sesion activa. Se ignora.")
        actualizar_estado_interfaz()
        return

    fin_sesion = time.time()
    sesion_activa = False
    resumen = collector.calcular_resumen_sesion(sesion, inicio_sesion, fin_sesion)

    if resumen is None:
        estado_envio = "Sesion finalizada sin muestras validas"
        print("Sesion finalizada sin muestras validas.")
        actualizar_estado_interfaz()
        return

    estado_envio = "Sesion finalizada. Enviando resumen a n8n..."
    print("Sesion finalizada. Resumen generado:")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    actualizar_estado_interfaz()

    hilo = threading.Thread(
        target=enviar_resumen_en_segundo_plano,
        args=(resumen,),
        daemon=True,
    )
    hilo.start()


def procesar_linea(linea):
    global sesion_activa, sesion, inicio_sesion, estado_envio
    global reps1, reps2, reps3, dedo_en_matriz

    if linea == "SESSION_START":
        sesion_activa = True
        sesion = []
        inicio_sesion = time.time()
        estado_envio = "Sesion iniciada"
        print("Sesion iniciada.")
        actualizar_estado_interfaz()
        return None

    if linea == "SESSION_END":
        finalizar_sesion_local()
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
    texto_info.set(
        f"Dedo 1 | Repeticiones: {reps1} | ROM: {muestra['d1_rom']:.1f} deg   ---   "
        f"Dedo 2 | Repeticiones: {reps2} | ROM: {muestra['d2_rom']:.1f} deg   ---   "
        f"Dedo 3 | Repeticiones: {reps3} | ROM: {muestra['d3_rom']:.1f} deg\n"
        f"Sesion: {estado} | Mostrando en Matriz LED Fisica: DEDO {dedo_en_matriz}"
    )
    canvas.draw_idle()


def leer_serial_periodicamente():
    ultima_muestra = None

    try:
        while ser and ser.in_waiting > 0:
            linea = ser.readline().decode("utf-8", errors="ignore").strip()
            if not linea:
                continue
            muestra = procesar_linea(linea)
            if muestra:
                ultima_muestra = muestra

        if ultima_muestra:
            actualizar_grafica(ultima_muestra)

    except Exception as error:
        estado_var.set(f"Error serial: {error}")
        print(f"Error de lectura serial: {error}")

    root.after(20, leer_serial_periodicamente)


def cerrar():
    if ser and ser.is_open:
        ser.close()
    root.destroy()


# =========================
# PROGRAMA PRINCIPAL
# =========================
try:
    ser = serial.Serial(PUERTO_SERIAL, BAUDIOS, timeout=0)
    estado_envio = "Puerto serial conectado"
    actualizar_estado_interfaz()
    root.after(20, leer_serial_periodicamente)
except serial.SerialException as error:
    estado_var.set(f"No se pudo abrir {PUERTO_SERIAL}: {error}")
    boton_inicio.config(state=tk.DISABLED)
    boton_fin.config(state=tk.DISABLED)

root.protocol("WM_DELETE_WINDOW", cerrar)
root.mainloop()
