"""
codificar_mapa.py
=================
Codifica un mapa-imagen (cuadrícula de celdas) al formato numérico de dos dígitos.

Tabla de IDs:
  00 - Edificio (círculo rojo)
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
  11 - Calle arriba-derecha-abajo-izquierda (cruce completo)

Uso:
  python codificar_mapa.py imagen.png --filas 7 --columnas 5
  python codificar_mapa.py imagen.png --filas 7 --columnas 5 --debug
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image


# ─────────────────────────────────────────────
# Colores de referencia (RGB)
# ─────────────────────────────────────────────
COLOR_RED   = np.array([255,   0,   0])   # círculo edificio
COLOR_GREEN = np.array([  0, 200,   0])   # línea central verde
COLOR_BLUE  = np.array([  0,   0, 255])   # línea exterior azul
COLOR_BLACK = np.array([  0,   0,   0])   # intersección negra

THRESH = 80   # tolerancia de color (distancia euclídea)


def color_distance(pixel: np.ndarray, ref: np.ndarray) -> float:
    return float(np.linalg.norm(pixel.astype(float) - ref.astype(float)))


def pixel_is(pixel: np.ndarray, ref: np.ndarray) -> bool:
    return color_distance(pixel, ref) < THRESH


# ─────────────────────────────────────────────
# Análisis de una celda
# ─────────────────────────────────────────────

def analyze_cell(cell: np.ndarray) -> int:
    """
    Recibe un recorte (H×W×3) y devuelve el ID (0-11).

    Estrategia:
      1. Si hay suficiente rojo → edificio (00).
      2. Si no, detecta presencia de color de calle (azul o verde)
         en las cuatro bandas de borde (arriba, abajo, izquierda, derecha).
      3. Combina las conexiones detectadas para determinar el tipo.
    """
    h, w, _ = cell.shape

    # ── 1. Edificio ──────────────────────────────────────────
    red_pixels = np.sum(
        np.linalg.norm(cell.astype(float) - COLOR_RED, axis=2) < THRESH
    )
    if red_pixels > (h * w * 0.05):          # >5 % de la celda es rojo
        return 0

    # ── 2. Detección de conexiones ───────────────────────────
    band = max(4, h // 8)   # ancho de la franja de borde

    def has_road(region: np.ndarray) -> bool:
        """True si la región contiene píxeles azules o verdes."""
        blue  = np.sum(np.linalg.norm(region.astype(float) - COLOR_BLUE,  axis=2) < THRESH)
        green = np.sum(np.linalg.norm(region.astype(float) - COLOR_GREEN, axis=2) < THRESH)
        return (blue + green) > 5

    top    = cell[:band,      w//3:2*w//3, :]
    bottom = cell[-band:,     w//3:2*w//3, :]
    left   = cell[h//3:2*h//3, :band,      :]
    right  = cell[h//3:2*h//3, -band:,     :]

    T = has_road(top)
    B = has_road(bottom)
    L = has_road(left)
    R = has_road(right)

    # ── 3. Mapeo de conexiones → ID ──────────────────────────
    #   Notación: T=arriba, B=abajo, L=izquierda, R=derecha
    mapping = {
        (False, False, True,  True ): 1,   # L-R
        (True,  True,  False, False): 2,   # T-B  (arriba-abajo)
        (True,  False, False, True ): 3,   # T-R  (arriba-derecha)
        (False, True,  False, True ): 4,   # R-B  (derecha-abajo)
        (False, True,  True,  False): 5,   # B-L  (abajo-izquierda)
        (True,  False, True,  False): 6,   # T-L  (izquierda-arriba)
        (True,  False, True,  True ): 7,   # L-T-R (izquierda-arriba-derecha)
        (True,  True,  False, True ): 8,   # T-R-B (arriba-derecha-abajo)
        (False, True,  True,  True ): 9,   # R-B-L (derecha-abajo-izquierda)
        (True,  True,  True,  False): 10,  # B-L-T (abajo-izquierda-arriba)
        (True,  True,  True,  True ): 11,  # cruce completo
    }

    key = (T, B, L, R)
    if key in mapping:
        return mapping[key]

    # Fallback: si no coincide exactamente, buscar el más parecido
    # contando conexiones activas
    active = sum([T, B, L, R])
    if active == 0:
        return 0   # sin calle → edificio vacío
    # Devolver edificio si no se reconoce
    return 0


# ─────────────────────────────────────────────
# Función principal
# ─────────────────────────────────────────────

def encode_map(image_path: str, rows: int, cols: int, debug: bool = False) -> str:
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img)

    H, W, _ = arr.shape
    cell_h = H // rows
    cell_w = W // cols

    code_pairs = []

    for r in range(rows):
        for c in range(cols):
            y0 = r * cell_h
            y1 = y0 + cell_h
            x0 = c * cell_w
            x1 = x0 + cell_w

            cell = arr[y0:y1, x0:x1, :]
            tile_id = analyze_cell(cell)
            code_pairs.append(f"{tile_id:02d}")

            if debug:
                print(f"  Celda ({r},{c}): id={tile_id:02d}")

    encoded = "".join(code_pairs)
    return encoded


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Codifica un mapa-imagen a cadena numérica."
    )
    parser.add_argument("imagen", help="Ruta a la imagen del mapa (PNG, WEBP…)")
    parser.add_argument("--filas",    type=int, default=7,  help="Número de filas (default: 7)")
    parser.add_argument("--columnas", type=int, default=5,  help="Número de columnas (default: 5)")
    parser.add_argument("--debug",    action="store_true",  help="Muestra el ID de cada celda")
    args = parser.parse_args()

    path = Path(args.imagen)
    if not path.exists():
        print(f"Error: no se encontró el archivo '{path}'", file=sys.stderr)
        sys.exit(1)

    print(f"Procesando '{path}' ({args.filas}×{args.columnas})…")
    result = encode_map(str(path), args.filas, args.columnas, debug=args.debug)

    print(f"\nCódigo del mapa:\n{result}")
    print(f"\nTotal de celdas: {len(result)//2}  ({args.filas}×{args.columnas}={args.filas*args.columnas})")

    # Mostrar cuadrícula legible
    print("\nCuadrícula:")
    for r in range(args.filas):
        fila = " ".join(result[i*2:(i*2)+2] for i in range(r*args.columnas, (r+1)*args.columnas))
        print(f"  Fila {r+1}: {fila}")


if __name__ == "__main__":
    main()
