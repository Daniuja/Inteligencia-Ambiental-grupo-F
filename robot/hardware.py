from pybricks.hubs import EV3Brick
from pybricks.ev3devices import Motor, ColorSensor, GyroSensor
from pybricks.parameters import Port, Stop, Direction, Color
from pybricks.robotics import DriveBase
from pybricks.tools import wait



#motores
LEFT_MOTOR_PORT = Port.B
RIGHT_MOTOR_PORT = Port.C
PALA_MOTOR_PORT = Port.A

#sensores
COLOR_SENSOR_PORT = Port.S4
GYRO_SENSOR_PORT = Port.S1

# Dimensiones del robot
WHEEL_DIAMETER = 60   
AXLE_TRACK = 110         

# Velocidades 
DEFAULT_DRIVE_SPEED = 150       
DEFAULT_DRIVE_ACCELERATION = 200  
DEFAULT_TURN_RATE = 120         
DEFAULT_TURN_ACCELERATION = 200  

#pala
PALA_SPEED = 200         
PALA_DOWN_ANGLE = 90     
PALA_UP_ANGLE = -90      


class RobotHardware:
    def __init__(self):
        self.ev3 = EV3Brick()

        # Motores de movimiento
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
    # MOVIMIENTO
    
    def move_straight(self, distance_mm):
        self.drive_base.straight(distance_mm)

    def turn(self, angle_deg):
        self.drive_base.turn(angle_deg)

    def drive(self, speed, turn_rate):
        self.drive_base.drive(speed, turn_rate)

    def stop(self):
        self.drive_base.stop()

    # SENSORES

    def read_color(self):
        return self.color_sensor.color()

    def read_reflection(self):
        return self.color_sensor.reflection()

    def read_rgb(self):
        return self.color_sensor.rgb()

    def read_gyro_angle(self):
        if self.gyro_sensor is None:
            return 0
        return self.gyro_sensor.angle()

    def reset_gyro(self, angle=0):
        if self.gyro_sensor is not None:
            self.gyro_sensor.reset_angle(angle)


    # PALA (RECOGIDA / ENTREGA)

    def pala_bajar(self):
        self.pala_motor.run_until_stalled(-PALA_SPEED, then=Stop.HOLD, duty_limit=40)
        self.pala_down = True
        self.ev3.speaker.beep(frequency=600, duration=100)

    def pala_subir(self):
        self.pala_motor.run_until_stalled(PALA_SPEED, then=Stop.HOLD, duty_limit=40)
        self.pala_down = False
        self.ev3.speaker.beep(frequency=400, duration=100)

    # =========================================================================
    # ODOMETRÍA
    # =========================================================================

    def get_odometry(self):
        return self.drive_base.state()

    def get_distance(self):
        return self.drive_base.distance()

    def get_angle(self):
        return self.drive_base.angle()

    def reset_odometry(self):
        self.drive_base.reset()

    # =========================================================================
    # INTERFAZ DEL LADRILLO
    # =========================================================================

    def display_text(self, text, line=5):
        self.ev3.screen.clear()
        self.ev3.screen.draw_text(10, line, text)

    def beep(self, frequency=500, duration=200):
        self.ev3.speaker.beep(frequency=frequency, duration=duration)

    def set_light(self, color):
        self.ev3.light.on(color)

    def is_button_pressed(self):
        return len(self.ev3.buttons.pressed()) > 0

    def get_battery_voltage(self):
        return self.ev3.battery.voltage()

    # =========================================================================
    # MELODÍAS
    # =========================================================================

    def play_delivery_song(self):
        melody = [
            (800, 200),
            (1000, 200),
            (1200, 200),
            (1400, 300),
            (1200, 150),
            (1400, 150),
            (1600, 300),
        ]
        
        print("Reproduciendo melodía de entrega...")
        for freq, duration in melody:
            self.ev3.speaker.beep(frequency=freq, duration=duration)
            wait(50)
