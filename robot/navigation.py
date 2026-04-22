"""
navigation.py — Pathfinding y control de navegación del robot.

Implementa:
- Algoritmo BFS/A* para encontrar la ruta óptima entre dos puntos del mapa
- Control de navegación bloque a bloque
- Seguimiento de línea con controlador PID proporcional (Categoría C)
- Gestión de la orientación del robot
"""

from map_parser import (
    CityMap, UP, DOWN, LEFT, RIGHT,
    DIRECTION_DELTA, OPPOSITE, BLOCK_SIZE_MM
)


# Mapeo de dirección a ángulo absoluto (0 = arriba, 90 = derecha, etc.)
DIRECTION_TO_ANGLE = {
    UP:    0,
    RIGHT: 90,
    DOWN:  180,
    LEFT:  270,
}

ANGLE_TO_DIRECTION = {v: k for k, v in DIRECTION_TO_ANGLE.items()}


class PathFinder:
    """Algoritmo de búsqueda de rutas sobre el mapa de la ciudad."""

    def __init__(self, city_map):
        """
        Args:
            city_map: Instancia de CityMap con el mapa parseado.
        """
        self.city_map = city_map

    def find_path(self, start, goal):
        """
        Encuentra la ruta más corta entre dos posiciones usando BFS.

        Args:
            start: Tupla (fila, columna) de inicio
            goal: Tupla (fila, columna) de destino

        Returns:
            list: Lista de tuplas (fila, columna) que forman la ruta,
                  incluyendo inicio y destino. Lista vacía si no hay ruta.
        """
        if start == goal:
            return [start]

        # BFS
        queue = [start]
        visited = {start: None}  # nodo -> nodo padre

        while queue:
            current = queue.pop(0)  # FIFO (no hay deque en MicroPython)

            if current == goal:
                # Reconstruir la ruta
                path = []
                node = goal
                while node is not None:
                    path.append(node)
                    node = visited[node]
                path.reverse()
                return path

            for neighbor in self.city_map.get_neighbors(current[0], current[1]):
                if neighbor not in visited:
                    visited[neighbor] = current
                    queue.append(neighbor)

        return []  # No se encontró ruta

    def get_directions(self, path):
        """
        Convierte una ruta (lista de posiciones) en una lista de direcciones.

        Args:
            path: Lista de tuplas (fila, columna)

        Returns:
            list: Lista de direcciones (UP, DOWN, LEFT, RIGHT)
        """
        directions = []
        for i in range(len(path) - 1):
            direction = self.city_map.get_direction_to(path[i], path[i + 1])
            if direction:
                directions.append(direction)
        return directions


class Navigator:
    """Controla la navegación física del robot sobre el mapa."""

    def __init__(self, robot_hw, city_map):
        """
        Args:
            robot_hw: Instancia de RobotHardware
            city_map: Instancia de CityMap
        """
        self.robot = robot_hw
        self.city_map = city_map
        self.pathfinder = PathFinder(city_map)

        # Estado de navegación
        self.current_pos = city_map.start_position  # (fila, col)
        self.current_heading = UP  # Orientación inicial: mirando hacia arriba
        self.current_heading_angle = 0  # 0 = arriba

    # =========================================================================
    # SEGUIMIENTO DE LÍNEA (Categoría C)
    # =========================================================================

    # Constantes para el controlador PID de seguimiento de línea
    LINE_BLACK = 9          # Reflectancia de la línea negra (CALIBRAR)
    LINE_WHITE = 85         # Reflectancia de la superficie blanca (CALIBRAR)
    LINE_THRESHOLD = 47     # Umbral = (BLACK + WHITE) / 2
    PROPORTIONAL_GAIN = 1.2  # Ganancia proporcional del PID
    LINE_SPEED = 100        # Velocidad de seguimiento de línea (mm/s)

    # Reflectancia del cuadrado negro central (punto de referencia)
    BLACK_SQUARE_THRESHOLD = 15  # Por debajo de este valor = cuadrado negro

    def follow_line_to_next_block(self):
        """
        Sigue la línea hasta el centro del siguiente bloque.
        Detecta el cuadrado negro central como punto de parada.

        Returns:
            bool: True si llegó al centro del siguiente bloque
        """
        from pybricks.tools import wait, StopWatch

        timer = StopWatch()
        black_detected = False
        min_distance = 100  # mm mínimo antes de buscar el cuadrado negro

        self.robot.reset_odometry()

        while True:
            reflection = self.robot.read_reflection()

            # Controlador proporcional para seguimiento de línea
            deviation = reflection - self.LINE_THRESHOLD
            turn_rate = self.PROPORTIONAL_GAIN * deviation
            self.robot.drive(self.LINE_SPEED, turn_rate)

            distance = abs(self.robot.get_distance())

            # Buscar el cuadrado negro central después de recorrer una distancia mínima
            if distance > min_distance and reflection < self.BLACK_SQUARE_THRESHOLD:
                if not black_detected:
                    black_detected = True
                    # Avanzar un poco más para centrarse en el bloque
                    self.robot.stop()
                    self.robot.move_straight(30)  # Ajuste fino (CALIBRAR)
                    return True

            # Timeout de seguridad: si recorremos más de 2 bloques sin detectar, parar
            if distance > BLOCK_SIZE_MM * 2:
                self.robot.stop()
                return False

            wait(10)

    # =========================================================================
    # NAVEGACIÓN BLOQUE A BLOQUE (sin seguimiento de línea)
    # =========================================================================

    def move_one_block(self):
        """Avanza exactamente un bloque usando odometría."""
        self.robot.move_straight(BLOCK_SIZE_MM)

    def turn_to_direction(self, target_direction):
        """
        Gira el robot para que mire en la dirección objetivo.

        Args:
            target_direction: UP, DOWN, LEFT o RIGHT
        """
        target_angle = DIRECTION_TO_ANGLE[target_direction]
        current_angle = DIRECTION_TO_ANGLE[self.current_heading]

        # Calcular el giro más corto
        delta = target_angle - current_angle

        # Normalizar a [-180, 180]
        while delta > 180:
            delta -= 360
        while delta < -180:
            delta += 360

        if delta != 0:
            self.robot.turn(delta)

        self.current_heading = target_direction
        self.current_heading_angle = target_angle

    # =========================================================================
    # NAVEGACIÓN COMPLETA
    # =========================================================================

    def navigate_to(self, goal, use_line_following=False, on_block_callback=None):
        """
        Navega desde la posición actual hasta el objetivo.

        Args:
            goal: Tupla (fila, columna) del destino
            use_line_following: Si True, usa seguimiento de línea (Cat. C)
            on_block_callback: Función a llamar al llegar a cada bloque.
                               Recibe (fila, col) como argumentos.

        Returns:
            bool: True si se llegó al destino, False si falló
        """
        # Calcular ruta
        path = self.pathfinder.find_path(self.current_pos, goal)

        if not path:
            self.robot.display_text("No hay ruta!")
            self.robot.beep(200, 500)
            return False

        self.robot.display_text("Ruta: {} pasos".format(len(path) - 1))

        # Obtener las direcciones de la ruta
        directions = self.pathfinder.get_directions(path)

        # Ejecutar cada paso
        for i, direction in enumerate(directions):
            # 1. Girar hacia la dirección correcta
            self.turn_to_direction(direction)

            # 2. Avanzar un bloque
            if use_line_following:
                success = self.follow_line_to_next_block()
                if not success:
                    # Fallback: avanzar por odometría
                    self.move_one_block()
            else:
                self.move_one_block()

            # 3. Actualizar posición
            self.current_pos = path[i + 1]

            # 4. Callback (para publicar odometría, etc.)
            if on_block_callback:
                on_block_callback(self.current_pos[0], self.current_pos[1])

        self.robot.display_text("Destino alcanzado!")
        return True

    def pickup_package(self):
        """Recoge un paquete en la posición actual."""
        self.robot.display_text("Recogiendo...")
        self.robot.pala_bajar()
        from pybricks.tools import wait
        wait(500)
        self.robot.beep(800, 300)

    def deliver_package(self):
        """Entrega un paquete en la posición actual."""
        self.robot.display_text("Entregando...")
        self.robot.pala_subir()
        from pybricks.tools import wait
        wait(500)
        self.robot.beep(1000, 300)
        wait(200)
        self.robot.beep(1000, 300)

    def get_state(self):
        """
        Obtiene el estado actual del navegador.

        Returns:
            dict: Estado con posición, orientación y odometría
        """
        odo = self.robot.get_odometry()
        return {
            'row': self.current_pos[0],
            'col': self.current_pos[1],
            'heading': self.current_heading,
            'heading_angle': self.current_heading_angle,
            'distance': odo[0],
            'speed': odo[1],
            'angle': odo[2],
            'turn_rate': odo[3],
        }
