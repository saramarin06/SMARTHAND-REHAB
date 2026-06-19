from machine import Pin, ADC, I2C
import ssd1306
from time import sleep, ticks_ms, ticks_diff

# =========================
# CONFIGURACION ADC
# =========================
flex1 = ADC(Pin(34))   # Dedo 1
flex2 = ADC(Pin(35))   # Dedo 2
flex3 = ADC(Pin(36))   # Dedo 3

for flex in [flex1, flex2, flex3]:
    flex.atten(ADC.ATTN_11DB)
    flex.width(ADC.WIDTH_12BIT)

# =========================
# CALIBRACION ABSOLUTA DEL SENSOR
# =========================
# Estos valores DEBES medirlos en laboratorio (con un transportador/goniómetro).
# Fija el sensor a 0° exactos y anota el ADC. Luego a 90° exactos y anota el ADC.
ADC_0_D1  = 1208
ADC_0_D2  = 2119
ADC_0_D3  = 1954

ADC_90_D1 = 1600
ADC_90_D2 = 2222
ADC_90_D3 = 2110

ALPHA = 0.25
N_MUESTRAS = 16

# =========================
# CONFIGURACION PANTALLA OLED
# =========================
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

oled.fill(0)
oled.text("SISTEMA LISTO", 12, 28)
oled.show()
sleep(1.5)

# =========================
# INTERRUPCION PARA CAMBIO DE DEDO
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
# FUNCIONES DE LECTURA Y MAPEO
# =========================
def leer_promedio(adc, n=N_MUESTRAS):
    suma = 0
    for _ in range(n):
        suma += adc.read()
    return suma // n

def mapear_angulo(val, adc_0, adc_90):
    rango = adc_90 - adc_0
    if rango == 0:
        return 0.0
    angulo = (val - adc_0) * 90.0 / rango
    
    # Restricción estricta: nunca menos de 0°, nunca más de 90°
    if angulo < 0.0: return 0.0
    if angulo > 90.0: return 90.0
    return angulo

# =========================
# VARIABLES DEL SISTEMA
# =========================
rom1, rom2, rom3 = 0, 0, 0
repeticiones1, repeticiones2, repeticiones3 = 0, 0, 0
estado_flexion1, estado_flexion2, estado_flexion3 = 0, 0, 0

val_filt1 = float(leer_promedio(flex1))
val_filt2 = float(leer_promedio(flex2))
val_filt3 = float(leer_promedio(flex3))

# Umbrales para contar una repetición
UMBRAL_ALTO = 50
UMBRAL_BAJO = 20

# =========================
# BUCLE PRINCIPAL
# =========================
while True:
    val1_raw = leer_promedio(flex1)
    val2_raw = leer_promedio(flex2)
    val3_raw = leer_promedio(flex3)

    # Filtro EMA
    val_filt1 = ALPHA * val1_raw + (1 - ALPHA) * val_filt1
    val_filt2 = ALPHA * val2_raw + (1 - ALPHA) * val_filt2
    val_filt3 = ALPHA * val3_raw + (1 - ALPHA) * val_filt3

    val_dedo1 = int(val_filt1)
    val_dedo2 = int(val_filt2)
    val_dedo3 = int(val_filt3)

    voltaje1 = (val_dedo1 / 4095) * 3.3
    voltaje2 = (val_dedo2 / 4095) * 3.3
    voltaje3 = (val_dedo3 / 4095) * 3.3

    # Mapeo Absoluto (La Verdad Clínica)
    angulo1 = mapear_angulo(val_dedo1, ADC_0_D1, ADC_90_D1)
    angulo2 = mapear_angulo(val_dedo2, ADC_0_D2, ADC_90_D2)
    angulo3 = mapear_angulo(val_dedo3, ADC_0_D3, ADC_90_D3)

    # Registro de ROM Máximo
    if angulo1 > rom1: rom1 = angulo1
    if angulo2 > rom2: rom2 = angulo2
    if angulo3 > rom3: rom3 = angulo3

    # Conteo de Repeticiones
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

    # Selector de Pantalla
    if dedo_pantalla == 1:
        ang_n, rom_n, reps = angulo1, rom1, repeticiones1
    elif dedo_pantalla == 2:
        ang_n, rom_n, reps = angulo2, rom2, repeticiones2
    else:
        ang_n, rom_n, reps = angulo3, rom3, repeticiones3

    # =========================
    # VISUALIZACION EN OLED
    # =========================
    oled.fill(0)
    
    oled.text(f"-- DEDO {dedo_pantalla} --", 24, 0)
    oled.text(f"Angulo: {int(ang_n)} deg", 0, 16)
    oled.text(f"ROM max:{int(rom_n)} deg", 0, 28)
    oled.text(f"Reps:   {reps}", 0, 40)
    
    # Barra de progreso absoluta (0 a 90 grados = 0 a 128 pixeles)
    # Si el paciente hace 45°, la barra llegará a 64 píxeles (exactamente la mitad)
    ancho_barra = int((ang_n / 90.0) * 128)
    
    # Marco exterior de la barra (Meta total: 90°)
    oled.rect(0, 52, 128, 10, 1)
    
    # Relleno interior de la barra (Progreso actual)
    oled.fill_rect(0, 52, ancho_barra, 10, 1)
    
    oled.show()

    # =========================
    # COMUNICACION SERIAL
    # =========================
    mensaje = (
        f"D1,{round(angulo1,1)},{round(rom1,1)},{repeticiones1},{round(voltaje1,2)},{val_dedo1},"
        f"D2,{round(angulo2,1)},{round(rom2,1)},{repeticiones2},{round(voltaje2,2)},{val_dedo2},"
        f"D3,{round(angulo3,1)},{round(rom3,1)},{repeticiones3},{round(voltaje3,2)},{val_dedo3},"
        f"VIENDO_DEDO,{dedo_pantalla}"
    )
    print(mensaje)

    sleep(0.05)