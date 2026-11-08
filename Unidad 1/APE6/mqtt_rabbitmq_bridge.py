import json
import paho.mqtt.client as mqtt
import pika

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
RABBITMQ_HOST = "localhost"

def configurar_rabbitmq():
    conexion = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    canal = conexion.channel()
    
    canal.queue_declare(queue="cola.gps.telemetria", durable=True)
    canal.queue_declare(queue="cola.alertas.temperatura", durable=True)
    canal.queue_declare(queue="cola.combustible.nivel", durable=True)
    
    print("Colas RabbitMQ creadas exitosamente")
    return conexion, canal

def al_recibir_mensaje_mqtt(client, userdata, mensaje):
    topic = mensaje.topic
    try:
        payload = json.loads(mensaje.payload.decode())
    except json.JSONDecodeError:
        return

    canal = userdata["rabbitmq_channel"]

    if "/gps" in topic:
        canal.basic_publish(
            exchange="",
            routing_key="cola.gps.telemetria",
            body=json.dumps(payload),
            properties=pika.BasicProperties(delivery_mode=2) # Persistente
        )
    elif "/temperatura" in topic:
        if payload.get("temperature", 0) > 4:
            alerta = {
                "type": "TEMP_ALERT",
                "message": "Temperatura excedida",
                **payload
            }
            canal.basic_publish(
                exchange="",
                routing_key="cola.alertas.temperatura",
                body=json.dumps(alerta),
                properties=pika.BasicProperties(delivery_mode=2)
            )
    elif "/combustible" in topic:
        if payload.get("fuel_level", 100) < 20:
            alerta = {
                "type": "FUEL_LOW",
                "message": "Combustible bajo",
                **payload
            }
            canal.basic_publish(
                exchange="",
                routing_key="cola.combustible.nivel",
                body=json.dumps(alerta),
                properties=pika.BasicProperties(delivery_mode=2)
            )

def principal():
    conexion_rabbit, canal_rabbit = configurar_rabbitmq()
    
    client = mqtt.Client(userdata={"rabbitmq_channel": canal_rabbit})
    client.on_message = al_recibir_mensaje_mqtt
    
    client.connect(MQTT_BROKER, MQTT_PORT)
    client.subscribe("flota/#")
    
    print("Bridge MQTT-RabbitMQ iniciado...")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        client.disconnect()
        conexion_rabbit.close()
        print("Bridge detenido.")

if __name__ == "__main__":
    principal()