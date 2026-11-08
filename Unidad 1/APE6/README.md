# Monitoreo de flota con MQTT, RabbitMQ y Spring Boot
Guía de instalación y ejecución en Windows con PowerShell. Una computadora funciona como servidor; las demás se conectan a su IP dentro de la misma red. También puede probarse todo en una sola computadora.

> Estas instrucciones se basan en la documentación y el diagnóstico de la copia revisada, no en una ejecución completa del repositorio. Permiten preparar y comprobar los componentes existentes; no garantizan resolver errores de código que aparezcan al ejecutarlos. La API actual devuelve datos de ejemplo y Spring no almacena GPS en una base de datos. Cambiar IP e instalar dependencias no implementa esas funcionalidades.

## 1. Distribución de componentes

| Equipo | Componentes |
|---|---|
| Servidor | Mosquitto, RabbitMQ y Spring Boot |
| Cliente de sensores | `sensor_simulador.py` |
| Equipo del puente, preferiblemente el servidor | `mqtt_rabbitmq_bridge.py`; ejecutar una sola instancia |
| Equipo de almacenamiento opcional | `mqtt_subscriber.py`; crea SQLite local |
| Cualquier equipo conectado | Navegador para RabbitMQ y consultas de la API |

No es necesario instalar RabbitMQ en cada cliente. Cada simulador simultáneo debe tener un identificador de cliente MQTT diferente si el código fija uno; revisarlo antes de ejecutar varias copias.

| Puerto TCP del servidor | Uso |
|---|---|
| 1883 | MQTT |
| 5672 | AMQP: puente y Spring |
| 15672 | Interfaz web de RabbitMQ |
| 8080 | API REST |

El puerto 9001 publicado en Compose no tiene un listener WebSocket configurado en la copia revisada y no se utiliza en esta guía.

## 2. Descargar y ubicar el proyecto
Instalar [Git](https://git-scm.com/downloads), clonar la URL real del repositorio y entrar a la carpeta que contiene `docker-compose.yml`, los tres scripts Python y `fleet-monitor/`:

```powershell
git clone <URL_REAL_DEL_REPOSITORIO>
cd <RUTA_DE_LA_CARPETA_APE6>
Get-ChildItem
```

Los marcadores entre `<...>` deben reemplazarse antes de ejecutar los comandos. La URL del repositorio no fue proporcionada; no se incluye una ficticia. En adelante esta carpeta se llama **raíz del proyecto**. Si se descarga ZIP, extraerlo y abrir PowerShell en esa misma carpeta.

## 3. Instalar y comprobar requisitos
En el servidor instalar [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) con contenedores Linux y un [JDK 21](https://adoptium.net/temurin/releases/?version=21). En los equipos que ejecuten scripts instalar [Python 3.13](https://www.python.org/downloads/). Usar el Maven Wrapper incluido: no es necesario instalar Maven por separado. La primera ejecución requiere Internet para descargar imágenes, Maven y dependencias.

Abrir Docker Desktop y esperar a que su motor esté listo. Comprobar en PowerShell:

```powershell
docker version
docker compose version
docker info
java -version
javac -version
```

`docker info` debe mostrar información del servidor Docker, sin error de conexión. `java` y `javac` deben usar el mismo JDK compatible; Java 8 no sirve para este proyecto. Si apuntan a versiones diferentes, configurar la sesión con la ruta real del JDK:

```powershell
$env:JAVA_HOME = '<CARPETA_REAL_DEL_JDK_21>'
$env:Path = "$env:JAVA_HOME\bin;$env:Path"
java -version
javac -version
```

Repetir esta configuración en cada terminal Java nueva o dejarla configurada en las variables de entorno de Windows. No copiar un entorno virtual de otra computadora.

## 4. Identificar la IP y cambiar los destinos estáticos
En el **servidor** ejecutar:

```powershell
ipconfig
```

Anotar la IPv4 de Wi-Fi o Ethernet de la red compartida; no usar la de Docker, WSL ni una interfaz desconectada. Por ejemplo, `192.168.1.50` es solo un ejemplo: sustituirlo por la IP real. La IP observada anteriormente, `192.168.0.108`, tampoco está confirmada como servidor.

**Cambiar toda IP fija heredada de otra computadora y los `localhost` de los componentes que se conectan a un servidor remoto.** `localhost` significa el equipo que ejecuta el proceso, no el servidor del grupo. La revisión encontró principalmente `localhost`; buscar también otras direcciones incrustadas en la copia actual.

| Archivo | Destino a revisar | Valor para varios equipos |
|---|---|---|
| `sensor_simulador.py` | `BROKER` | IP real del servidor MQTT |
| `mqtt_subscriber.py` | `BROKER` | IP real del servidor MQTT |
| `mqtt_rabbitmq_bridge.py` | Host MQTT, normalmente `BROKER` | IP real del servidor MQTT |
| `mqtt_rabbitmq_bridge.py` | `RABBITMQ_HOST` | IP real del servidor RabbitMQ |
| `fleet-monitor/src/main/resources/application.properties` | `spring.rabbitmq.host` | `127.0.0.1` si Spring y RabbitMQ están en el servidor; IP del broker si están separados |

Ejemplo en Python, respetando los nombres reales de las variables que ya utiliza cada archivo:

```python
BROKER = "192.168.1.50"  # Sustituir por la IP real
RABBITMQ_HOST = "192.168.1.50"  # Solo en el puente
```

Mantener MQTT en 1883 y AMQP en 5672 salvo que se hayan cambiado sus publicaciones. No usar `http://`, puertos ni rutas dentro de las variables de host. Para una prueba íntegramente local se puede usar `127.0.0.1` en todos los destinos. Si el servidor cambia de red o recibe otra IP, actualizar los clientes; una reserva DHCP en el router permite conservar su dirección.

## 5. Preparar Python en cada equipo que ejecute scripts
Desde la raíz del proyecto:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install "paho-mqtt==2.2.0" pika
.\.venv\Scripts\python.exe -c "import paho.mqtt.client, pika; print('Dependencias disponibles')"
```

Si Python 3.13 se instaló sin el lanzador `py`, comprobar `python --version` y usar `python -m venv .venv` con ese intérprete. Los comandos siguientes invocan directamente el Python del entorno virtual; no requieren activar scripts de PowerShell.

Si aparece un error de callbacks de Paho al arrancar, revisar la construcción de `mqtt.Client` y las firmas existentes. Para callbacks de la API histórica, usar `callback_api_version=mqtt.CallbackAPIVersion.VERSION1`, manteniendo `client_id` como argumento con nombre si existe. Si ya usa `VERSION2`, no cambiarlo a VERSION1 sin adaptar las firmas. No actualizar dependencias o callbacks a ciegas.

## 6. Iniciar los brokers en el servidor
Ejecutar desde la raíz. Primero identificar si ya hay un Mosquitto nativo activo:

```powershell
Get-Service -Name mosquitto -ErrorAction SilentlyContinue
Get-NetTCPConnection -State Listen -LocalPort 1883 -ErrorAction SilentlyContinue
docker compose config
```

Elegir **una** de estas opciones; no iniciar dos brokers en el mismo puerto.

### Opción A: Mosquitto nativo ya configurado y en ejecución
Conservarlo si escucha en la IP LAN o en `0.0.0.0:1883` y permite las conexiones de esta práctica. Iniciar únicamente RabbitMQ:

```powershell
docker compose up -d rabbitmq
```

El Mosquitto nativo usa su propia configuración, no necesariamente `mosquitto/config/mosquitto.conf` del repositorio. Si solo acepta conexiones locales, revisar su archivo de servicio y configurar un listener LAN antes de continuar. La configuración de laboratorio de esta copia usa `listener 1883 0.0.0.0` y `allow_anonymous true`; no reemplazar configuraciones compartidas sin revisar sus usos.

### Opción B: ambos brokers en Docker
Usar esta opción en una instalación nueva sin otro proceso ocupando 1883. El archivo `mosquitto/config/mosquitto.conf` debe contener la configuración de laboratorio existente:

```text
listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data
```

Preparar el directorio de datos e iniciar ambos servicios:

```powershell
New-Item -ItemType Directory -Force .\mosquitto\data
docker compose up -d mosquitto rabbitmq
```

Si se decide sustituir un Mosquitto nativo por el contenedor, detener primero el servicio nativo desde PowerShell como administrador, únicamente si no lo usan otros proyectos:

```powershell
Stop-Service -Name mosquitto
```

### Comprobación común

```powershell
docker compose ps
docker compose logs --tail 50 rabbitmq
docker compose exec rabbitmq rabbitmq-diagnostics -q ping
```

Esperar hasta que el diagnóstico responda correctamente. Si se usa Mosquitto Docker, revisar también `docker compose logs --tail 50 mosquitto`. La advertencia de Compose sobre `version` obsoleta no equivale a un fallo de arranque.

## 7. Crear el usuario RabbitMQ y configurar las aplicaciones
No usar `guest` para conexiones remotas: está restringido a conexiones locales del broker. Incluso el acceso desde el host a un contenedor puede no considerarse local para esa restricción.

En el servidor crear una cuenta de laboratorio. El primer comando solicita la contraseña de forma interactiva; usar una contraseña propia y conservarla fuera del repositorio:

```powershell
docker compose exec rabbitmq rabbitmqctl add_user flota
docker compose exec rabbitmq rabbitmqctl set_user_tags flota administrator
docker compose exec rabbitmq rabbitmqctl set_permissions -p / flota ".*" ".*" ".*"
docker compose exec rabbitmq rabbitmqctl list_users
```

Si `flota` ya existe, no repetir su creación: utilizar la contraseña válida. La cuenta administradora se usa aquí para la demostración y la interfaz; en un despliegue permanente separar la administración de las cuentas de aplicación.

### Puente Python
Cambiar únicamente la creación de los parámetros de conexión a RabbitMQ para que use este usuario. Añadir `import os` y usar este patrón, **conservando los nombres de las variables de conexión y canal del archivo original**:

```python
credenciales = pika.PlainCredentials(
    os.environ["RABBITMQ_USER"],
    os.environ["RABBITMQ_PASSWORD"],
)
parametros = pika.ConnectionParameters(
    host=RABBITMQ_HOST,
    port=5672,
    virtual_host="/",
    credentials=credenciales,
)
# En la asignación de conexión existente, reemplazar únicamente
# pika.BlockingConnection(...) por pika.BlockingConnection(parametros).
# Conservar después la creación del canal y toda la lógica del puente.
```

No basta cambiar `RABBITMQ_HOST` si el puente sigue usando las credenciales predeterminadas. No cambiar las colas, los umbrales ni la lógica de publicación para configurar el acceso.

### Spring Boot
Conservar `spring.application.name=fleet-monitor` y añadir o actualizar, sin duplicar claves, en `fleet-monitor/src/main/resources/application.properties`:

```properties
spring.rabbitmq.host=${RABBITMQ_HOST:127.0.0.1}
spring.rabbitmq.port=5672
spring.rabbitmq.username=${RABBITMQ_USER}
spring.rabbitmq.password=${RABBITMQ_PASSWORD}
server.address=0.0.0.0
server.port=8080
```

Estas propiedades leen las variables del proceso; no implican que Python o Spring carguen automáticamente un archivo `.env`. Las variables se establecerán en las terminales de arranque. Spring se ejecuta directamente en Windows; no usar aquí un nombre de servicio Docker como host.

## 8. Comprobar conexión entre computadoras
Conectar los equipos a la misma red, sin aislamiento de clientes. En cada cliente, definir la IP real y comprobar:

```powershell
$ipServidor = '<IP_REAL_DEL_SERVIDOR>'
Test-NetConnection $ipServidor -Port 1883
Test-NetConnection $ipServidor -Port 5672
Test-NetConnection $ipServidor -Port 15672
```

Cada puerto necesario debe mostrar `TcpTestSucceeded : True`. Si falla, comprobar primero los servicios y sus puertos publicados. Si funcionan localmente y Windows bloquea el acceso remoto, en el **servidor**, con PowerShell como administrador y en una red privada de confianza, crear una regla limitada a la subred local:

```powershell
New-NetFirewallRule -DisplayName 'Flota laboratorio TCP' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 1883,5672,15672,8080 -Profile Private -RemoteAddress LocalSubnet
```

No desactivar el firewall. Una red pública o Wi-Fi con aislamiento puede seguir bloqueando las conexiones. El puerto 8080 se comprueba después de iniciar Spring. Usar la IP real: que Docker funcione no confirma acceso desde los demás equipos.

## 9. Abrir RabbitMQ
En el servidor abrir [http://localhost:15672](http://localhost:15672). Desde otra computadora abrir `http://IP_REAL_DEL_SERVIDOR:15672`. Iniciar sesión con `flota` y la contraseña creada.

La interfaz corre en el servidor, pero puede verse desde los clientes. El puerto 15672 es para administración web; las aplicaciones AMQP usan 5672. Ver el login confirma acceso a la interfaz, no el funcionamiento completo del proyecto.

## 10. Compilar e iniciar Spring Boot — terminal 1 del servidor
Abrir PowerShell en la raíz y configurar el JDK del paso 3 si hace falta. Establecer las variables en esta misma terminal:

```powershell
$env:RABBITMQ_HOST = '127.0.0.1'
$env:RABBITMQ_USER = 'flota'
$env:RABBITMQ_PASSWORD = [System.Net.NetworkCredential]::new('', (Read-Host 'Contraseña RabbitMQ' -AsSecureString)).Password
cd .\fleet-monitor
.\mvnw.cmd -version
.\mvnw.cmd test
```

Maven debe identificar el JDK correcto y terminar las pruebas con `BUILD SUCCESS`. No continuar ocultando errores o saltando pruebas. Si las pruebas necesitan el broker, debe estar activo y usar las variables anteriores. Después:

```powershell
.\mvnw.cmd spring-boot:run
```

Dejar la terminal abierta. Esperar el mensaje de aplicación iniciada y comprobar que no haya errores repetidos de conexión o autenticación AMQP. Si Spring corre en otra computadora, usar la IP del servidor RabbitMQ en `RABBITMQ_HOST`.

En RabbitMQ comprobar las cuatro colas y `exchange.fleet`. Las colas son `cola.gps.telemetria`, `cola.alertas.temperatura`, `cola.combustible.nivel` y `cola.notificaciones`.

## 11. Iniciar el puente — terminal 2
Abrir otra PowerShell en la raíz del proyecto, en el equipo elegido para el puente. Confirmar que los hosts Python apuntan al servidor. Establecer las credenciales en esta terminal:

```powershell
$env:RABBITMQ_USER = 'flota'
$env:RABBITMQ_PASSWORD = [System.Net.NetworkCredential]::new('', (Read-Host 'Contraseña RabbitMQ' -AsSecureString)).Password
.\.venv\Scripts\python.exe .\mqtt_rabbitmq_bridge.py
```

Dejarlo ejecutándose. Debe conectarse a MQTT y RabbitMQ sin errores. Si muestra una excepción, resolverla antes de arrancar sensores. Las variables de una terminal no se transmiten a otras ya abiertas.

## 12. Iniciar sensores y almacenamiento opcional
En otra PowerShell, desde la raíz del equipo de sensores:

```powershell
.\.venv\Scripts\python.exe .\sensor_simulador.py
```

El simulador publica GPS, temperatura y combustible de `VH-001`, `VH-002` y `VH-003` aproximadamente cada 5 segundos. Dejarlo ejecutándose.

Si se desea almacenamiento SQLite, abrir otra terminal en la raíz e iniciar:

```powershell
.\.venv\Scripts\python.exe .\mqtt_subscriber.py
```

El suscriptor crea `telemetria.db` en su directorio de trabajo. SQLite se guarda en el equipo donde se ejecuta este script y es independiente de Spring y de la API. Para capturar desde el primer mensaje, iniciar este suscriptor antes del simulador.

## 13. Comprobar que pasan mensajes
### MQTT
Si se dispone de las herramientas de Mosquitto, observar desde otra terminal:

```powershell
mosquitto_sub -h <IP_REAL_DEL_SERVIDOR> -t 'flota/#' -v
```

Deben aparecer topics como `flota/VH-001/gps` y sus JSON. Si Windows no reconoce `mosquitto_sub`, usar la ruta real del ejecutable; no significa que el broker esté fallando.

### RabbitMQ y Spring
En la interfaz abrir **Queues and Streams** (o **Queues**, según la versión). Verificar tasas de publicación/entrega y consumidores. En la consola Spring deben aparecer logs de GPS y, al generarse los umbrales, alertas. Una cola GPS en cero puede ser normal si Spring consume inmediatamente.

El puente genera alertas si `temperature > 4` o `fuel_level < 20`. Como el simulador genera valores aleatorios, las alertas no aparecen en todas las iteraciones. Para una comprobación reproducible, exclusivamente en este laboratorio, con el puente y Spring activos, publicar dos mensajes de prueba desde un equipo con el entorno Python preparado:

```powershell
$env:MQTT_TEST_HOST = '<IP_REAL_DEL_SERVIDOR>'
@'
import json, os
from datetime import datetime, timezone
import paho.mqtt.publish as publish
base = {"vehicle_id": "VH-TEST", "timestamp": datetime.now(timezone.utc).isoformat()}
for tipo, datos in [
    ("temperatura", {"temperature": 8, "unit": "C"}),
    ("combustible", {"fuel_level": 10, "unit": "%"}),
]:
    publish.single(f"flota/VH-TEST/{tipo}", json.dumps({**base, **datos}),
                   hostname=os.environ["MQTT_TEST_HOST"], port=1883, qos=1)
print("Mensajes de prueba publicados")
'@ | .\.venv\Scripts\python.exe -
```

Comprobar las dos alertas en los logs Spring y el aumento de mensajes en `cola.notificaciones`. El mensaje de Python solo confirma publicación al broker MQTT; la confirmación del recorrido requiere los logs y la cola. Actualmente no hay consumidor final de notificaciones: los mensajes pueden acumularse. No usar la opción de obtener mensajes de la interfaz como si fuera una consulta inocua; puede consumirlos según el modo elegido.

El puente actual publica mediante el exchange por defecto (`exchange=""`) usando el nombre de cola como routing key. `exchange.fleet` y sus bindings existen en Spring, pero no participan en esa publicación. No cambiar esa lógica para resolver un problema de IP.

### API REST
En otra terminal del servidor:

```powershell
Invoke-RestMethod 'http://localhost:8080/api/fleet/status'
Invoke-RestMethod 'http://localhost:8080/api/fleet/vehicle/VH-001/telemetria'
```

Desde un cliente, usar la IP real en lugar de `localhost`. Comprobar también `Test-NetConnection <IP_REAL_DEL_SERVIDOR> -Port 8080`.

La API actual devuelve `totalVehicles=3`, `activeAlerts=2` y una marca de tiempo en `/status`; la otra ruta devuelve un texto de ejemplo. Obtener estas respuestas demuestra que HTTP funciona, **no que la API consulte la telemetría de RabbitMQ o SQLite**.

## 14. Criterios de funcionamiento

| Verificación | Resultado esperado |
|---|---|
| Docker | Motor disponible y RabbitMQ activo |
| MQTT desde otro equipo | Puerto 1883 accesible y JSON visibles |
| RabbitMQ web | Login accesible y usuario válido |
| Puente | Conectado a ambos brokers, sin excepciones |
| Spring | Aplicación iniciada y consumidores activos |
| GPS | Mensajes de GPS registrados en Spring |
| Alertas | Temperatura/combustible registrados y reenviados a notificaciones |
| API | Ambas rutas responden con los ejemplos actuales |
| SQLite opcional | Base local con registros tras recibir mensajes |

No declarar la práctica completa únicamente por abrir RabbitMQ. Guardar evidencias de cada etapa y registrar cualquier paso que no se haya podido comprobar.

## 15. Problemas frecuentes

| Síntoma | Qué revisar |
|---|---|
| Docker no conecta con `dockerDesktopLinuxEngine` | Abrir Docker Desktop, esperar al motor y verificar WSL/contenedores Linux |
| `address already in use` en 1883 | Mosquitto nativo y contenedor compiten; elegir uno |
| `Connection refused` en MQTT/AMQP | Servicio apagado, host incorrecto o puerto no publicado |
| Timeout remoto | IP, firewall, red compartida y aislamiento Wi-Fi |
| RabbitMQ rechaza `guest` | Usar `flota` en puente y Spring con permisos sobre `/` |
| Login o AMQP rechaza `flota` | Contraseña, existencia del usuario y permisos; comprobar en el servidor |
| `ModuleNotFoundError: pika` | Instalar con el Python de `.venv` del mismo equipo |
| Error de Paho/callback | Versión de API y firmas del paso 5 |
| Java 8 o errores de compilación por versión | Corregir `JAVA_HOME` y PATH; comprobar `mvnw.cmd -version` |
| Maven no descarga un artefacto | Revisar Internet, proxy, coordenadas y versión real del `pom.xml`; no cambiar versiones arbitrariamente |
| `PRECONDITION_FAILED` al declarar una cola | Comparar durabilidad/argumentos de la cola existente; no purgarla ni borrarla para ocultar el problema |
| No llegan alertas | Confirmar umbrales y probar los mensajes controlados del paso 13 |
| Colas sin mensajes visibles | Revisar tasas y logs: consumidores rápidos pueden dejarlas vacías |
| API sigue mostrando valores fijos | Es el comportamiento actual del controlador, no un problema de IP |

## 16. Detener y volver a ejecutar
Detener primero el simulador, después el puente/suscriptor y finalmente Spring con `Ctrl+C` en cada terminal. En el servidor detener solo los contenedores de esta práctica:

```powershell
docker compose stop rabbitmq
```

Si Mosquitto también se ejecuta en este Compose:

```powershell
docker compose stop mosquitto
```

Para la siguiente sesión, abrir Docker Desktop, iniciar los brokers, volver a definir las variables de cada terminal y seguir Spring → puente → sensores. `stop` conserva los contenedores. La copia revisada no declara almacenamiento persistente de RabbitMQ mediante un volumen: no asumir conservación de mensajes al eliminar/recrear el contenedor. No utilizar `down -v` como limpieza habitual.

## 17. Alcance actual y documentación oficial
El proyecto contiene mensajería, logs GPS, reenvío de alertas, API de ejemplo y un suscriptor SQLite independiente. No incluye frontend, persistencia GPS en Spring, consulta de telemetría real desde la API ni procesamiento final de notificaciones. Esta guía describe la configuración necesaria; no modifica esos componentes. La configuración MQTT anónima indicada corresponde a una red de laboratorio y no debe exponerse directamente a Internet.

- [RabbitMQ: interfaz de administración](https://www.rabbitmq.com/docs/management)
- [RabbitMQ: usuarios y permisos](https://www.rabbitmq.com/docs/access-control)
- [Spring Boot: requisitos](https://docs.spring.io/spring-boot/system-requirements.html)
- [Paho MQTT: migración de callbacks](https://eclipse.dev/paho/files/paho.mqtt.python/html/migrations.html)
- [Mosquitto: configuración](https://mosquitto.org/man/mosquitto-conf-5.html)

Esta guía se reconstruyó a partir de `explicacion_practica.md` y `revision_funcionamiento.md`. La ejecución debe validarse sobre la versión concreta del repositorio antes de presentarla como instalación probada.
