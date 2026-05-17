# Presentacion: Robot de reparto autonomo - Grupo F

Duracion objetivo: 15-18 minutos, dejando 2-3 minutos para preguntas o incidencias en la demostracion.

## Diapositiva 1. Titulo

**Robot de reparto autonomo sobre mapa urbano**

- Grupo F
- Inteligencia Ambiental
- LEGO EV3 + aplicacion web + MQTT

Notas para exponer:

Presentar brevemente el proyecto: un robot que recibe pedidos, calcula rutas y se mueve por el tablero para recoger y entregar paquetes.

Tiempo aproximado: 1 minuto.

## Diapositiva 2. Objetivo del sistema

- Recibir pedidos desde una aplicacion web.
- Interpretar un mapa de calles y edificios.
- Calcular una ruta valida entre recogida y entrega.
- Mover el robot de forma autonoma siguiendo la linea verde.
- Publicar posicion, estado y odometria durante el recorrido.

Notas para exponer:

Explicar que no es solo mover el robot, sino integrar planificacion, comunicacion, interfaz y control fisico.

Tiempo aproximado: 1 minuto.

## Diapositiva 3. Arquitectura general

```text
Aplicacion web
     |
     | MQTT WebSocket
     v
Broker Mosquitto
     |
     | MQTT TCP
     v
Robot EV3
```

- La web envia mapa, posicion inicial y pedidos.
- El robot recibe pedidos y ejecuta la navegacion.
- El robot publica odometria y estado.

Notas para exponer:

Esta diapositiva sirve para explicar la division de responsabilidades. La web no conduce el robot, solo envia ordenes y visualiza informacion. La autonomia esta en el EV3.

Tiempo aproximado: 2 minutos.

## Diapositiva 4. Decision de diseno: mapa como grafo

- El mapa llega como una cadena de IDs de bloques.
- Cada bloque indica que direcciones permite.
- Se transforma en una matriz de 7 x 5.
- Despues se crea un grafo de conexiones.
- Solo se conectan dos casillas si ambas tienen entrada/salida compatible.

Notas para exponer:

Explicar que esta decision simplifica la planificacion: en vez de trabajar con pixeles o coordenadas reales, el robot planifica sobre casillas conectadas.

Tiempo aproximado: 2 minutos.

## Diapositiva 5. Decision de diseno: BFS para calcular rutas

- Se usa busqueda en anchura.
- Todas las casillas tienen el mismo coste.
- BFS encuentra la ruta con menor numero de pasos.
- La ruta se convierte despues en direcciones: arriba, derecha, abajo, izquierda.

Notas para exponer:

Justificar por que no se uso un algoritmo mas complejo: para este mapa, BFS es suficiente, simple y fiable.

Tiempo aproximado: 1 minuto y medio.

## Diapositiva 6. Aplicacion web y MQTT

- La web permite seleccionar recogida y entrega.
- Muestra el mapa y la posicion del robot.
- Se comunica con el robot mediante topics MQTT.
- Topics principales:
  - `map`
  - `Equipo F/pedidos`
  - `Equipo F/odometria`
  - `Equipo F/estado`
  - `Equipo F/posicion_inicial`

Notas para exponer:

Comentar que MQTT facilita desacoplar web y robot. La web no necesita saber como navega el robot, y el robot solo consume mensajes sencillos.

Tiempo aproximado: 2 minutos.

## Diapositiva 7. Control del robot

- Dos motores grandes para traccion diferencial.
- Un motor mediano para la pala.
- Sensor de color para linea verde y cuadrados negros.
- Sensor giroscopico disponible para orientacion.
- `hardware.py` centraliza el acceso al hardware.

Notas para exponer:

Explicar que se encapsulo el hardware para que la navegacion no dependiera directamente de los puertos o detalles fisicos.

Tiempo aproximado: 1 minuto y medio.

## Diapositiva 8. Seguimiento de linea verde

- El sensor lee valores RGB.
- Se calcula la verdosidad:

```text
G - max(R, B)
```

- Si supera el umbral, se considera linea verde.
- Se usa un controlador proporcional-derivativo.
- El robot corrige su giro mientras avanza.

Notas para exponer:

Explicar rapidamente el PD: la parte proporcional corrige segun el error actual y la derivativa suaviza la respuesta mirando como cambia ese error.

Tiempo aproximado: 2 minutos.

## Diapositiva 9. Deteccion de casillas negras

- Los cuadrados negros marcan centros de casilla.
- El robot distingue:
  - salida del cuadrado actual,
  - frontera entre bloques,
  - llegada al centro del siguiente bloque.
- Se usa una maquina de estados para no parar antes de tiempo.

Notas para exponer:

Esta es una decision importante: no basta con detectar negro una vez, porque hay lineas negras de frontera y cuadrados negros centrales. Por eso se usan fases.

Tiempo aproximado: 2 minutos.

## Diapositiva 10. Calibracion y problemas reales

- El sensor esta delante y a la izquierda del centro del robot.
- Los giros a izquierda y derecha no se comportaban igual.
- Los giros de 180 grados se forzaron hacia la izquierda.
- En giros a la derecha:
  - se redujo el giro,
  - se avanza un poco buscando verde,
  - si no se encuentra, se hace busqueda en abanico.

Notas para exponer:

Esta diapositiva es clave para hablar de decisiones practicas. Explicar que el algoritmo teorico funcionaba, pero hubo que adaptarlo al comportamiento fisico real del robot.

Tiempo aproximado: 2 minutos.

## Diapositiva 11. Demostracion practica

Orden recomendado para la demo:

1. Abrir la web.
2. Mostrar el mapa cargado.
3. Seleccionar punto de recogida y entrega.
4. Enviar pedido.
5. Enseñar como el robot:
   - calcula la ruta,
   - sigue la linea,
   - gira en intersecciones,
   - recoge y entrega.

Notas para exponer:

Mientras el robot se mueve, una persona puede explicar que esta pasando en cada fase y otra puede vigilar el robot por si hay que recolocarlo.

Tiempo aproximado: 3-4 minutos.

## Diapositiva 12. Resultados y conclusiones

- El sistema integra web, MQTT y robot fisico.
- El robot puede ejecutar pedidos completos.
- La parte mas dificil fue la calibracion real.
- La arquitectura modular permitio ajustar componentes sin rehacer todo.
- Posibles mejoras:
  - mas sensores,
  - calibracion desde la web,
  - mejor medicion automatica de tiempos,
  - visualizacion de ruta planificada.

Notas para exponer:

Cerrar destacando aprendizaje: la diferencia entre que un algoritmo funcione en codigo y que funcione en un robot real sobre un tablero.

Tiempo aproximado: 1-2 minutos.

## Reparto sugerido para la exposicion

| Bloque | Duracion | Contenido |
|---|---:|---|
| Introduccion | 2 min | Objetivo y arquitectura |
| Diseno software | 5 min | Web, MQTT, mapa como grafo y BFS |
| Diseno robot | 6 min | Hardware, linea verde, negros, calibracion |
| Demostracion | 4 min | Pedido real y movimiento del robot |
| Cierre | 1 min | Resultados y mejoras |

