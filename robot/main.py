#!/usr/bin/env pybricks-micropython
"""
main.py — Punto de entrada del robot de reparto EV3.

Flujo principal:
1. Inicializar hardware
2. Conectar al broker MQTT
3. Recibir y parsear el mapa de la ciudad
4. Esperar pedidos de la aplicación cliente
5. Para cada pedido: navegar → recoger → navegar → entregar
6. Publicar odometría continuamente (≥1 Hz)

Equipo F — Inteligencia Ambiental
"""

from pybricks.parameters import Color
from pybricks.tools import wait, StopWatch

from hardware import RobotHardware
from map_parser import CityMap
from navigation import Navigator
from mqtt_client import RobotMQTTClient


# =============================================================================
# CONFIGURACIÓN
# =============================================================================

# Usar seguimiento de línea (True = Categoría C, False = Categoría A/B)
USE_LINE_FOLLOWING = True  # Categoría C — seguir trazado de calles

# Tiempo máximo de espera para el mapa (ms)
MAP_TIMEOUT_MS = 120000


def main():
    """Función principal del robot de reparto."""

    # =========================================================================
    # PASO 1: Inicializar hardware
    # =========================================================================
    print("=" * 40)
    print("Robot de Reparto - Equipo F")
    print("=" * 40)
    print("Inicializando hardware...")

    robot = RobotHardware()
    robot.display_text("Iniciando...")
    robot.set_light(Color.ORANGE)

    # =========================================================================
    # PASO 2: Conectar al broker MQTT
    # =========================================================================
    print("Conectando al broker MQTT...")
    robot.display_text("Conectando MQTT...")

    mqtt = RobotMQTTClient()
    connected = mqtt.connect()

    if not connected:
        robot.display_text("Error MQTT!")
        robot.set_light(Color.RED)
        robot.beep(200, 1000)
        print("ERROR: No se pudo conectar al broker MQTT")
        # Continuar sin MQTT para pruebas locales
        print("Continuando sin MQTT...")

    # =========================================================================
    # PASO 3: Recibir y parsear el mapa
    # =========================================================================
    print("Esperando mapa del servidor...")
    robot.display_text("Esperando mapa...")

    city_map = CityMap()

    if connected:
        mqtt.subscribe_map()
        mqtt.subscribe_orders()

        map_string = mqtt.wait_for_map(timeout_ms=MAP_TIMEOUT_MS)

        if map_string:
            city_map.parse(map_string)
            print("Mapa parseado correctamente")
            city_map.print_map()
            print("Puntos de recogida/entrega: {}".format(city_map.pickup_points))
        else:
            print("Timeout esperando mapa. Usando mapa por defecto.")
            load_default_map(city_map)
    else:
        print("Sin MQTT. Usando mapa por defecto.")
        load_default_map(city_map)

    robot.display_text("Mapa OK!")
    robot.set_light(Color.GREEN)
    robot.beep(600, 200)
    wait(200)
    robot.beep(800, 200)

    # =========================================================================
    # PASO 4: Inicializar navegador
    # =========================================================================
    navigator = Navigator(robot, city_map)
    print("Navegador inicializado")
    print("Posición inicial: {}".format(navigator.current_pos))
    print("Orientación: {}".format(navigator.current_heading))

    # Publicar estado inicial
    if connected:
        mqtt.publish_status('idle')
        mqtt.publish_odometry(navigator.get_state())

    # =========================================================================
    # PASO 5: Bucle principal — Esperar y ejecutar pedidos
    # =========================================================================
    print("\nEsperando pedidos...")
    robot.display_text("Listo!")

    odometry_timer = StopWatch()
    order_count = 0

    while True:
        # Publicar odometría periódicamente
        if connected and odometry_timer.time() >= 500:
            mqtt.publish_odometry(navigator.get_state())
            odometry_timer.reset()

        # Comprobar mensajes MQTT
        if connected:
            mqtt.check_messages()

        # Obtener siguiente pedido
        order = None
        if connected:
            order = mqtt.get_next_order()

        if order:
            order_count += 1
            print("\n--- Pedido #{} ---".format(order_count))
            print("Recogida: {}".format(order.get('pickup', '?')))
            print("Entrega: {}".format(order.get('delivery', '?')))

            # Ejecutar el pedido
            execute_order(robot, navigator, mqtt, order, connected, odometry_timer)

            # Volver a estado idle
            if connected:
                mqtt.publish_status('idle')
            robot.display_text("Listo!")
            robot.set_light(Color.GREEN)
            print("Pedido #{} completado!".format(order_count))

        # Comprobar si se pulsa un botón (para pruebas sin MQTT)
        if robot.is_button_pressed() and not connected:
            print("\nPrueba manual iniciada!")
            test_manual(robot, navigator)

        wait(50)


def execute_order(robot, navigator, mqtt, order, connected, odometry_timer):
    """
    Ejecuta un pedido completo: ir a recoger y luego entregar.

    Args:
        robot: RobotHardware
        navigator: Navigator
        mqtt: RobotMQTTClient
        order: Dict con 'pickup' [row, col] y 'delivery' [row, col]
        connected: Bool si MQTT está conectado
        odometry_timer: StopWatch para odometría
    """
    pickup = tuple(order.get('pickup', [0, 0]))
    delivery = tuple(order.get('delivery', [0, 0]))

    # Callback para publicar odometría durante la navegación
    def on_block(row, col):
        if connected:
            mqtt.publish_odometry(navigator.get_state())
            odometry_timer.reset()

    # --- FASE 1: Ir al punto de recogida ---
    print("Navegando a punto de recogida: {}".format(pickup))
    robot.display_text("Recogida...")
    robot.set_light(Color.ORANGE)

    if connected:
        mqtt.publish_status('navigating_pickup', {
            'pickup': list(pickup),
            'delivery': list(delivery)
        })

    success = navigator.navigate_to(
        pickup,
        use_line_following=USE_LINE_FOLLOWING,
        on_block_callback=on_block
    )

    if not success:
        print("ERROR: No se pudo llegar al punto de recogida")
        robot.set_light(Color.RED)
        if connected:
            mqtt.publish_status('error', {'message': 'No route to pickup'})
        return

    # --- FASE 2: Recoger paquete ---
    print("Recogiendo paquete...")
    if connected:
        mqtt.publish_status('picking_up')
    navigator.pickup_package()

    # --- FASE 3: Ir al punto de entrega ---
    print("Navegando a punto de entrega: {}".format(delivery))
    robot.display_text("Entrega...")

    if connected:
        mqtt.publish_status('navigating_delivery', {
            'pickup': list(pickup),
            'delivery': list(delivery)
        })

    success = navigator.navigate_to(
        delivery,
        use_line_following=USE_LINE_FOLLOWING,
        on_block_callback=on_block
    )

    if not success:
        print("ERROR: No se pudo llegar al punto de entrega")
        robot.set_light(Color.RED)
        if connected:
            mqtt.publish_status('error', {'message': 'No route to delivery'})
        return

    # --- FASE 4: Entregar paquete ---
    print("Entregando paquete...")
    if connected:
        mqtt.publish_status('delivering')
    navigator.deliver_package()

    if connected:
        mqtt.publish_status('completed', {
            'pickup': list(pickup),
            'delivery': list(delivery)
        })

    robot.set_light(Color.GREEN)
    robot.beep(1000, 200)
    wait(100)
    robot.beep(1200, 200)
    wait(100)
    robot.beep(1500, 300)


def load_default_map(city_map):
    """Carga el mapa de ejemplo de las primeras pruebas."""
    # Mapa de la Figura 8 del enunciado
    # Grid 5 filas x 7 columnas
    # Fila 0: 02 02 00 01 05 03 07
    # Fila 1: 02 00 00 00 02 02 08
    # Fila 2: 08 01 01 00 10 00 02
    # Fila 3: 02 00 00 00 02 00 02
    # Fila 4: 04 01 07 01 09 01 06
    default_map = "02020001050307020000000202080101010000100002000000020002040107010901060107010701"

    # Nota: Esta cadena es una estimación del mapa de ejemplo.
    # El mapa real se obtiene del servidor MQTT.
    # Si no coincide con el mapa real, ajustar según la Figura 8.

    city_map.parse(default_map)
    print("Mapa por defecto cargado")


def test_manual(robot, navigator):
    """
    Modo de prueba manual sin MQTT.
    Ejecuta una secuencia de prueba básica.
    """
    robot.display_text("Prueba manual")
    print("Prueba: avanzar 1 bloque, girar 90, avanzar 1 bloque")

    navigator.move_one_block()
    wait(500)

    navigator.turn_to_direction('right')
    wait(500)

    navigator.move_one_block()
    wait(500)

    robot.display_text("Prueba OK!")
    robot.beep(800, 300)


# Punto de entrada
main()
