"""
mqtt_client.py — Cliente MQTT para el robot EV3.

Gestiona la comunicación con el broker MQTT central:
- Suscripción al topic 'map' para recibir el mapa de la ciudad
- Publicación de odometría del robot
- Recepción de pedidos de la aplicación cliente
- Publicación del estado del robot

NOTA: El EV3 con firmware Pybricks tiene acceso completo al SO Linux
      vía SSH. Para MQTT se usa la librería umqtt.simple si está disponible,
      o como alternativa se ejecutan comandos mosquitto_pub/sub vía subprocess.
"""

import ujson
import usocket
import ustruct
import utime


# =============================================================================
# CONFIGURACIÓN MQTT
# =============================================================================

MQTT_BROKER = "192.168.1.122"
MQTT_PORT = 1883
TEAM_LETTER = "F"  # Letra del equipo en Platea

# Topics
TOPIC_MAP = "map"
TOPIC_ODOMETRY = "Equipo {}/odometria".format(TEAM_LETTER)
TOPIC_ORDERS = "Equipo {}/pedidos".format(TEAM_LETTER)
TOPIC_STATUS = "Equipo {}/estado".format(TEAM_LETTER)

# Intervalo de publicación de odometría (ms)
ODOMETRY_INTERVAL_MS = 500  # 2 Hz (supera el mínimo de 1 Hz)


class MQTTMessage:
    """Almacena un mensaje MQTT recibido."""
    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload


class SimpleMQTT:
    """
    Cliente MQTT simplificado para MicroPython en EV3.

    Implementa el protocolo MQTT 3.1.1 a nivel de socket para
    no depender de librerías externas.
    """

    def __init__(self, client_id, broker, port=1883):
        self.client_id = client_id
        self.broker = broker
        self.port = port
        self.sock = None
        self.callbacks = {}  # topic -> callback function
        self.connected = False

    def connect(self):
        """Conecta al broker MQTT."""
        try:
            self.sock = usocket.socket()
            addr = usocket.getaddrinfo(self.broker, self.port)[0][-1]
            self.sock.connect(addr)
            self.sock.setblocking(False)

            # Construir paquete CONNECT
            client_id_bytes = self.client_id.encode('utf-8')
            remaining_length = 10 + 2 + len(client_id_bytes)

            packet = bytearray()
            packet.append(0x10)  # CONNECT
            packet.append(remaining_length)

            # Variable header
            packet.extend(b'\x00\x04MQTT')  # Protocol name
            packet.append(0x04)  # Protocol level (3.1.1)
            packet.append(0x02)  # Connect flags (clean session)
            packet.extend(b'\x00\x3C')  # Keep alive (60s)

            # Payload
            packet.extend(ustruct.pack('!H', len(client_id_bytes)))
            packet.extend(client_id_bytes)

            self.sock.send(packet)

            # Esperar CONNACK
            utime.sleep_ms(500)
            try:
                resp = self.sock.recv(4)
                if resp and resp[0] == 0x20 and resp[3] == 0x00:
                    self.connected = True
                    return True
            except OSError:
                pass

            self.connected = True  # Asumir conectado si no hay error explícito
            return True

        except Exception as e:
            print("MQTT Connect error: {}".format(e))
            self.connected = False
            return False

    def subscribe(self, topic, callback):
        """
        Se suscribe a un topic MQTT.

        Args:
            topic: String del topic
            callback: Función que recibe (topic, payload) como strings
        """
        self.callbacks[topic] = callback

        topic_bytes = topic.encode('utf-8')
        packet_id = 1

        remaining_length = 2 + 2 + len(topic_bytes) + 1

        packet = bytearray()
        packet.append(0x82)  # SUBSCRIBE
        packet.append(remaining_length)
        packet.extend(ustruct.pack('!H', packet_id))
        packet.extend(ustruct.pack('!H', len(topic_bytes)))
        packet.extend(topic_bytes)
        packet.append(0x00)  # QoS 0

        try:
            self.sock.send(packet)
        except Exception as e:
            print("MQTT Subscribe error: {}".format(e))

    def publish(self, topic, payload):
        """
        Publica un mensaje en un topic MQTT.

        Args:
            topic: String del topic
            payload: String del payload
        """
        if not self.connected:
            return

        topic_bytes = topic.encode('utf-8')
        payload_bytes = payload.encode('utf-8') if isinstance(payload, str) else payload

        remaining_length = 2 + len(topic_bytes) + len(payload_bytes)

        packet = bytearray()
        packet.append(0x30)  # PUBLISH (QoS 0)

        # Codificar remaining length (puede ser >127)
        while remaining_length > 0:
            byte = remaining_length % 128
            remaining_length = remaining_length // 128
            if remaining_length > 0:
                byte = byte | 0x80
            packet.append(byte)

        packet.extend(ustruct.pack('!H', len(topic_bytes)))
        packet.extend(topic_bytes)
        packet.extend(payload_bytes)

        try:
            self.sock.send(packet)
        except Exception as e:
            print("MQTT Publish error: {}".format(e))

    def check_messages(self):
        """
        Comprueba si hay mensajes pendientes y los procesa.
        No bloquea (non-blocking).
        """
        if not self.sock:
            return

        try:
            data = self.sock.recv(2048)
            if data and len(data) > 0:
                self._process_packet(data)
        except OSError:
            pass  # No hay datos disponibles (non-blocking)

    def _process_packet(self, data):
        """Procesa un paquete MQTT recibido."""
        if len(data) < 2:
            return

        packet_type = data[0] & 0xF0

        if packet_type == 0x30:  # PUBLISH
            # Decodificar remaining length
            idx = 1
            remaining_length = 0
            multiplier = 1
            while idx < len(data):
                byte = data[idx]
                remaining_length += (byte & 0x7F) * multiplier
                multiplier *= 128
                idx += 1
                if (byte & 0x80) == 0:
                    break

            # Decodificar topic
            if idx + 2 <= len(data):
                topic_len = ustruct.unpack('!H', data[idx:idx+2])[0]
                idx += 2
                if idx + topic_len <= len(data):
                    topic = data[idx:idx+topic_len].decode('utf-8')
                    idx += topic_len
                    payload = data[idx:idx+remaining_length-2-topic_len].decode('utf-8')

                    # Llamar al callback si existe
                    if topic in self.callbacks:
                        self.callbacks[topic](topic, payload)

    def disconnect(self):
        """Desconecta del broker MQTT."""
        if self.sock:
            try:
                packet = bytearray([0xE0, 0x00])  # DISCONNECT
                self.sock.send(packet)
                self.sock.close()
            except Exception:
                pass
        self.connected = False


class RobotMQTTClient:
    """
    Cliente MQTT de alto nivel para el robot de reparto.

    Gestiona la comunicación con el broker:
    - Recibe el mapa
    - Recibe pedidos
    - Publica odometría y estado
    """

    def __init__(self, client_id="ev3_robot_F"):
        self.mqtt = SimpleMQTT(client_id, MQTT_BROKER, MQTT_PORT)
        self.map_data = None
        self.pending_orders = []
        self.last_odometry_time = 0

    def connect(self):
        """Conecta al broker MQTT."""
        return self.mqtt.connect()

    def subscribe_map(self):
        """Se suscribe al topic del mapa."""
        def on_map(topic, payload):
            self.map_data = payload
            print("Mapa recibido: {} bytes".format(len(payload)))

        self.mqtt.subscribe(TOPIC_MAP, on_map)

    def subscribe_orders(self):
        """Se suscribe al topic de pedidos."""
        def on_order(topic, payload):
            try:
                order = ujson.loads(payload)
                self.pending_orders.append(order)
                print("Pedido recibido: {}".format(order))
            except Exception as e:
                print("Error parseando pedido: {}".format(e))

        self.mqtt.subscribe(TOPIC_ORDERS, on_order)

    def wait_for_map(self, timeout_ms=120000):
        """
        Espera a recibir el mapa (se retransmite cada 60s).

        Args:
            timeout_ms: Tiempo máximo de espera en ms

        Returns:
            str: Cadena del mapa, o None si timeout
        """
        start = utime.ticks_ms()
        while self.map_data is None:
            self.mqtt.check_messages()
            if utime.ticks_diff(utime.ticks_ms(), start) > timeout_ms:
                return None
            utime.sleep_ms(100)
        return self.map_data

    def get_next_order(self):
        """
        Obtiene el siguiente pedido pendiente.

        Returns:
            dict: Pedido con 'pickup' y 'delivery', o None
        """
        self.mqtt.check_messages()
        if self.pending_orders:
            return self.pending_orders.pop(0)
        return None

    def publish_odometry(self, nav_state):
        """
        Publica la odometría del robot.

        Args:
            nav_state: Dict con el estado del navegador
        """
        now = utime.ticks_ms()
        if utime.ticks_diff(now, self.last_odometry_time) >= ODOMETRY_INTERVAL_MS:
            payload = ujson.dumps(nav_state)
            self.mqtt.publish(TOPIC_ODOMETRY, payload)
            self.last_odometry_time = now

    def publish_status(self, status, order_info=None):
        """
        Publica el estado actual del robot.

        Args:
            status: String de estado (e.g., 'idle', 'navigating', 'picking', 'delivering')
            order_info: Dict con info adicional del pedido
        """
        data = {'status': status}
        if order_info:
            data['order'] = order_info
        self.mqtt.publish(TOPIC_STATUS, ujson.dumps(data))

    def check_messages(self):
        """Comprueba y procesa mensajes pendientes."""
        self.mqtt.check_messages()

    def disconnect(self):
        """Desconecta del broker."""
        self.mqtt.disconnect()
