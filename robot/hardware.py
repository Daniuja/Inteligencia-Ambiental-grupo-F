"""
hardware.py — Abstracción del hardware del robot EV3.

Encapsula la inicialización y control de todos los componentes físicos:
- EV3Brick (ladrillo principal)
- 2x Motor grande (propulsión diferencial)
- 1x Motor mediano (pala de recogida/entrega)
- 1x Sensor de color (detección de líneas y patrones)
- 1x Sensor giroscópico (orientación)
- DriveBase (control cinemático del robot diferencial)

IMPORTANTE: Ajustar los puertos y dimensiones según el robot real.
"""

from pybricks.hubs import EV3Brick
from pybricks.ev3devices import Motor, ColorSensor, GyroSensor
from pybricks.parameters import Port, Stop, Direction, Color
from pybricks.robotics import DriveBase
from pybricks.tools import wait


# =============================================================================
# CONFIGURACIÓN DEL HARDWARE — AJUSTAR SEGÚN EL ROBOT REAL
# =============================================================================

# Puertos de los motores
LEFT_MOTOR_PORT = Port.B
RIGHT_MOTOR_PORT = Port.C
PALA_MOTOR_PORT = Port.A

# Puertos de los sensores
COLOR_SENSOR_PORT = Port.S4
GYRO_SENSOR_PORT = Port.S1

# Dimensiones del robot (en mm) — CALIBRAR CON EL ROBOT REAL
WHEEL_DIAMETER = 60   # Diámetro de las ruedas en mm
AXLE_TRACK = 110         # Distancia entre puntos de contacto de las ruedas en mm

# Velocidades por defecto
DEFAULT_DRIVE_SPEED = 150       # mm/s
DEFAULT_DRIVE_ACCELERATION = 200  # mm/s²
DEFAULT_TURN_RATE = 120         # deg/s
DEFAULT_TURN_ACCELERATION = 200  # deg/s²

# Configuración de la pala
PALA_SPEED = 200         # deg/s
PALA_DOWN_ANGLE = 90     # Grados para bajar la pala (AJUSTAR)
PALA_UP_ANGLE = -90      # Grados para subir la pala (AJUSTAR)


class RobotHardware:
    """Clase que abstrae todo el hardware del robot EV3."""

    def __init__(self):
        """Inicializa todos los componentes del robot."""
        # Ladrillo EV3
        self.ev3 = EV3Brick()

        # Motores de propulsión
        self.left_motor = Motor(LEFT_MOTOR_PORT)
        self.right_motor = Motor(RIGHT_MOTOR_PORT)

        # Motor de la pala
        self.pala_motor = Motor(PALA_MOTOR_PORT)

        # Sensores
        self.color_sensor = ColorSensor(COLOR_SENSOR_PORT)
        try:
            self.gyro_sensor = GyroSensor(GYRO_SENSOR_PORT)
            print("Giroscopio detectado en el puerto", GYRO_SENSOR_PORT)
        except Exception:
            self.gyro_sensor = None
            print("AVISO: No se detecta giroscopio en el puerto", GYRO_SENSOR_PORT)

        # DriveBase para control cinemático
        self.drive_base = DriveBase(
            self.left_motor,
            self.right_motor,
            wheel_diameter=WHEEL_DIAMETER,
            axle_track=AXLE_TRACK
        )

        # Configurar velocidades por defecto
        self.drive_base.settings(
            straight_speed=DEFAULT_DRIVE_SPEED,
            straight_acceleration=DEFAULT_DRIVE_ACCELERATION,
            turn_rate=DEFAULT_TURN_RATE,
            turn_acceleration=DEFAULT_TURN_ACCELERATION
        )

        # Estado de la pala
        self.pala_down = False

        # Señal de inicialización
        self.ev3.speaker.beep(frequency=800, duration=200)
        self.ev3.light.on(Color.GREEN)

    # =========================================================================
    # MOVIMIENTO
    # =========================================================================

    def move_straight(self, distance_mm):
        """
        Mueve el robot en línea recta.

        Args:
            distance_mm: Distancia en mm (positivo = adelante, negativo = atrás)
        """
        self.drive_base.straight(distance_mm)

    def turn(self, angle_deg):
        """
        Gira el robot en su sitio.

        Args:
            angle_deg: Ángulo en grados (positivo = derecha, negativo = izquierda)
        """
        self.drive_base.turn(angle_deg)

    def drive(self, speed, turn_rate):
        """
        Conduce continuamente a una velocidad y tasa de giro dadas.

        Args:
            speed: Velocidad en mm/s
            turn_rate: Velocidad angular en deg/s
        """
        self.drive_base.drive(speed, turn_rate)

    def stop(self):
        """Detiene el robot (las ruedas quedan libres)."""
        self.drive_base.stop()

    # =========================================================================
    # SENSORES
    # =========================================================================

    def read_color(self):
        """
        Lee el color detectado por el sensor.

        Returns:
            Color: Color.BLACK, Color.BLUE, Color.GREEN, Color.YELLOW,
                   Color.RED, Color.WHITE, Color.BROWN, o None
        """
        return self.color_sensor.color()

    def read_reflection(self):
        """
        Lee la reflectancia de la superficie (0-100%).

        Returns:
            int: Porcentaje de reflexión (0 = negro, 100 = blanco)
        """
        return self.color_sensor.reflection()

    def read_rgb(self):
        """
        Lee los valores RGB de la superficie.

        Returns:
            tuple: (red%, green%, blue%) cada uno de 0 a 100
        """
        return self.color_sensor.rgb()

    def read_gyro_angle(self):
        """
        Lee el ángulo acumulado del giroscopio.

        Returns:
            int: Ángulo en grados, o 0 si no hay giroscopio.
        """
        if self.gyro_sensor is None:
            return 0
        return self.gyro_sensor.angle()

    def reset_gyro(self, angle=0):
        """Resetea el ángulo del giroscopio."""
        if self.gyro_sensor is not None:
            self.gyro_sensor.reset_angle(angle)

    # =========================================================================
    # PALA (RECOGIDA / ENTREGA)
    # =========================================================================

    def pala_bajar(self):
        """Baja la pala para recoger un paquete."""
        if not self.pala_down:
            self.pala_motor.run_angle(PALA_SPEED, PALA_DOWN_ANGLE, then=Stop.HOLD)
            self.pala_down = True
            self.ev3.speaker.beep(frequency=600, duration=100)

    def pala_subir(self):
        """Sube la pala para soltar un paquete."""
        if self.pala_down:
            self.pala_motor.run_angle(PALA_SPEED, PALA_UP_ANGLE, then=Stop.HOLD)
            self.pala_down = False
            self.ev3.speaker.beep(frequency=400, duration=100)

    # =========================================================================
    # ODOMETRÍA
    # =========================================================================

    def get_odometry(self):
        """
        Obtiene el estado actual de odometría del DriveBase.

        Returns:
            tuple: (distance_mm, drive_speed_mm_s, angle_deg, turn_rate_deg_s)
        """
        return self.drive_base.state()

    def get_distance(self):
        """Obtiene la distancia recorrida acumulada en mm."""
        return self.drive_base.distance()

    def get_angle(self):
        """Obtiene el ángulo girado acumulado en grados."""
        return self.drive_base.angle()

    def reset_odometry(self):
        """Resetea la distancia y ángulo acumulados del DriveBase a 0."""
        self.drive_base.reset()

    # =========================================================================
    # INTERFAZ DEL LADRILLO
    # =========================================================================

    def display_text(self, text, line=5):
        """Muestra texto en la pantalla del EV3."""
        self.ev3.screen.clear()
        self.ev3.screen.draw_text(10, line, text)

    def beep(self, frequency=500, duration=200):
        """Reproduce un beep."""
        self.ev3.speaker.beep(frequency=frequency, duration=duration)

    def set_light(self, color):
        """Cambia el color del LED del ladrillo."""
        self.ev3.light.on(color)

    def is_button_pressed(self):
        """Comprueba si algún botón del ladrillo está pulsado."""
        return len(self.ev3.buttons.pressed()) > 0

    def get_battery_voltage(self):
        """Obtiene el voltaje de la batería."""
        return self.ev3.battery.voltage()
