# 🤖 Robot de Reparto — Equipo F

**Inteligencia Ambiental — Universidad de Jaén — 2026**

Robot autónomo de reparto de paquetería basado en LEGO Mindstorms EV3 con aplicación web cliente y comunicación MQTT.

---

## 📋 Estructura del proyecto

```
├── robot/                  # Código MicroPython para el EV3
│   ├── main.py             # Punto de entrada del robot
│   ├── hardware.py         # Abstracción del hardware (motores, sensores)
│   ├── map_parser.py       # Decodificación del mapa de la ciudad
│   ├── navigation.py       # Pathfinding (BFS) y control de navegación
│   └── mqtt_client.py      # Cliente MQTT para comunicación
├── webapp/                 # Aplicación web cliente
│   ├── index.html          # Página principal
│   ├── styles.css          # Estilos (tema oscuro premium)
│   ├── app.js              # Lógica principal + MQTT WebSocket
│   └── map_renderer.js     # Renderizador del mapa en Canvas
└── README.md
```

## 🚀 Cómo empezar

### Aplicación web (cliente)

1. Abrir `webapp/index.html` directamente en el navegador
2. Por defecto arranca en **modo simulación** (sin necesidad de broker MQTT)
3. Para conectar al broker real, editar `app.js` y cambiar `SIMULATION_MODE: false`

### Robot (EV3)

1. Abrir el proyecto en VS Code con las extensiones:
   - **LEGO MINDSTORMS EV3 MicroPython**
   - **ev3dev-browser**
2. Conectar al EV3 vía USB o WiFi
3. Subir la carpeta `robot/` al EV3
4. Ejecutar `main.py`

> ⚠️ **No extraer la tarjeta SD del robot**. El firmware Pybricks ya está instalado.

### Configuración de red

| Parámetro | Valor |
|-----------|-------|
| SSID WiFi | `domotica` |
| Contraseña | `domotica` |
| IP Broker MQTT | `192.168.1.122` |
| Puerto MQTT | `1883` |
| Puerto WebSockets | `8083` |
| Topic mapa | `map` |

## 🔧 Configuración del hardware

Editar los puertos en `robot/hardware.py` según la conexión real del robot:

| Componente | Puerto por defecto |
|------------|-------------------|
| Motor izquierdo | `Port.B` |
| Motor derecho | `Port.C` |
| Motor pala | `Port.A` |
| Sensor color | `Port.S3` |
| Sensor giroscópico | `Port.S2` |

Parámetros a calibrar:
- `WHEEL_DIAMETER`: Diámetro de rueda en mm (default: 55.5)
- `AXLE_TRACK`: Distancia entre ejes en mm (default: 104)
- `PALA_DOWN_ANGLE` / `PALA_UP_ANGLE`: Ángulos de la pala

## 📡 Topics MQTT

| Topic | Dirección | Descripción |
|-------|-----------|-------------|
| `map` | Broker → Robot/Web | Mapa codificado (cada 60s) |
| `Equipo F/pedidos` | Web → Robot | Pedidos JSON `{pickup, delivery}` |
| `Equipo F/odometria` | Robot → Web | Odometría JSON (≥1 Hz) |
| `Equipo F/estado` | Robot → Web | Estado del robot |

## 🗺️ IDs de bloques del mapa

| ID | Tipo | Direcciones |
|----|------|-------------|
| 00 | Edificio | — |
| 01 | Calle | ← → |
| 02 | Calle | ↑ ↓ |
| 03 | Calle | ↑ → |
| 04 | Calle | → ↓ |
| 05 | Calle | ↓ ← |
| 06 | Calle | ← ↑ |
| 07 | Calle | ← ↑ → |
| 08 | Calle | ↑ → ↓ |
| 09 | Calle | → ↓ ← |
| 10 | Calle | ↓ ← ↑ |
| 11 | Calle | ↑ → ↓ ← |
