import network
import time
from machine import Pin, UART
import dht
from umqtt.simple import MQTTClient

# Configuracion WiFi
WIFI_SSID     = "NombreWifi"
WIFI_PASSWORD = "Contraseña"

# Configuracion MQTT
MQTT_BROKER   = "192.168.x.x"   # IP donde corre Mosquitto
MQTT_PORT     = 1883
MQTT_CLIENT   = "pico_aula_01"
TOPIC_CO2     = b"aula/co2"
TOPIC_TEMP    = b"aula/temperatura"
TOPIC_HUM     = b"aula/humedad"

# Intervalo de lectura en segundos
INTERVALO = 30

# Sensor DHT22 en su pin 15
sensor_dht = dht.DHT22(Pin(15))

# Sensor MH-Z19
uart = UART(1, baudrate=9600, tx=Pin(4), rx=Pin(5))

# Comando de lectura del MH-Z19
CMD_READ_CO2 = bytes([0xFF, 0x01, 0x86, 0x00, 0x00,
                      0x00, 0x00, 0x00, 0x79])

def leer_co2():
    uart.write(CMD_READ_CO2)
    time.sleep_ms(100)
    if uart.any():
        respuesta = uart.read(9)
        if respuesta and len(respuesta) == 9 and respuesta[0] == 0xFF:
            ppm = respuesta[2] * 256 + respuesta[3]
            return ppm
    return None

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

        print(f"Temp: {temperatura}°C | Hum: {humedad}% | CO2: {co2} ppm")

        # Publicar por MQTT (como strings el broker recibira texto)
        client.publish(TOPIC_TEMP, str(temperatura))
        client.publish(TOPIC_HUM,  str(humedad))
        if co2 is not None:
            client.publish(TOPIC_CO2, str(co2))

    except OSError as e:
        print("Error de sensor:", e)
        # Si el MQTT se desconecta se reconecta
        try:
            client = conectar_mqtt()
        except:
            conectar_wifi()
            client = conectar_mqtt()

    time.sleep(INTERVALO)