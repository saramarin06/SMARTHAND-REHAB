from machine import Pin, ADC, SPI
from max7219 import Matrix8x8
from time import sleep, ticks_ms, ticks_diff

# =========================
# CONFIGURACION ADC
# =========================
flex1 = ADC(Pin(34))   # Dedo 1
flex2 = ADC(Pin(35))   # Dedo 2
flex3 = ADC(Pin(32))   # Dedo 3

for flex in [flex1, flex2, flex3]:
    flex.atten(ADC.ATTN_11DB)
    flex.width(ADC.WIDTH_12BIT)

# =========================
# CALIBRACION DE SENSORES FLEX  <-- AJUSTA ESTOS VALORES
# =========================
# Valor de ADC cuando el dedo está RECTO (0°)
ADC_0_D1  = 1895
ADC_0_D2  = 1884
ADC_0_D3  = 1868

# Valor de ADC cuando el dedo está totalmente FLEXIONADO (90°)
ADC_90_D1 = 2311
ADC_90_D2 = 2003
ADC_90_D3 = 2008

# Filtro EMA: 0 < ALPHA <= 1. Más bajo = más suave pero más "lento".
# Buen punto de partida: 0.20 - 0.30
ALPHA = 0.25

# Cuántas lecturas tomar por ciclo para promediar (oversampling)
N_MUESTRAS = 16

# =========================
# CONFIGURACION MAX7219
# =========================
spi = SPI(1, baudrate=1000000, polarity=0, phase=0,
          sck=Pin(18), mosi=Pin(23))
cs = Pin(5, Pin.OUT)
display = Matrix8x8(spi, cs, 4)
display.brightness(3)
display.fill(0)
display.show()

# =========================
# INTERRUPCION PARA PANTALLA
# =========================
boton_pantalla = Pin(15, Pin.IN, Pin.PULL_UP)
dedo_pantalla = 1
ultimo_tiempo_irq = 0

def cambiar_pantalla(pin):
    global dedo_pantalla, ultimo_tiempo_irq
    tiempo_actual = ticks_ms()
    if ticks_diff(tiempo_actual, ultimo_tiempo_irq) > 300:
        dedo_pantalla += 1
        if dedo_pantalla > 3:
            dedo_pantalla = 1
        ultimo_tiempo_irq = tiempo_actual

boton_pantalla.irq(trigger=Pin.IRQ_FALLING, handler=cambiar_pantalla)

# =========================
# FUNCIONES NUEVAS PARA EL FLEX
# =========================
def leer_promedio(adc, n=N_MUESTRAS):
    """Oversampling: lee N veces el ADC y devuelve el promedio."""
    suma = 0
    for _ in range(n):
        suma += adc.read()
    return suma // n

def mapear_angulo(val, adc_0, adc_90):
    """
    Convierte una lectura cruda del ADC a un ángulo entre 0 y 90 grados,
    usando los valores de calibración del dedo. Funciona aunque
    adc_90 sea menor que adc_0 (depende de cómo armaste el divisor).
    """
    rango = adc_90 - adc_0
    if rango == 0:
        return 0
    angulo = (val - adc_0) * 90.0 / rango
    if angulo < 0:
        return 0.0
    if angulo > 90:
        return 90.0
    return angulo

# =========================
# VARIABLES DEL SISTEMA
# =========================
rom1, rom2, rom3 = 0, 0, 0
repeticiones1, repeticiones2, repeticiones3 = 0, 0, 0
estado_flexion1, estado_flexion2, estado_flexion3 = 0, 0, 0

# Inicializamos el filtro EMA con la primera lectura real
val_filt1 = float(leer_promedio(flex1))
val_filt2 = float(leer_promedio(flex2))
val_filt3 = float(leer_promedio(flex3))

UMBRAL_ALTO = 60
UMBRAL_BAJO = 30

# =========================
# FUENTE MANUAL DE NUMEROS
# =========================
FONT_3x5 = {
    0: [(0,0),(1,0),(2,0),(0,1),(2,1),(0,2),(2,2),(0,3),(2,3),(0,4),(1,4),(2,4)],
    1: [(1,0),(0,1),(1,1),(1,2),(1,3),(0,4),(1,4),(2,4)],
    2: [(0,0),(1,0),(2,0),(2,1),(0,2),(1,2),(2,2),(0,3),(0,4),(1,4),(2,4)],
    3: [(0,0),(1,0),(2,0),(2,1),(0,2),(1,2),(2,2),(2,3),(0,4),(1,4),(2,4)],
    4: [(0,0),(2,0),(0,1),(2,1),(0,2),(1,2),(2,2),(2,3),(2,4)],
    5: [(0,0),(1,0),(2,0),(0,1),(0,2),(1,2),(2,2),(2,3),(0,4),(1,4),(2,4)],
    6: [(0,0),(1,0),(2,0),(0,1),(0,2),(1,2),(2,2),(0,3),(2,3),(0,4),(1,4),(2,4)],
    7: [(0,0),(1,0),(2,0),(2,1),(2,2),(2,3),(2,4)],
    8: [(0,0),(1,0),(2,0),(0,1),(2,1),(0,2),(1,2),(2,2),(0,3),(2,3),(0,4),(1,4),(2,4)],
    9: [(0,0),(1,0),(2,0),(0,1),(2,1),(0,2),(1,2),(2,2),(2,3),(0,4),(1,4),(2,4)]
}

# =========================
# FUNCIONES DE DIBUJO (sin cambios)
# =========================
def set_pixel(x, y, color):
    if 0 <= x <= 31 and 0 <= y <= 7:
        display.pixel(31 - x, 7 - y, color)

def dibujar_barra(modulo, nivel):
    x_inicio = modulo * 8
    for x in range(x_inicio, x_inicio + 8):
        for y in range(8):
            set_pixel(x, y, 0)
    nivel = max(0, min(nivel, 8))
    for fila in range(nivel):
        y = 7 - fila
        for x in range(x_inicio + 2, x_inicio + 6):
            set_pixel(x, y, 1)

def dibujar_numero(modulo, numero):
    x_inicio = modulo * 8
    for x in range(x_inicio, x_inicio + 8):
        for y in range(8):
            set_pixel(x, y, 0)
    numero = max(0, min(numero, 9))
    for px, py in FONT_3x5.get(numero, []):
        set_pixel(x_inicio + px + 2, py + 1, 1)

# =========================
# BUCLE PRINCIPAL
# =========================
while True:
    # --- LECTURA con oversampling ---
    val1_raw = leer_promedio(flex1)
    val2_raw = leer_promedio(flex2)
    val3_raw = leer_promedio(flex3)

    # --- FILTRO EMA: suaviza ruido entre ciclos ---
    val_filt1 = ALPHA * val1_raw + (1 - ALPHA) * val_filt1
    val_filt2 = ALPHA * val2_raw + (1 - ALPHA) * val_filt2
    val_filt3 = ALPHA * val3_raw + (1 - ALPHA) * val_filt3

    val_dedo1 = int(val_filt1)
    val_dedo2 = int(val_filt2)
    val_dedo3 = int(val_filt3)

    # --- VOLTAJE (informativo) ---
    voltaje1 = (val_dedo1 / 4095) * 3.3
    voltaje2 = (val_dedo2 / 4095) * 3.3
    voltaje3 = (val_dedo3 / 4095) * 3.3

    # --- ANGULO usando la calibración por dedo ---
    angulo1 = mapear_angulo(val_dedo1, ADC_0_D1, ADC_90_D1)
    angulo2 = mapear_angulo(val_dedo2, ADC_0_D2, ADC_90_D2)
    angulo3 = mapear_angulo(val_dedo3, ADC_0_D3, ADC_90_D3)

    # --- ROM MAXIMO ---
    if angulo1 > rom1: rom1 = angulo1
    if angulo2 > rom2: rom2 = angulo2
    if angulo3 > rom3: rom3 = angulo3

    # --- REPETICIONES (con histéresis) ---
    if estado_flexion1 == 0 and angulo1 > UMBRAL_ALTO: estado_flexion1 = 1
    elif estado_flexion1 == 1 and angulo1 < UMBRAL_BAJO:
        estado_flexion1 = 0
        repeticiones1 += 1

    if estado_flexion2 == 0 and angulo2 > UMBRAL_ALTO: estado_flexion2 = 1
    elif estado_flexion2 == 1 and angulo2 < UMBRAL_BAJO:
        estado_flexion2 = 0
        repeticiones2 += 1

    if estado_flexion3 == 0 and angulo3 > UMBRAL_ALTO: estado_flexion3 = 1
    elif estado_flexion3 == 1 and angulo3 < UMBRAL_BAJO:
        estado_flexion3 = 0
        repeticiones3 += 1

    # =========================
    # VISUALIZACION MATRIZ
    # (la barra "corr_vis" ahora muestra ángulo en lugar de ADC bruto)
    # =========================
    if dedo_pantalla == 1:
        ang_n, rom_n, reps = angulo1, rom1, repeticiones1
    elif dedo_pantalla == 2:
        ang_n, rom_n, reps = angulo2, rom2, repeticiones2
    else:
        ang_n, rom_n, reps = angulo3, rom3, repeticiones3

    corr_vis = int((ang_n / 90) * 8)
    ang_niv  = int((ang_n / 90) * 8)
    rom_niv  = int((rom_n / 90) * 8)

    dibujar_barra(0, corr_vis)
    dibujar_numero(1, reps)
    dibujar_barra(2, ang_niv)
    dibujar_barra(3, rom_niv)
    display.show()

    # =========================
    # COMUNICACION SERIAL (mismo formato, no rompe tu script de Python)
    # =========================
    mensaje = (
        f"D1,{round(angulo1,1)},{round(rom1,1)},{repeticiones1},{round(voltaje1,2)},{val_dedo1},"
        f"D2,{round(angulo2,1)},{round(rom2,1)},{repeticiones2},{round(voltaje2,2)},{val_dedo2},"
        f"D3,{round(angulo3,1)},{round(rom3,1)},{repeticiones3},{round(voltaje3,2)},{val_dedo3},"
        f"VIENDO_DEDO,{dedo_pantalla}"
    )
    print(mensaje)

    sleep(0.05)