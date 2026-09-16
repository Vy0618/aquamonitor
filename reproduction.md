# Aqua Monitor — Guia de Reprodução do Ambiente

> **Repositório:** https://github.com/Vy0618/aquamonitor  
> **Projeto:** Monitoramento de estações de coleta com visão computacional  
> **Pipeline:** SSD MobileNet V3 + ByteTrack → FastAPI → MongoDB → Dashboard Leaflet  
> **Última atualização:** Setembro 2026

Este guia ensina a reproduzir o ambiente completo do projeto **Aqua Monitor** em outra máquina, incluindo o servidor FastAPI, o pipeline de reconhecimento de imagem (detecção de garrafas plásticas via SSD MobileNet V3 + ByteTrack), e o dashboard web.

Cobertura: **Linux** e **Windows**.

---

## 1. Pré-requisitos do Sistema

### 1.1 Ferramentas gerais (Linux + Windows)

| Ferramenta | Versão mínima | Finalidade |
|---|---|---|
| **Git** | 2.30+ | Clonar o repositório |
| **Python** | 3.12.x | Backend e pipeline de detecção |
| **pip** | 23.0+ | Instalar dependências Python |
| **MongoDB** | 6.0+ | Armazenar estações, métricas e eventos |
| **Node.js** | 18+ | Servir o dashboard estaticamente |
| **OpenCV** | 4.8+ | Dependência do pipeline (instalada via pip) |

### 1.2 Linux — Instalação dos pré-requisitos

```bash
# Debian/Ubuntu
sudo apt update
sudo apt install -y git python3.12 python3.12-venv python3-pip \
    mongodb pipx

# Verificar versões
python3 --version    # deve ser 3.12.x
pip --version
mongod --version
node --version
```

> **Se seu distribuição não tem Python 3.12 nos repositórios**, use o deadsnakes PPA ou compile from source:
> ```bash
> sudo add-apt-repository ppa:deadsnakes/ppa
> sudo apt update
> sudo apt install -y python3.12 python3.12-venv python3.12-dev
> ```

### 1.3 Windows — Instalação dos pré-requisitos

1. **Python 3.12.x** — Baixe o instalador em https://www.python.org/downloads/  
   ⚠️ **Marque "Add Python to PATH"** durante a instalação.

2. **Git** — Baixe em https://git-scm.com/download/win  
   Use o Git Bash (vem com Git for Windows).

3. **MongoDB Community** — Baixe em https://www.mongodb.com/try/download/community  
   Ou use o instalador MSIs. Configure como serviço Windows.

   Alternativa rápida (via winget):
   ```powershell
   winget install MongoDB.Manifest
   ```

4. **Node.js** — Baixe em https://nodejs.org/ (LTS 18+)

5. **Microsoft Visual C++ Build Tools** — Necessário para compilar o `lap` e `cython-bbox`  
   Baixe em: https://visualstudio.microsoft.com/visual-cpp-build-tools/  
   Instale o workload **"Desktop development with C++"**.

---

## 2. Clonar o Repositório

```bash
git clone https://github.com/Vy0618/aquamonitor.git
cd aquamonitor
```

### 2.1 Verificar estrutura após clonar

```bash
# Linux
find . -maxdepth 3 -type f | sort | head -40

# Windows (PowerShell)
Get-ChildItem -Recurse -File -Depth 3 | Sort-Object FullName | Select-Object -First 40 FullName
```

Você deve ver, no mínimo:
```
├── backend/
│   ├── app.py
│   ├── requirements.txt
│   ├── test_station_metrics.py
│   ├── test_bottle_events.py
│   ├── test_bottle_count.py
│   └── detection/
│       ├── config.py
│       ├── geometry.py
│       ├── line_counter.py
│       ├── tracker.py
│       ├── detection_pipeline.py
│       ├── api_client.py
│       ├── object-ident.py
│       └── models/
│           ├── coco.names
│           ├── frozen_inference_graph.pb
│           └── ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt
├── dashboard/
│   ├── index.html
│   ├── crud.html
│   ├── style.css
│   ├── cadastro-style.css
│   └── js/
│       ├── main.js, api.js, bottle-counter.js, map.js,
│       ├── heatmap.js, markers.js, filters.js, crud.js,
│       ├── uptime.js, zoom.js, config.js
├── stations.json
├── requirements.txt
└── .gitignore
```

### 2.2 Verificar arquivos de modelo

O repositório agora inclui os arquivos de modelo no Git (as regras `*.pb` e `*.pbtxt` foram removidas do `.gitignore`). Após clonar, verifique se estão presentes:

```bash
ls backend/detection/models/
```

Você deve ver:
```
coco.names
frozen_inference_graph.pb
ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt
```

- **`coco.names`** — 90 classes COCO (necessário para mapear class_id para nome)
- **`frozen_inference_graph.pb`** — Pesos do SSD MobileNet V3 Large COCO
- **`ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt`** — Configuração do modelo

**Se algum arquivo estiver faltando**, baixe manualmente:
- **Modelo:** https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_2018-08-23/faster_rcnn_resnet50_coco.tar.gz
- Ou via OpenCV model zoo: http://github.com/opencv/opencv/wiki/TensorFlow-object-detection-api
- Procure por `ssd_mobilenet_v3_large_coco_2020_01_14.pb` e `.pbtxt`
- Coloque os dois arquivos em `backend/detection/models/`

---

## 3. Configurar o MongoDB

### 3.1 Linux

```bash
# Iniciar o serviço
sudo systemctl start mongod
sudo systemctl enable mongod

# Verificar status
sudo systemctl status mongod

# Testar conexão
mongosh
# No shell do mongosh:
db.runCommand({ping: 1})   # deve retornar { ok: 1 }
exit
```

Se o MongoDB não inicia (problema de permissão):
```bash
sudo chown -R mongodb:mongodb /var/lib/mongodb /var/log/mongodb
sudo rm -f /tmp/mongodb-27017.sock
sudo systemctl restart mongod
```

### 3.2 Windows

```powershell
# Iniciar o MongoDB como serviço
net start MongoDB

# Ou rodar manualmente (ajuste o caminho do exe)
"C:\Program Files\MongoDB\Server\7.0\bin\mongod.exe" --dbpath="C:\data\db"

# Em outro terminal, testar:
"C:\Program Files\MongoDB\Server\7.0\bin\mongosh.exe"
> db.runCommand({ping: 1})
```

### 3.3 Criar o banco de dados e importar dados de exemplo

```bash
# O banco é criado automaticamente ao inserir o primeiro documento.
# Importar os dados de exemplo (30 estações):
mongosh --eval '
use aquamonitor
db.stations.insertMany(
  JSON.parse(
    await (new TextDecoder().decode(await (await fetch("file:///caminho/absoluto/para/stations.json")).arrayBuffer()))
  )
)
'

# Ou mais simplesmente com mongoimport:
mongoimport --db aquamonitor --collection stations --file stations.json --jsonArray
```

> O arquivo `stations.json` contém 30 documentos de exemplo com localizações GeoJSON.

---

## 4. Configurar o Ambiente Python (Backend + Detecção)

### 4.1 Criar o venv e instalar dependências (Linux + Windows)

**Linux:**
```bash
cd /home/vyzxc/aquamonitor  # ou o diretório onde clonou
python3.12 -m venv .venv
source .venv/bin/activate

# Atualizar pip
pip install --upgrade pip

# Instalar dependências
pip install -r requirements.txt
```

**Windows (Git Bash ou PowerShell):**
```bash
cd C:\Users\seu_usuario\aquamonitor
python -m venv .venv
.venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
```

### 4.2 Verificar instalação

```bash
python -c "
import fastapi, uvicorn, pydantic, pymongo, cv2, numpy, requests
import supervision
print('Todas as importações OK')
print(f'fastapi: {fastapi.__version__}')
print(f'supervision: {supervision.__version__}')
print(f'cv2: {cv2.__version__}')
print(f'numpy: {numpy.__version__}')
"
```

> ⚠️ Se `supervision` falhar ao importar, verifique se `lap` e `cython-bbox` foram instalados corretamente (dependem de compilação C++ no Windows).

### 4.3 `requirements.txt` (conteúdo)

```
fastapi>=0.141.0
uvicorn>=0.52.0
pydantic>=2.0.0
pymongo
opencv-python
supervision==0.27.0
lap==0.5.12
cython-bbox==0.1.5
numpy==1.26.4
requests
```

> **Nota sobre `lap` e `cython-bbox` no Windows:** Esses pacotes exigem compilação C++. Se a instalação falhar, tente instalar os wheels pré-compilados:
> ```bash
> pip install lap --only-binary=:all:
> pip install cython-bbox --only-binary=:all:
> ```
> Ou compile o Visual C++ Build Tools conforme seção 1.3.

---

## 5. Configurar o Venv Ultralytics (Opcional — Apenas para Treinamento YOLOv8)

O venv `ultralytics-env/` é excluído pelo `.gitignore`. Se estiver clonando um repositório limpo (sem ele), é necessário criar do zero.

```bash
# Linux + Windows
cd /home/vyzxc/aquamonitor
python3.12 -m venv ultralytics-env
```

**Linux:**
```bash
source ultralytics-env/bin/activate
pip install ultralytics==8.4.138
```

**Windows:**
```bash
ultralytics-env\Scripts\activate
pip install ultralytics==8.4.138
```

> O venv `ultralytics-env` é usado **apenas para treinamento de modelos YOLOv8**. O pipeline de detecção em produção usa SSD MobileNet via OpenCV DNN, **não** usa YOLOv8. Não é necessário para o funcionamento do sistema.

---

## 6. Rodar o Backend (FastAPI)

### 6.1 Iniciar o servidor

**Linux:**
```bash
cd /home/vyzxc/aquamonitor
source .venv/bin/activate
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

**Windows:**
```powershell
cd C:\Users\seu_usuario\aquamonitor
.venv\Scripts\activate
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

### 6.2 Verificar se está funcionando

```bash
# Testar a API
curl http://127.0.0.1:8000/api/stations

# Deve retornar JSON com a lista de estações
# Cada estação deve ter: station_id, location, administrative, detections, bottle_count
```

Também abra no navegador: http://127.0.0.1:8000/docs  
A documentação interativa do FastAPI deve aparecer.

### 6.3 Endpoints da API

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/stations` | Listar todas as estações com `bottle_count` |
| `POST` | `/api/stations` | Criar nova estação (body: estação completa) |
| `DELETE` | `/api/stations/{station_id}` | Deletar estação |
| `POST` | `/api/stations/{station_id}/bottle-count` | Ingestão de contagem agregada |
| `GET` | `/api/stations/{station_id}/bottle-count` | Última contagem da estação |
| `POST` | `/api/stations/{station_id}/bottle-events` | Ingestão de evento (idempotente) |

---

## 7. Rodar o Pipeline de Detecção (Reconhecimento de Imagem)

### 7.1 Sem publicação (modo local)

**Linux:**
```bash
cd /home/vyzxc/aquamonitor
source .venv/bin/activate
python backend/detection/object-ident.py
```

**Windows:**
```powershell
cd C:\Users\seu_usuario\aquamonitor
.venv\Scripts\activate
python backend\detection\object-ident.py
```

Isso abre a câmera padrão (índice 0) e processa frames a cada 0.25s com SSD MobileNet V3, contando garrafas que cruzam a linha de contagem (y=240 em frame 640×480).

Pressione **`q`** para sair.

### 7.2 Com publicação ao backend

```bash
python backend/detection/object-ident.py --publish
```

Ou via variável de ambiente:
```bash
export BOTTLE_COUNT_API_URL="http://127.0.0.1:8000"
export BOTTLE_COUNT_STATION_ID="1"
export BOTTLE_COUNT_PUBLISH_INTERVAL="5"
export BOTTLE_COUNT_API_ENABLED="1"
python backend/detection/object-ident.py
```

No Windows (PowerShell):
```powershell
$env:BOTTLE_COUNT_API_URL="http://127.0.0.1:8000"
$env:BOTTLE_COUNT_STATION_ID="1"
$env:BOTTLE_COUNT_PUBLISH_INTERVAL="5"
$env:BOTTLE_COUNT_API_ENABLED="1"
python backend\detection\object-ident.py --publish
```

### 7.3 Argumentos disponíveis

```bash
python backend/detection/object-ident.py --help
```

| Argumento | Padrão | Descrição |
|---|---|---|
| `--camera` | `0` | Índice da câmera OpenCV |
| `--width` | `640` | Largura do frame |
| `--height` | `480` | Altura do frame |
| `--detection-interval` | `0.25` | Intervalo entre detecções (segundos) |
| `--confidence` | `0.45` | Threshold de confiança da detecção |
| `--nms` | `0.2` | Threshold de Non-Maximum Suppression |
| `--publish` | `False` | Publicar agregados ao backend |

### 7.4 Usar vídeo ao invés de câmera

Para reproduzir um arquivo de vídeo em vez da câmera ao vivo, modifique `object-ident.py` ou passe um caminho de vídeo para `cv2.VideoCapture()`. Exemplo de modificação rápida no código:

```python
# Substituir no main() de object-ident.py:
camera = cv2.VideoCapture("caminho/para/video.mp4")
# Em vez de: camera = cv2.VideoCapture(args.camera)
```

---

## 8. Rodar o Dashboard (Frontend)

### 8.1 Servidor estático

**Linux:**
```bash
cd /home/vyzxc/aquamonitor/dashboard
python -m http.server 3000
```

**Windows:**
```powershell
cd C:\Users\seu_usuario\aquamonitor\dashboard
python -m http.server 3000
```

### 8.2 Acessar o dashboard

Abra no navegador: **http://127.0.0.1:3000**

O dashboard mostra:
- Mapa Leaflet com heatmap e marcadores
- Sidebar com uptime, contagem de garrafas, e filtros hierárquicos (estado → cidade → distrito)
- Polling ativo a cada 3 segundos no backend

### 8.3 Usar um servidor HTTP mais robusto (opcional)

Se preferir, use `http-server` via npm:
```bash
npm install -g http-server
cd dashboard
http-server -p 3000
```

---

## 9. Fluxo Completo de Inicialização

A sequência correta de inicialização é:

```
1. MongoDB  ──►  2. FastAPI (:8000)  ──►  3. Pipeline (opcional)  ──►  4. Dashboard (:3000)
```

### 9.1 Script de inicialização completa (Linux)

```bash
#!/bin/bash
# salvar como: start_all.sh
# uso: bash start_all.sh

echo "1. Verificando MongoDB..."
mongosh --eval 'db.runCommand({ping: 1})' || { echo "MongoDB não está rodando!"; exit 1; }

echo "2. Iniciando backend..."
cd /home/vyzxc/aquamonitor
source .venv/bin/activate
uvicorn backend.app:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
sleep 2

echo "3. Verificando API..."
curl -s http://127.0.0.1:8000/api/stations > /dev/null && echo "Backend OK" || echo "Backend DOWN"

echo "4. Iniciando dashboard..."
cd dashboard
python -m http.server 3000 &
DASHBOARD_PID=$!

echo ""
echo "========================================="
echo "Dashboard:  http://127.0.0.1:3000"
echo "API Docs:   http://127.0.0.1:8000/docs"
echo "Backend PID: $BACKEND_PID"
echo "Dashboard PID: $DASHBOARD_PID"
echo "========================================="
echo "Pressione Ctrl+C para parar."
wait
```

### 9.2 Script de inicialização completa (Windows PowerShell)

```powershell
# salvar como: start_all.ps1
# execução: powershell -ExecutionPolicy Bypass -File .\start_all.ps1

Write-Host "1. Verificando MongoDB..."
$mongodb = mongosh --eval 'db.runCommand({ping: 1})' 2>&1
if ($LASTEXITCODE -ne 0) { Write-Host "MongoDB nao esta rodando!" -ForegroundColor Red; exit 1 }
Write-Host "MongoDB OK" -ForegroundColor Green

Write-Host "2. Iniciando backend..."
cd C:\Users\seu_usuario\aquamonitor
& .venv\Scripts\activate
Start-Process -FilePath "uvicorn" -ArgumentList "backend.app:app --host 0.0.0.0 --port 8000" -NoNewWindow
Start-Sleep -Seconds 2

Write-Host "3. Verificando API..."
$api = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/stations" -UseBasicParsing -ErrorAction SilentlyContinue
if ($api) { Write-Host "Backend OK" -ForegroundColor Green } else { Write-Host "Backend DOWN" -ForegroundColor Red }

Write-Host "4. Iniciando dashboard..."
cd dashboard
Start-Process -FilePath "python" -ArgumentList "-m http.server 3000" -NoNewWindow

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Dashboard:  http://127.0.0.1:3000" -ForegroundColor Cyan
Write-Host "API Docs:   http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Pressione Ctrl+C para parar."
```

---

## 10. Execução da Detecção na Raspberry Pi

Para rodar o pipeline em uma Raspberry Pi:

### 10.1 Na Raspberry Pi

```bash
# Clonar o repositório
git clone https://github.com/Vy0618/aquamonitor.git
cd aquamonitor

# Criar venv e instalar
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copiar os arquivos de modelo para backend/detection/models/
# (frozen_inference_graph.pb, ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt, coco.names)

# Variáveis de conexão com o servidor
export BOTTLE_COUNT_API_URL="http://<IP_DO_SERVIDOR>:8000"
export BOTTLE_COUNT_STATION_ID="1"
export BOTTLE_COUNT_PUBLISH_INTERVAL="5"
export BOTTLE_COUNT_API_ENABLED="1"

# Rodar
.venv/bin/python backend/detection/object-ident.py --publish
```

> A Raspberry Pi **não precisa** de MongoDB nem FastAPI instalados. Ela envia apenas agregados via HTTP POST para o servidor.

---

## 11. Testes

### 11.1 Executar testes Python

**Linux:**
```bash
cd /home/vyzxc/aquamonitor
source .venv/bin/activate
python -m unittest discover -v
```

**Windows:**
```powershell
cd C:\Users\seu_usuario\aquamonitor
.venv\Scripts\activate
python -m unittest discover -v
```

### 11.2 Testes específicos

```bash
python -m unittest backend.test_station_metrics -v
python -m unittest backend.test_bottle_events -v
python -m unittest backend.test_bottle_count -v
```

São **13 testes** distribuídos em 3 arquivos:
- `test_station_metrics.py` — 4 testes (associação de métricas com estações)
- `test_bottle_events.py` — 5 testes (idempotência de eventos)
- `test_bottle_count.py` — 4 testes (ingestão de contagens)

---

## 12. Solução de Problemas Comuns

### 12.1 MongoDB não conecta

**Sintoma:** `ServerSelectionTimeoutError` ou hang no startup.

**Solução Linux:**
```bash
sudo chown -R mongodb:mongodb /var/lib/mongodb /var/log/mongodb
sudo rm -f /tmp/mongodb-27017.sock /data/db/mongod.lock
sudo systemctl restart mongod
```

**Solução Windows:** Verifique se o serviço MongoDB está rodando (`services.msc` → MongoDB).

> ⚠️ O `MongoClient` do `app.py` não tem `serverSelectionTimeoutMS` configurado, o que pode causar **hang** em vez de erro rápido se o MongoDB estiver indisponível. Considere adicionar:
> ```python
> client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
> ```

### 12.2 `supervision` não importa (ModuleNotFoundError)

**Solução:** Reinstale com flags de binary:
```bash
pip install supervision==0.27.0 lap==0.5.12 cython-bbox==0.1.5 --force-reinstall
```

Se compilação falhar, instale o Visual C++ Build Tools (Windows) ou `build-essential` (Linux):
```bash
# Linux
sudo apt install -y build-essential
pip install lap==0.5.12 cython-bbox==0.1.5 --no-binary :all:
```

### 12.3 OpenCV não encontra o modelo SSD MobileNet

**Sintoma:** `cv2.dnn_DetectionModel` falha ao carregar `frozen_inference_graph.pb`.

**Verificação:**
```python
import os
print(os.path.exists("backend/detection/models/frozen_inference_graph.pb"))
print(os.path.exists("backend/detection/models/ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt"))
```

**Solução:** Baixe os arquivos do modelo e coloque em `backend/detection/models/`.

### 12.4 Dashboard não mostra dados

1. Verifique se o backend está rodando: `curl http://127.0.0.1:8000/api/stations`
2. Verifique se o MongoDB tem dados: `mongosh --eval 'use aquamonitor; db.stations.countDocuments({})'`
3. Verifique o console do navegador (F12 → Console) para erros CORS ou de rede
4. O CORS está configurado para `"*"` no backend, então não deve haver bloqueio

### 12.5 `lap` ou `cython-bbox` falha no Windows

**Solução:** Instale o Visual C++ Build Tools:
1. Baixe: https://visualstudio.microsoft.com/visual-cpp-build-tools/
2. Instale o workload **"Desktop development with C++"**
3. Reinicie o terminal
4. Reinstale: `pip install lap cython-bbox --force-reinstall`

---

## 13. Resumo de Dependências por Plataforma

### Linux
```bash
sudo apt install -y git python3.12 python3.12-venv python3-pip mongodb nodejs npm build-essential
pip install -r requirements.txt
```

### Windows
```powershell
# 1. Instale: Python 3.12 (com PATH), Git, MongoDB Community, Node.js LTS, Visual C++ Build Tools
# 2.
pip install -r requirements.txt
```

---

## 14. Notas Importantes

1. **`requirements.txt` contém 10 pacotes** (9 linhas): fastapi, uvicorn, pydantic, pymongo, opencv-python, supervision==0.27.0, lap==0.5.12, cython-bbox==0.1.5, numpy==1.26.4, requests.

2. **O pipeline usa SSD MobileNet V3 via OpenCV DNN**, não YOLOv8. O arquivo `best.pt` existe no projeto mas **não é utilizado** pelo código de detecção.

3. **GeoJSON usa `[longitude, latitude]`** (ordem inversa do padrão GPS).

4. **O venv `ultralytics-env`** é apenas para treinamento YOLOv8 e **não é necessário** para o pipeline de detecção em produção.

5. **O arquivo `.gitignore` exclui `*.pb` e `*.pbtxt`** — esses arquivos de modelo agora estão no repositório, mas podem ainda faltar dependendo do histórico do clone. Verifique em `backend/detection/models/`.

6. **MongoDB sem timeout configurado** — pode causar hang no startup se o banco estiver indisponível.

7. **O dashboard usa CDN** (leaflet@1.9.4, leaflet-heat) — precisa de internet para carregar os mapas.

8. **Testes usam `unittest`** (não pytest) com Mock para collections MongoDB.

---

## 15. Referências

- **Repositório:** https://github.com/Vy0618/aquamonitor
- **Documentação interna:** `README.md`, `rpi-server-communication.md`
- **Documentação de detecção:** `backend/detection/` (docstrings em cada módulo)
- **Documentação de validação:** `dashboard/VALIDATION.md`

---

*Guia gerado para reprodução do ambiente Aqua Monitor — Setembro 2026.*
