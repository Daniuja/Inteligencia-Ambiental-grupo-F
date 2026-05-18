

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
        self.city_map = city_map

    def find_path(self, start, goal):
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
        directions = []
        for i in range(len(path) - 1):
            direction = self.city_map.get_direction_to(path[i], path[i + 1])
            if direction:
                directions.append(direction)
        return directions


class Navigator:

    def __init__(self, robot_hw, city_map):
        self.robot = robot_hw
        self.city_map = city_map
        self.pathfinder = PathFinder(city_map)

        # Estado de navegación
        self.current_pos = city_map.start_position  # (fila, col)
        self.current_heading = RIGHT  # Orientación inicial: mirando hacia la derecha
        self.current_heading_angle = 90  # 90 = derecha
        self.last_turn_delta = 0

    def set_pose(self, row, col, heading):
        if heading not in DIRECTION_TO_ANGLE:
            heading = RIGHT

        self.current_pos = (row, col)
        self.current_heading = heading
        self.current_heading_angle = DIRECTION_TO_ANGLE[heading]
        self.last_turn_delta = 0
        self.robot.reset_odometry()
        self.robot.reset_gyro(self.current_heading_angle)



    GREEN_ON_LINE = 35      # Verdosidad típica sobre la línea verde (CALIBRAR)
    GREEN_OFF_LINE = 5      # Verdosidad típica fuera de la línea (CALIBRAR)
    # Umbral = (ON + OFF) / 2 aprox. (CALIBRAR)
    LINE_THRESHOLD = 20     
    PROPORTIONAL_GAIN = 3.5  # Ganancia proporcional (Kp) aumentada para girar rápido
    DERIVATIVE_GAIN = 2.0    # Ganancia derivativa (Kd) para frenar oscilaciones
    LINE_SPEED = 80         # Velocidad de seguimiento de línea verde (mm/s)

    # Umbral de intensidad para detectar negro. La condicion de verdosidad en
    # is_black evita confundir una linea verde oscura con una zona negra.
    BLACK_INTENSITY_THRESHOLD = 45

    # Compensacion de giro real del robot.
    # En pruebas: 90 ordenados ~= 60 reales, 180 ordenados ~= 150 reales.
    TURN_90_CORRECTION = 1.60
    TURN_180_CORRECTION = 1.35
    RIGHT_TURN_REDUCTION = 0.60
    RIGHT_TURN_LINE_SEARCH_SPEED = 50
    RIGHT_TURN_LINE_SEARCH_DISTANCE = 90

    def _compute_greenness(self, r, g, b):
        return g - max(r, b)

    def follow_line_to_next_block(self):
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
        green_count = 0

        self.robot.reset_odometry()

        if self.last_turn_delta > 0:
            found_line = False
            self.robot.drive(self.RIGHT_TURN_LINE_SEARCH_SPEED, 0)
            while abs(self.robot.get_distance()) < self.RIGHT_TURN_LINE_SEARCH_DISTANCE:
                r, g, b = self.robot.read_rgb()
                if self._compute_greenness(r, g, b) >= self.LINE_THRESHOLD:
                    found_line = True
                    break
                wait(10)

            self.robot.stop()
            if not found_line:
                self.realign_to_line()

            fase = 1
            black_count = 0
            last_deviation = 0

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
            # Mejorado: es negro solo si la intensidad es baja Y no es verde
            is_black = (intensity < self.BLACK_INTENSITY_THRESHOLD) and (greenness < self.LINE_THRESHOLD)
            
            if is_black:
                black_count += 1
                green_count = 0
                # Al detectar negro se avanza recto para cruzar fronteras y
                # cuadrados sin que el controlador de linea corrija el giro.
                turn_rate = 0
                last_deviation = 0
            else:
                black_count = 0
                green_count += 1

            # Aplicar la velocidad y el giro calculados.
            self.robot.drive(current_speed, turn_rate)

            if fase == 0:
                # Saliendo: ignorar negro hasta ver verde continuo
                if not is_black:
                    # Al salir del negro se comprueba si el sensor esta sobre verde.
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
                # Cruzando frontera: ignorar negro hasta volver a ver verde FIRME
                # Usamos green_count para evitar que un solo pico de ruido 
                # (un falso 'no negro' estando sobre la línea negra) nos salte de fase.
                if green_count >= 2:
                    fase = 3
                    
            elif fase == 3:
                # Buscando centro: esperar al cuadrado negro central
                if black_count >= 2:
                    # ¡Llegamos al centro!
                    self.robot.stop()
                    # Avanzamos un poco más para que las RUEDAS queden perfectamente centradas
                    # Así el giro de 90º será sobre el centro exacto de la casilla.
                    self.robot.move_straight(65)  
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
        self.robot.move_straight(BLOCK_SIZE_MM)

    def turn_to_direction(self, target_direction):
        target_angle = DIRECTION_TO_ANGLE[target_direction]
        current_angle = DIRECTION_TO_ANGLE[self.current_heading]

        # Calcular el giro más corto
        delta = target_angle - current_angle

        # Normalizar a [-180, 180]
        while delta > 180:
            delta -= 360
        while delta < -180:
            delta += 360

        # Si hay que dar media vuelta, preferimos girar a la izquierda.
        # En el robot real ese sentido sale mejor y evita el caso malo de 0,1.
        if delta == 180:
            delta = -180

        if delta != 0:
            # Giro compensado: el robot real se queda corto al girar sobre negro.
            abs_delta = abs(delta)
            if abs_delta == 90:
                corrected_delta = delta * self.TURN_90_CORRECTION
            elif abs_delta == 180:
                corrected_delta = delta * self.TURN_180_CORRECTION
            else:
                corrected_delta = delta

            if delta > 0:
                corrected_delta *= self.RIGHT_TURN_REDUCTION

            self.robot.turn(corrected_delta)

        self.last_turn_delta = delta
        self.current_heading = target_direction
        self.current_heading_angle = target_angle

    def realign_to_line(self):
        from pybricks.tools import wait, StopWatch
        timer = StopWatch()
        
        sweep_speed = 45  # Ajustado a 45 deg/s para no saltarse la línea
        
        # 1. Comprobar si el sensor ya esta sobre la linea.
        r, g, b = self.robot.read_rgb()
        if self._compute_greenness(r, g, b) >= self.LINE_THRESHOLD:
            return

        # Patrón de búsqueda: abanico sobre el sitio, cada ciclo un poco más amplio.
        search_time = 1800
        max_search_time = 3000
        
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
                
            # 2. Buscar hacia la izquierda el doble de tiempo (cruza el centro hacia el otro lado)
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
                
            # 4. Si no la encuentra, repetir el abanico sin avanzar.
            self.robot.stop()
            if search_time < max_search_time:
                search_time += 300

    # =========================================================================
    # NAVEGACIÓN COMPLETA
    # =========================================================================

    def navigate_to(self, goal, use_line_following=False, on_block_callback=None):
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
        self.robot.display_text("Recogiendo...")
        self.robot.pala_bajar()
        from pybricks.tools import wait
        wait(500)
        self.robot.beep(800, 300)

    def deliver_package(self):
        self.robot.display_text("Entregando...")
        self.robot.pala_subir()
        from pybricks.tools import wait
        wait(500)
        self.robot.beep(1000, 300)
        wait(200)
        self.robot.beep(1000, 300)

    def get_state(self):
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
