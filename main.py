# ==========================================
# CALIBRACION FLEX SENSOR - MICROPYTHON
# ESP32
# ==========================================


from machine import ADC, Pin
from time import sleep

flex = ADC(Pin(32))    # Cambia el pin segun el dedo que estes calibrando
flex.atten(ADC.ATTN_11DB)
flex.width(ADC.WIDTH_12BIT)

N = 200  # numero de muestras a promediar por posicion

def capturar(etiqueta):
    input("\nPon el dedo en " + etiqueta + " y presiona ENTER...")
    print("Capturando, NO te muevas...")
    lecturas = []
    for _ in range(N):
        lecturas.append(flex.read())
        sleep(0.01)
        
    prom = sum(lecturas) // N
    mn = min(lecturas)
    mx = max(lecturas)
    print("  Promedio: ", prom)
    print("  Min:", mn, " Max:", mx, " Rango ruido:", mx - mn)
    return prom

print("=== CALIBRACION FLEX SENSOR ===")

adc_0  = capturar("0 GRADOS (dedo recto)")
adc_90 = capturar("90 GRADOS (dedo doblado al maximo)")

print("\n=== RESULTADOS ===")
print("ADC_0  =", adc_0)
print("ADC_90 =", adc_90)
print("Diferencia util:", abs(adc_90 - adc_0), "counts")