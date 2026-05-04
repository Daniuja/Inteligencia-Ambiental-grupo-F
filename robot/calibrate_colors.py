#!/usr/bin/env pybricks-micropython

from pybricks.tools import wait
from hardware import RobotHardware

def main():
    print("========================================")
    print("  CALIBRADOR DE COLORES RGB (EQUIPO F)  ")
    print("========================================")
    print("Iniciando hardware...")
    robot = RobotHardware()
    
    print("\nInstrucciones:")
    print("1. Pon el robot sobre el BLANCO y anota la Verdosidad (aprox 0).")
    print("2. Pon el robot sobre la LÍNEA VERDE y anota la Verdosidad (aprox 30-40).")
    print("   -> LINE_THRESHOLD será la mitad entre ambos valores.")
    print("3. Pon el robot sobre el CUADRADO NEGRO y anota la Intensidad (aprox 15-30).")
    print("   -> BLACK_INTENSITY_THRESHOLD debe ser un poco mayor que este valor.")
    print("Pulsa Ctrl+C o el botón gris del robot para salir.\n")

    while True:
        r, g, b = robot.read_rgb()
        
        greenness = g - max(r, b)
        intensity = r + g + b
        
        print("RGB: ({:3d}, {:3d}, {:3d}) | Verdosidad: {:3d} | Intensidad: {:3d}".format(r, g, b, greenness, intensity))
        
        if robot.is_button_pressed():
            break
            
        wait(500)  # Leer cada medio segundo

if __name__ == "__main__":
    main()
