#!/usr/bin/env python3
"""
Testa a conexão MQTT com o broker Mosquitto.
Simula uma publicação do ESP32 com payload de temperatura DS18B20.

Uso:
    pip install -r requirements.txt
    python scripts/test_mqtt_connection.py

Pré-requisito: .env preenchido e Mosquitto rodando.
"""

import json
import time
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import paho.mqtt.client as mqtt

load_dotenv(Path(__file__).parent.parent / ".env")

BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
TOPIC       = os.getenv("MQTT_TOPIC_TEMPERATURE", "brewery/sensors/temperature")  # FIX 2
ESP32_USER  = os.getenv("MQTT_ESP32_USER", "esp32")
ESP32_PASS  = os.getenv("MQTT_ESP32_PASSWORD", "")

received_messages = []


def on_connect(client, userdata, flags, *args):  # FIX 1
    rc = args[0] if args else 0
    rc_value = rc if isinstance(rc, int) else rc.value
    codes = {0: "OK", 1: "Bad protocol", 2: "Rejected ID",
             3: "Broker unavailable", 4: "Bad credentials", 5: "Unauthorized"}
    if rc_value == 0:
        print(f"✅ Conectado ao broker {BROKER_HOST}:{BROKER_PORT}")
        client.subscribe(TOPIC, qos=1)
        print(f"📡 Subscrito em: {TOPIC}")
    else:
        print(f"❌ Falha na conexão: {codes.get(rc_value, rc_value)}")
        sys.exit(1)


def on_message(client, userdata, msg):
    print(f"\n📥 Mensagem recebida:")
    print(f"   Tópico : {msg.topic}")
    print(f"   QoS    : {msg.qos}")
    try:
        payload = json.loads(msg.payload.decode())
        print(f"   Payload: {json.dumps(payload, indent=6)}")
    except Exception:
        print(f"   Payload (raw): {msg.payload}")
    received_messages.append(msg)


def on_publish(client, userdata, mid):
    print(f"✅ Publicação confirmada (mid={mid})")


def main():
    print("=" * 55)
    print("  BREWERY IoT — Teste de Conexão MQTT")
    print(f"  Broker : {BROKER_HOST}:{BROKER_PORT}")
    print(f"  Usuário: {ESP32_USER}")
    print(f"  Tópico : {TOPIC}")
    print("=" * 55)

    client = mqtt.Client(client_id="test_esp32_simulator", protocol=mqtt.MQTTv311)
    client.username_pw_set(ESP32_USER, ESP32_PASS)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_publish = on_publish

    try:
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    except ConnectionRefusedError:
        print(f"❌ Conexão recusada — broker está rodando em {BROKER_HOST}:{BROKER_PORT}?")
        sys.exit(1)

    client.loop_start()
    time.sleep(1)

    payload = {
        "temperature": 23.5,
        "unit": "C",
        "device_id": "esp32_test"
    }

    print(f"\n📤 Publicando payload de teste...")
    result = client.publish(TOPIC, json.dumps(payload), qos=1)
    result.wait_for_publish(timeout=5)

    print("\n⏳ Aguardando mensagem de volta por 3s...")
    time.sleep(3)

    client.loop_stop()
    client.disconnect()

    if received_messages:
        print(f"\n✅ Teste concluído! {len(received_messages)} mensagem(ns) recebida(s).")
    else:
        print("\n⚠️  Nenhuma mensagem recebida. Broker aceitou a conexão mas não roteou.")


if __name__ == "__main__":
    main()