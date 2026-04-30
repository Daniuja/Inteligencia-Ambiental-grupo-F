# 🚀 Guía Rápida — Robot de Reparto Equipo F

## Requisitos Previos
- **Mosquitto** instalado en el PC (`C:\Program Files\mosquitto\`)
- **VS Code** con la extensión **LEGO MINDSTORMS EV3 MicroPython**
- PC y Robot EV3 conectados a la **misma red Wi-Fi** (ej: `domotica2`)

---

## Paso 1: Configurar la IP

Cada vez que cambies de red Wi-Fi o de ordenador, ejecuta este script para actualizar la IP del broker MQTT:

```bash
# En la raíz del proyecto (Inteligencia-Ambiental-grupo-F/)
python set_ip.py <TU_IP>
```

**¿Cómo saber tu IP?** Abre una terminal y ejecuta `ipconfig`. Busca la IP de tu adaptador Wi-Fi (será algo como `192.168.0.XXX`).

**Ejemplo:**
```bash
python set_ip.py 192.168.0.100
```

Esto actualiza automáticamente tanto `webapp/app.js` como `robot/mqtt_client.py`.

---

## Paso 2: Arrancar Mosquitto (Broker MQTT)

Abre una terminal y ejecuta:

```bash
& "C:\Program Files\mosquitto\mosquitto.exe" -v -c mosquitto.conf
```

> ⚠️ **Deja esta terminal abierta.** Si la cierras, el broker se apaga y el robot pierde la conexión.

---

## Paso 3: Subir código al Robot y ejecutarlo

1. Conecta el robot al PC con el **cable USB**.
2. En VS Code, abre el panel **EV3DEV DEVICE BROWSER** (barra lateral izquierda, icono del robot).
3. Conecta al robot (punto verde = conectado).
4. Haz clic en la **flechita 📥** para subir los archivos al robot.
5. Abre un **SSH Terminal** (clic derecho en "ev3dev" → "Open SSH Terminal").
6. Ejecuta el programa:
   ```bash
   brickrun --directory="/home/robot/ProyectoLEGO/Inteligencia-Ambiental-grupo-F/robot" "/home/robot/ProyectoLEGO/Inteligencia-Ambiental-grupo-F/robot/main.py"
   ```
7. Cuando veas **"Esperando mapa..."**, ya puedes **desconectar el cable USB**. El robot sigue funcionando por Wi-Fi.

---

## Paso 4: Abrir la Web y mandar pedidos

1. Abre `webapp/index.html` en el navegador.
2. Pulsa **F5** para recargar (asegura que usa la IP correcta).
3. La web enviará el mapa al robot automáticamente.
4. ¡Añade un pedido desde la interfaz y el robot se moverá!

---

## Solución de problemas

| Problema | Solución |
|----------|----------|
| Robot dice "Conectando al broker MQTT..." y no avanza | Comprueba que Mosquitto está corriendo y que la IP es correcta (`python set_ip.py <TU_IP>`) |
| Error `ENODEV` al arrancar el robot | Revisa los cables de motores/sensores en el robot |
| La web no conecta | Asegúrate de estar en la misma Wi-Fi que el robot y recarga con F5 |
| Bucle infinito de "Mapa enviado" en la web | Recarga la página (F5), ya está corregido en el código |
