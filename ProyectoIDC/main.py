import network
import json
import time
import dht
from machine import Pin, ADC
from umqtt.simple import MQTTClient

# Configuracion WiFi
WIFI_SSID     = "POCO X6 Pro 5G"
WIFI_PASSWORD = "13579000"

# Configuracion MQTT
MQTT_BROKER   = "10.226.2.73"   # IP donde corre Mosquitto
MQTT_PORT     = 1883
MQTT_CLIENT   = "pico_aula_01"
TOPIC_SENSORES = b"upv/etsiinf/aula1/sensors"

# Intervalo de lectura en segundos
INTERVALO = 20

# Sensor DHT22 en su pin 15
sensor_dht = dht.DHT22(Pin(15))

# Sensor MH-Z19
adc_co2 = ADC(Pin(26))

def leer_co2():
    valor = adc_co2.read_u16()
    voltaje = valor * 3.3 / 65535
    ppm = (voltaje - 0.4) * (2000 - 400) / (2.0 - 0.4) + 400
    if ppm < 400:
        ppm = 400
    return round(ppm)

def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Conectando a WiFi...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        intentos = 0
        while not wlan.isconnected() and intentos < 20:
            time.sleep(1)
            intentos += 1
            print(".")
    if wlan.isconnected():
        print("WiFi conectado:", wlan.ifconfig())
        return True
    print("Error: no se pudo conectar al WiFi")
    return False

def conectar_mqtt():
    client = MQTTClient(MQTT_CLIENT, MQTT_BROKER, port=MQTT_PORT)
    client.connect()
    print("MQTT conectado a", MQTT_BROKER)
    return client

# Bucle principal
conectar_wifi()
client = conectar_mqtt()

# MH-Z19 necesita 3 minutos de calentamiento en el primer arranque
print("Esperando calentamiento del sensor CO2 (3 min)...")
time.sleep(180)

while True:
    try:
        # Lectura DHT22
        sensor_dht.measure()
        temperatura = sensor_dht.temperature()
        humedad     = sensor_dht.humidity()

        # Lectura MH-Z19
        co2 = leer_co2()
        
        # Lectura hora
        t = time.localtime()
        timeString = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
            t[0], t[1], t[2], t[3], t[4], t[5])

        print(f"Temp: {temperatura}°C | Hum: {humedad}% | CO2: {co2} ppm | Tiempo: {timeString}")

        # Publicar por MQTT
        playload = json.dumps({
            "temperatura": temperatura,
            "humedad": humedad,
            "co2": co2,
            "time": timeString})
        client.publish(TOPIC_SENSORES, playload)

    except OSError as e:
        print("Error de sensor:", e)
        # Si el MQTT se desconecta se reconecta
        try:
            client = conectar_mqtt()
        except:
            conectar_wifi()
            client = conectar_mqtt()

    time.sleep(INTERVALO)