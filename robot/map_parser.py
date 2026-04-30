"""
map_parser.py — Decodificación y análisis del mapa de la ciudad.

El mapa se recibe como una cadena de caracteres desde el servidor MQTT,
donde cada par de dígitos representa el ID de un bloque. El orden es por
filas: primero bloque (0,0), luego (0,1), ..., hasta (6,4).

IDs de bloque:
  00 - Edificio (sin entrada)
  01 - Calle izquierda-derecha
  02 - Calle arriba-abajo
  03 - Calle arriba-derecha
  04 - Calle derecha-abajo
  05 - Calle abajo-izquierda
  06 - Calle izquierda-arriba
  07 - Calle izquierda-arriba-derecha
  08 - Calle arriba-derecha-abajo
  09 - Calle derecha-abajo-izquierda
  10 - Calle abajo-izquierda-arriba
  11 - Calle arriba-derecha-abajo-izquierda
"""

# Dimensiones del mapa (filas x columnas)
MAP_ROWS = 7
MAP_COLS = 5

# Tamaño de cada bloque en mm
BLOCK_SIZE_MM = 280

# Direcciones posibles
UP = 'up'
RIGHT = 'right'
DOWN = 'down'
LEFT = 'left'

# Mapeo de ID de bloque a las direcciones de entrada/salida
BLOCK_DIRECTIONS = {
    0:  [],                          # Edificio
    1:  [LEFT, RIGHT],               # Izquierda-derecha
    2:  [UP, DOWN],                  # Arriba-abajo
    3:  [UP, RIGHT],                 # Arriba-derecha
    4:  [RIGHT, DOWN],               # Derecha-abajo
    5:  [DOWN, LEFT],                # Abajo-izquierda
    6:  [LEFT, UP],                  # Izquierda-arriba
    7:  [LEFT, UP, RIGHT],           # Izquierda-arriba-derecha
    8:  [UP, RIGHT, DOWN],           # Arriba-derecha-abajo
    9:  [RIGHT, DOWN, LEFT],         # Derecha-abajo-izquierda
    10: [DOWN, LEFT, UP],            # Abajo-izquierda-arriba
    11: [UP, RIGHT, DOWN, LEFT],     # Todas las direcciones
}

# Dirección opuesta (para verificar conexión bidireccional)
OPPOSITE = {
    UP: DOWN,
    DOWN: UP,
    LEFT: RIGHT,
    RIGHT: LEFT,
}

# Desplazamiento en la grid para cada dirección (fila, columna)
DIRECTION_DELTA = {
    UP:    (-1,  0),
    DOWN:  ( 1,  0),
    LEFT:  ( 0, -1),
    RIGHT: ( 0,  1),
}


class CityMap:
    """Representa el mapa de la ciudad como un grid de bloques."""

    def __init__(self):
        self.grid = []           # Matriz MAP_ROWS x MAP_COLS de IDs de bloque
        self.adjacency = {}      # Grafo: (fila, col) -> lista de (fila, col) vecinos
        self.pickup_points = []  # Bloques con solo 1 entrada/salida
        self.start_position = (MAP_ROWS - 1, 0)  # Esquina inferior izquierda (fila 6, col 0 en grid 7x5)

    def parse(self, map_string):
        """
        Parsea la cadena del mapa y construye el grid y el grafo de adyacencia.

        Args:
            map_string: Cadena de caracteres con los IDs de bloque concatenados.
                        Ejemplo: "02020001050307..."
        """
        # Extraer pares de dígitos
        block_ids = []
        for i in range(0, len(map_string), 2):
            block_id = int(map_string[i:i+2])
            block_ids.append(block_id)

        # Construir la grid
        self.grid = []
        for row in range(MAP_ROWS):
            row_data = []
            for col in range(MAP_COLS):
                idx = row * MAP_COLS + col
                if idx < len(block_ids):
                    row_data.append(block_ids[idx])
                else:
                    row_data.append(0)  # Default: edificio
            self.grid.append(row_data)

        # Construir grafo de adyacencia
        self._build_adjacency()

        # Identificar puntos de recogida/entrega
        self._find_pickup_points()

    def _build_adjacency(self):
        """Construye el grafo de adyacencia basado en las conexiones de los bloques."""
        self.adjacency = {}

        for row in range(MAP_ROWS):
            for col in range(MAP_COLS):
                block_id = self.grid[row][col]
                directions = BLOCK_DIRECTIONS.get(block_id, [])
                neighbors = []

                for direction in directions:
                    dr, dc = DIRECTION_DELTA[direction]
                    nr, nc = row + dr, col + dc

                    # Verificar límites
                    if 0 <= nr < MAP_ROWS and 0 <= nc < MAP_COLS:
                        # Verificar que el vecino también tiene entrada desde nuestra dirección
                        neighbor_id = self.grid[nr][nc]
                        neighbor_dirs = BLOCK_DIRECTIONS.get(neighbor_id, [])
                        if OPPOSITE[direction] in neighbor_dirs:
                            neighbors.append((nr, nc))

                self.adjacency[(row, col)] = neighbors

    def _find_pickup_points(self):
        """Identifica los puntos de recogida/entrega (bloques con solo 1 conexión válida)."""
        self.pickup_points = []

        for row in range(MAP_ROWS):
            for col in range(MAP_COLS):
                block_id = self.grid[row][col]
                if block_id == 0:  # Edificio, no es punto de recogida
                    continue

                # Contar conexiones válidas (no solo direcciones del bloque)
                valid_connections = len(self.adjacency.get((row, col), []))
                if valid_connections == 1:
                    self.pickup_points.append((row, col))

    def is_building(self, row, col):
        """Comprueba si un bloque es un edificio."""
        if 0 <= row < MAP_ROWS and 0 <= col < MAP_COLS:
            return self.grid[row][col] == 0
        return True  # Fuera de límites se considera edificio

    def is_street(self, row, col):
        """Comprueba si un bloque es una calle."""
        return not self.is_building(row, col)

    def get_block_directions(self, row, col):
        """Devuelve las direcciones de entrada/salida de un bloque."""
        if 0 <= row < MAP_ROWS and 0 <= col < MAP_COLS:
            block_id = self.grid[row][col]
            return BLOCK_DIRECTIONS.get(block_id, [])
        return []

    def get_neighbors(self, row, col):
        """Devuelve los vecinos accesibles de un bloque."""
        return self.adjacency.get((row, col), [])

    def get_direction_to(self, from_pos, to_pos):
        """Calcula la dirección necesaria para ir de from_pos a to_pos (adyacentes)."""
        dr = to_pos[0] - from_pos[0]
        dc = to_pos[1] - from_pos[1]

        for direction, (delta_r, delta_c) in DIRECTION_DELTA.items():
            if delta_r == dr and delta_c == dc:
                return direction
        return None

    def to_json(self):
        """Serializa el mapa a un diccionario JSON-compatible."""
        return {
            'grid': self.grid,
            'rows': MAP_ROWS,
            'cols': MAP_COLS,
            'pickup_points': self.pickup_points,
            'start': list(self.start_position),
        }

    def print_map(self):
        """Imprime una representación visual del mapa en consola."""
        for row in range(MAP_ROWS):
            line = ""
            for col in range(MAP_COLS):
                block_id = self.grid[row][col]
                if block_id == 0:
                    line += " ## "
                elif (row, col) in self.pickup_points:
                    line += " PP "
                else:
                    line += " {:02d} ".format(block_id)
            print(line)
