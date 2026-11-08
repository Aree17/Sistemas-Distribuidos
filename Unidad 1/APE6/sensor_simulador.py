import json
import time
import random
from datetime import datetime
import paho.mqtt.client as mqtt

BROKER = "localhost"
PUERTO = 1883
VEHICULOS = ["VH-001", "VH-002", "VH-003"]

def on_connect(client, userdata, flags, rc):
    print(f"[{datetime.now().isoformat()}] Conectado al broker MQTT (rc={rc})")

def simular_gps(id_vehiculo):
    base_lat = -2.1709
    base_lng = -79.9224
    latitud = base_lat + random.uniform(-0.01, 0.01)
    longitud = base_lng + random.uniform(-0.01, 0.01)
    velocidad = random.uniform(20, 80)
    return {
        "lat": round(latitud, 6),
        "lng": round(longitud, 6),
        "speed": round(velocidad, 1)
    }

def simular_temperatura(id_vehiculo):
    temperatura = random.uniform(-5, 8)
    return {
        "temperature": round(temperatura, 1),
        "unit": "celsius"
    }

def simular_combustible(id_vehiculo):
    combustible = random.uniform(10, 100)
    return {
        "fuel_level": round(combustible, 1),
        "unit": "percent"
    }

def principal():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.connect(BROKER, PUERTO)
    client.loop_start()

    print("Iniciando simulador de sensores IoT...")
    try:
        while True:
            timestamp = datetime.now().isoformat()
            for vehiculo in VEHICULOS:
                # GPS
                gps_data = {**{"vehicle_id": vehiculo, "timestamp": timestamp}, **simular_gps(vehiculo)}
                client.publish(f"flota/{vehiculo}/gps", json.dumps(gps_data))

                # Temperatura
                temp_data = {**{"vehicle_id": vehiculo, "timestamp": timestamp}, **simular_temperatura(vehiculo)}
                client.publish(f"flota/{vehiculo}/temperatura", json.dumps(temp_data))

                # Combustible
                fuel_data = {**{"vehicle_id": vehiculo, "timestamp": timestamp}, **simular_combustible(vehiculo)}
                client.publish(f"flota/{vehiculo}/combustible", json.dumps(fuel_data))

                print(f"[{timestamp}] Datos publicados para vehículo {vehiculo}")
            
            time.sleep(5)
    except KeyboardInterrupt:
        print("Deteniendo simulador...")
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    principal()