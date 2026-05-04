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
        self.current_heading = RIGHT  # Orientación inicial: mirando hacia la derecha
        self.current_heading_angle = 90  # 90 = derecha

    # =========================================================================
    # SEGUIMIENTO DE LÍNEA VERDE (Categoría C)
    # =========================================================================

    # Constantes para el controlador PID de seguimiento de línea verde.
    # La "verdosidad" (greenness) se calcula como: G - max(R, B) del sensor RGB.
    # Sobre la línea verde el valor es alto; fuera (blanco) es cercano a 0.
    GREEN_ON_LINE = 35      # Verdosidad típica sobre la línea verde (CALIBRAR)
    GREEN_OFF_LINE = 5      # Verdosidad típica fuera de la línea (CALIBRAR)
    LINE_THRESHOLD = 20     # Umbral = (ON + OFF) / 2 aprox. (CALIBRAR)
    PROPORTIONAL_GAIN = 3.5  # Ganancia proporcional (Kp) aumentada para girar rápido
    DERIVATIVE_GAIN = 2.0    # Ganancia derivativa (Kd) para frenar oscilaciones
    LINE_SPEED = 80         # Velocidad de seguimiento de línea verde (mm/s)

    # NUEVO: Intensidad para el cuadrado negro (R + G + B)
    # El negro absorbe luz, por lo que R, G y B serán bajos.
    BLACK_INTENSITY_THRESHOLD = 45  # (CALIBRAR, ej: 15+15+15=45)

    def _compute_greenness(self, r, g, b):
        """Calcula la puntuación de verdosidad a partir del RGB."""
        return g - max(r, b)

    def follow_line_to_next_block(self):
        """
        Sigue la línea verde usando controlador PD y una máquina de estados
        para cruzar la línea de frontera negra antes de parar en el centro negro.
        """
        from pybricks.tools import wait, StopWatch

        SPEED = self.LINE_SPEED
        last_deviation = 0
        
        # Máquina de estados para avanzar por el bloque
        # 0 = Saliendo del cuadrado central actual (ignorando negro)
        # 1 = Buscando la línea negra de frontera
        # 2 = Cruzando la frontera (esperando verde de nuevo)
        # 3 = Buscando el cuadrado negro central de destino
        fase = 0
        black_count = 0

        self.robot.reset_odometry()

        while True:
            r, g, b = self.robot.read_rgb()
            greenness = self._compute_greenness(r, g, b)
            intensity = r + g + b

            # Controlador PD
            deviation = self.LINE_THRESHOLD - greenness
            turn_rate = (self.PROPORTIONAL_GAIN * deviation) + (self.DERIVATIVE_GAIN * (deviation - last_deviation))
            last_deviation = deviation
            
            # Frenar ligeramente si el giro es muy brusco (curva fuerte)
            current_speed = SPEED
            if abs(turn_rate) > 40:
                current_speed = SPEED - 20
                
            # Máquina de estados para fronteras e intersecciones
            is_black = intensity < self.BLACK_INTENSITY_THRESHOLD
            
            if is_black:
                black_count += 1
                # ¡MAGIA! Si estamos pisando negro, anular el giro y el freno
                # para cruzar la línea/cuadrado totalmente rectos
                turn_rate = 0
                last_deviation = 0
            else:
                black_count = 0

            # AHORA SÍ aplicamos la velocidad y el giro al robot
            self.robot.drive(current_speed, turn_rate)

            if fase == 0:
                # Saliendo: ignorar negro hasta ver verde continuo
                if not is_black:
                    # Acabamos de salir del negro. ¿Estamos en verde o blanco?
                    if greenness < self.LINE_THRESHOLD:
                        # Hemos salido al blanco. El robot está torcido (p.ej tras recoger un paquete)
                        self.robot.stop()
                        self.realign_to_line()
                        last_deviation = 0  # Resetear error para no dar un latigazo
                    fase = 1
                    
            elif fase == 1:
                # Buscando frontera: esperar a detectar negro firme
                if black_count >= 2:
                    fase = 2
                    
            elif fase == 2:
                # Cruzando frontera: ignorar negro hasta volver a ver verde
                if not is_black:
                    fase = 3
                    
            elif fase == 3:
                # Buscando centro: esperar al cuadrado negro central
                if black_count >= 2:
                    # ¡Llegamos al centro!
                    self.robot.stop()
                    self.robot.move_straight(40)  # Centrar ruedas
                    return True

            # Timeout de seguridad
            distance = abs(self.robot.get_distance())
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

    def realign_to_line(self):
        """
        Hace un barrido (sweep) izquierda-derecha para encontrar
        la línea verde y quedarse centrado. Búsqueda infinita y progresiva.
        """
        from pybricks.tools import wait, StopWatch
        timer = StopWatch()
        
        sweep_speed = 30  # Muy lento para detectarla perfectamente
        
        # 1. ¿Estamos ya en la línea?
        r, g, b = self.robot.read_rgb()
        if self._compute_greenness(r, g, b) >= self.LINE_THRESHOLD:
            return

        # Patrón de búsqueda: Empezar buscando poco, e ir abriendo el abanico
        search_time = 1000  # 1 segundo = 30 grados
        
        while True:
            # 1. Buscar hacia la derecha
            self.robot.drive(0, sweep_speed)
            timer.reset()
            while timer.time() < search_time:
                r, g, b = self.robot.read_rgb()
                if self._compute_greenness(r, g, b) >= self.LINE_THRESHOLD:
                    self.robot.stop()
                    return
                wait(10)
                
            # 2. Buscar hacia la izquierda el doble de tiempo (cruza el centro)
            self.robot.drive(0, -sweep_speed)
            timer.reset()
            while timer.time() < search_time * 2:
                r, g, b = self.robot.read_rgb()
                if self._compute_greenness(r, g, b) >= self.LINE_THRESHOLD:
                    self.robot.stop()
                    return
                wait(10)
                
            # 3. Volver al centro (derecha de nuevo)
            self.robot.drive(0, sweep_speed)
            timer.reset()
            while timer.time() < search_time:
                r, g, b = self.robot.read_rgb()
                if self._compute_greenness(r, g, b) >= self.LINE_THRESHOLD:
                    self.robot.stop()
                    return
                wait(10)
                
            # Si seguimos sin encontrarla, ampliamos el rango de búsqueda y repetimos
            search_time += 1000

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
