import json
import sqlite3
from datetime import datetime
import paho.mqtt.client as mqtt

BROKER = "localhost"
PUERTO = 1883

def inicializar_base_datos():
    conexion = sqlite3.connect("telemetria.db")
    cursor = conexion.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gps_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT,
            lat REAL,
            lng REAL,
            speed REAL,
            timestamp TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS temp_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT,
            temperature REAL,
            unit TEXT,
            timestamp TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fuel_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT,
            fuel_level REAL,
            unit TEXT,
            timestamp TEXT
        )
    """)
    
    conexion.commit()
    conexion.close()
    print("Base de datos inicializada.")

def al_recibir_mensaje(client, userdata, mensaje):
    topic = mensaje.topic
    try:
        payload = json.loads(mensaje.payload.decode())
    except json.JSONDecodeError:
        return

    conexion = sqlite3.connect("telemetria.db")
    cursor = conexion.cursor()

    if "/gps" in topic:
        cursor.execute("""
            INSERT INTO gps_data (vehicle_id, lat, lng, speed, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (payload["vehicle_id"], payload["lat"], payload["lng"], payload["speed"], payload["timestamp"]))
        
    elif "/temperatura" in topic:
        temperatura = payload["temperature"]
        if temperatura > 4:
            print(f"ALERTA: {payload['vehicle_id']} temperatura alta -> {temperatura} °C")
        cursor.execute("""
            INSERT INTO temp_data (vehicle_id, temperature, unit, timestamp)
            VALUES (?, ?, ?, ?)
        """, (payload["vehicle_id"], temperatura, payload["unit"], payload["timestamp"]))
        
    elif "/combustible" in topic:
        fuel_level = payload["fuel_level"]
        if fuel_level < 20:
            print(f"ALERTA: {payload['vehicle_id']} combustible bajo -> {fuel_level} %")
        cursor.execute("""
            INSERT INTO fuel_data (vehicle_id, fuel_level, unit, timestamp)
            VALUES (?, ?, ?, ?)
        """, (payload["vehicle_id"], fuel_level, payload["unit"], payload["timestamp"]))

    conexion.commit()
    conexion.close()

def principal():
    inicializar_base_datos()
    client = mqtt.Client()
    client.on_message = al_recibir_mensaje
    client.connect(BROKER, PUERTO)
    
    client.subscribe("flota/+/gps")
    client.subscribe("flota/+/temperatura")
    client.subscribe("flota/+/combustible")
    
    print("Suscriptor activo. Escuchando topics flota/+/...")
    client.loop_forever()

if __name__ == "__main__":
    principal()