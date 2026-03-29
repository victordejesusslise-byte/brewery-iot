# 🍺 Brewery IoT — Pipeline de Dados

Pipeline de monitoramento de temperatura para cervejaria artesanal.
Captura leituras do sensor DS18B20 via ESP32, processa com Node-RED
e persiste no Google Sheets com visualização em Grafana Cloud.

```
ESP32 (DS18B20)  →  Mosquitto MQTT  →  Node-RED  →  Google Sheets  →  Grafana Cloud
                         [Docker]         [Docker]
```

---

## Estrutura do Repositório

```
brewery-iot/
├── .env.example                    # Template de variáveis (copie → .env)
├── .gitignore
├── docker-compose.yml              # Mosquitto + Node-RED
├── requirements.txt                # Dependências Python (scripts utilitários)
│
├── mosquitto/
│   └── config/
│       ├── mosquitto.conf          # Configuração do broker
│       └── passwd                  # Senhas (gerado pelo script setup)
│
├── node-red/
│   ├── flows/
│   │   └── brewery_flow.json       # Flow principal com queue/retry
│   └── data/
│       ├── settings.js             # Configuração do Node-RED
│       ├── package.json            # Dependências (google-sheets)
│       └── credentials/            # Service Account JSON (NÃO versionar)
│
├── scripts/
│   ├── setup_mosquitto_users.sh    # Cria usuários no broker
│   └── test_mqtt_connection.py     # Simula publicação do ESP32
│
└── docs/
    └── esp32-mqtt-connection.md    # Contrato de interface MQTT para o firmware
```

---

## Pré-requisitos

### Com Docker (recomendado)

| Requisito       | Versão mínima |
|-----------------|---------------|
| Docker Engine   | 24.x          |
| Docker Compose  | v2.x          |

### Sem Docker (somente scripts utilitários)

| Requisito       | Versão mínima |
|-----------------|---------------|
| Python          | 3.10          |
| pip             | 23.x          |
| Mosquitto CLI   | 2.x (opcional)|

---

## Setup Inicial

### 1 — Clone o repositório

```bash
git clone https://github.com/Cajuz/brewery-iot.git
cd brewery-iot
```

### 2 — Configure as variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` e preencha **todos** os campos:

```bash
nano .env   # ou code .env, vim .env ...
```

Campos obrigatórios antes de subir:

| Campo                    | Onde obter                                     |
|--------------------------|------------------------------------------------|
| `MQTT_ESP32_PASSWORD`    | Defina uma senha forte                         |
| `MQTT_NODERED_PASSWORD`  | Defina uma senha forte                         |
| `GOOGLE_SHEET_ID`        | URL da planilha: `/spreadsheets/d/<ID>/edit`  |

### 3 — Configure a Service Account do Google

1. Acesse [console.cloud.google.com](https://console.cloud.google.com)
2. Crie um projeto → ative **Google Sheets API**
3. Crie uma **Service Account** → baixe o JSON de credenciais
4. Salve o arquivo em: `node-red/data/credentials/google-service-account.json`
5. **Compartilhe** a planilha com o e-mail da Service Account (permissão de Editor)

### 4 — Crie os usuários MQTT

```bash
bash scripts/setup_mosquitto_users.sh
```

> Isso cria o arquivo `mosquitto/config/passwd` com os usuários
> `esp32` e `nodered` com as senhas definidas no `.env`.

---

## Rodando com Docker

### Subir todos os serviços

```bash
docker compose up -d
```

### Verificar status

```bash
docker compose ps
docker compose logs -f
```

### Acessar Node-RED

Abra no browser: [http://localhost:1880](http://localhost:1880)

Login: usuário e senha definidos em `NODERED_ADMIN_USER` / `NODERED_ADMIN_PASSWORD`.

### Instalar dependência do Google Sheets no Node-RED

```bash
docker compose exec nodered npm install node-red-contrib-google-sheets
docker compose restart nodered
```

### Parar os serviços

```bash
docker compose down
```

---

## Rodando sem Docker

### Mosquitto local

**Ubuntu/Debian:**
```bash
sudo apt-get install mosquitto mosquitto-clients
sudo systemctl enable --now mosquitto
```

**macOS:**
```bash
brew install mosquitto
brew services start mosquitto
```

Configure o arquivo `/etc/mosquitto/mosquitto.conf` (ou equivalente)
apontando para `mosquitto/config/mosquitto.conf` deste repositório,
e crie os usuários manualmente:

```bash
mosquitto_passwd -b mosquitto/config/passwd esp32 SUA_SENHA
mosquitto_passwd -b mosquitto/config/passwd nodered SUA_SENHA_NR
```

### Node-RED local

```bash
npm install -g node-red
npm install -g node-red-contrib-google-sheets
node-red --userDir ./node-red/data --port 1880
```

### Scripts utilitários Python

```bash
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Testando a Pipeline

### 1 — Simular publicação do ESP32

```bash
python scripts/test_mqtt_connection.py
```

Ou via CLI:

```bash
source .env
mosquitto_pub \
  -h ${MQTT_BROKER_HOST} -p ${MQTT_BROKER_PORT} \
  -u ${MQTT_ESP32_USER} -P ${MQTT_ESP32_PASSWORD} \
  -t ${MQTT_TOPIC_TEMPERATURE} \
  -m '{"temperature":23.5,"unit":"C","device_id":"esp32_01"}' \
  -q 1
```

### 2 — Verificar no Node-RED

Acesse [http://localhost:1880](http://localhost:1880) e observe
os nós do flow `Brewery IoT — DS18B20` — os status badges mostram
o estado da fila e das escritas no Sheets.

### 3 — Verificar no Google Sheets

Abra a planilha configurada em `GOOGLE_SHEET_ID` e confirme
que uma nova linha foi adicionada na aba `sensor_readings`.

---

## Formato dos Dados

### Payload MQTT (ESP32 → Broker)

```json
{
  "temperature": 23.5,
  "unit": "C",
  "device_id": "esp32_01"
}
```

### Linha no Google Sheets (sensor_readings)

| timestamp              | device_id  | temperature_c | unit |
|------------------------|------------|---------------|------|
| 2026-03-29T15:00:00Z   | esp32_01   | 23.5          | C    |

---

## Tratativa de Erros (Falha Crítica — Sheets)

| Erro            | Comportamento                                              |
|-----------------|------------------------------------------------------------|
| `429` Rate Limit| Pausa `RETRY_DELAY_SECONDS` (padrão 60s) e tenta novamente |
| `401` Auth      | Loga o evento e aguarda 5s para retry                      |
| Timeout/Offline | Aguarda 5 minutos e tenta novamente                        |
| Max tentativas  | Descarta da fila e grava em `buffer.csv` local             |

A fila mantém até `QUEUE_MAX_SIZE` mensagens (padrão 500).
Descarta a mais antiga se a fila encher.

---

## Conexão com o ESP32

Veja [`docs/esp32-mqtt-connection.md`](docs/esp32-mqtt-connection.md)
para o contrato de interface MQTT que o firmware deve implementar.

---

## Variáveis de Ambiente

Todas as variáveis estão documentadas em `.env.example`.

---

## Licença

MIT
