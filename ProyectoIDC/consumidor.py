import json
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883

TOPIC = "upv/etsiinf/aula1/sensors"
OUTPUT_TOPIC = "upv/etsiinf/aula1/people"
IDEAL_PEOPLE_TOPIC = "upv/etsiinf/aula1/idealpeople"


CO2_EXT = 420
VOLUMEN_HABITACION = 50
CAUDAL_VENTILACION = 120
TIPO_ACTIVIDAD = 'oficina'

IDEAL_CO2 = 800
IDEAL_TEMPERATURE = 21

last_co2 = None
last_timestamp = None

# Método realizado con ayuda de ChatGPT #
def estimate_people(co2_medido, co2_ext, volumen, caudal_ventilacion, delta_co2, delta_tiempo, temp_c, actividad):
    """    
    Parámetros:
    - co2_medido: CO2 actual en la habitación medido por el sensor(ppm)
    - co2_ext: CO2 en el exterior (ppm, típicamente 400-450)
    - volumen: Volumen de la habitación (m3)
    - caudal_ventilacion: Tasa de renovación de aire (m3/hora)
    - delta_co2: Cambio de CO2 respecto a la medición anterior (ppm)
    - delta_tiempo: Tiempo transcurrido entre mediciones (segundos)
    - temp_c: Temperatura actual de la habitación (°C)
    - actividad: Tipo de actividad ('reposo', 'oficina', 'moderada')
    """
    # 1. Corrección del CO2 medido por temperatura (Ley de gases ideales)
    temp_k = temp_c + 273.15
    temp_ref_k = 298.15 # 25 °C como referencia estándar
    co2_corregido = co2_medido * (temp_k / temp_ref_k)
    
    # 2. Convertir ppm a fracción volumétrica (m3 de CO2 / m3 de aire)
    co2_m3 = co2_corregido / 1_000_000
    co2_ext_m3 = co2_ext / 1_000_000
    delta_co2_m3 = (delta_co2 * (temp_k / temp_ref_k)) / 1_000_000
    
    # 3. Convertir caudal de ventilación de m3/h a m3/s
    caudal_ventilacion_segundos = caudal_ventilacion / 3600
    
    # 4. Tasa de generación de CO2 por persona (m3/s) según actividad
    tasas_generacion = {
        'reposo': 0.0000045,  # 0.0045 L/s
        'oficina': 0.0000052, # 0.0052 L/s
        'moderada': 0.0000100 # 0.0100 L/s
    }
    m = tasas_generacion.get(actividad)
    
    # 5. Calcular la tasa de cambio en el tiempo (dCO2/dt)
    tasa_cambio = delta_co2_m3 / delta_tiempo
    
    # 6. Aplicar la fórmula de balance de masa
    término_acumulacion = volumen * tasa_cambio
    término_ventilacion = caudal_ventilacion_segundos * (co2_m3 - co2_ext_m3)
    
    personas = (término_acumulacion + término_ventilacion) / m
    
    # Retornamos el número redondeado ya que las personas son enteras
    return max(0, round(personas))

def on_connect(client, userdata, flags, rc):

    print("Conectado al broker MQTT")

    client.subscribe(TOPIC)

    idealPeople = estimate_people(IDEAL_CO2, CO2_EXT, VOLUMEN_HABITACION, CAUDAL_VENTILACION, 0, 1, IDEAL_TEMPERATURE, TIPO_ACTIVIDAD)

    result = {
        "ideal_people": idealPeople
    }

    client.publish(IDEAL_PEOPLE_TOPIC, json.dumps(result))

    print(f"Suscripto a: {TOPIC}")


def on_message(client, userdata, msg):

    global last_co2
    global last_timestamp

    try:

        payload = json.loads(msg.payload.decode())

        co2 = payload["co2"]
        temperature = payload["temperature"]
        timestamp = payload["timestamp"]


        if last_co2 is None:

            last_co2 = co2
            last_timestamp = timestamp

            print("\nPrimera medición recibida...")
            print("Esperando siguiente muestra para calcular variación.")

            return

        delta_co2 = co2 - last_co2
        delta_tiempo = timestamp - last_timestamp

        people = estimate_people(co2, CO2_EXT, VOLUMEN_HABITACION, CAUDAL_VENTILACION, delta_co2, delta_tiempo, temperature, TIPO_ACTIVIDAD)

        result = {
            "timestamp": timestamp,
            "people": people,
            "co2": co2,
            "temperature": temperature
        }

        client.publish(OUTPUT_TOPIC, json.dumps(result))

        last_co2 = co2
        last_timestamp = timestamp

    except Exception as e:

        print("Error procesando mensaje:")
        print(e)


client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT)

client.loop_forever()