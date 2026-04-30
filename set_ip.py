import os
import re
import sys

def update_ip(new_ip):
    # Rutas relativas a los archivos
    app_js_path = os.path.join("webapp", "app.js")
    mqtt_py_path = os.path.join("robot", "mqtt_client.py")
    
    # 1. Actualizar webapp/app.js
    if os.path.exists(app_js_path):
        with open(app_js_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Reemplazar BROKER_HOST y BROKER_URL usando expresiones regulares
        content = re.sub(r"BROKER_HOST:\s*'[^']+'", f"BROKER_HOST: '{new_ip}'", content)
        content = re.sub(r"BROKER_URL:\s*'ws://[^:]+:9001'", f"BROKER_URL: 'ws://{new_ip}:9001'", content)
        
        with open(app_js_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✔️ Webapp (app.js) actualizada a {new_ip}")
    else:
        print(f"❌ No se encontró {app_js_path}")
        
    # 2. Actualizar robot/mqtt_client.py
    if os.path.exists(mqtt_py_path):
        with open(mqtt_py_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Reemplazar MQTT_BROKER
        content = re.sub(r'MQTT_BROKER\s*=\s*"[^"]+"', f'MQTT_BROKER = "{new_ip}"', content)
        
        with open(mqtt_py_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✔️ Robot (mqtt_client.py) actualizado a {new_ip}")
    else:
        print(f"❌ No se encontró {mqtt_py_path}")
        
    print("\n✅ ¡Cambio de IP completado con éxito! Recuerda volver a pasar la carpeta 'robot' al EV3.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        ip = sys.argv[1]
    else:
        print("=== CONFIGURADOR DE IP PARA MQTT ===")
        ip = input("Introduce la IP de tu ordenador (Ej: 192.168.56.1): ")
    
    if ip.strip():
        update_ip(ip.strip())
    else:
        print("No se introdujo ninguna IP válida.")
