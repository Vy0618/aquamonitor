# Inconsistências do RaspberryPi/ para Linux (Mint / Debian Trixie)

O diretório `RaspberryPi/` foi concebido com pressupostos Windows e, ao portá-lo para Linux, encontramos as seguintes inconsistências que impedem ou dificultam o funcionamento pleno.

---

## 1. Diretório `data/` ausente — bloqueio de execução

**O que acontece:** `monitor_residuos.py` define `COUNTS_FILE = BASE_DIR / "data" / "contagem_residuos.json"`. A função `save_counts()` escreve primeiro em `data/contagem_residuos.tmp` e depois faz `temporary.replace(path)`. Se o diretório `data/` não existir, `write_text()` lança `FileNotFoundError` imediatamente.

**Por que não foi criado:** O `.gitignore` contém `data/`, portanto o diretório nunca foi versionado. E nenhuma linha de código faz `mkdir(parents=True, exist_ok=True)` para criá-lo automaticamente.

**Correção:** Adicionar em `save_counts()` ou na inicialização de `main()`:
```python
COUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
```

---

## 2. `gps.enabled: true` no `raspberrypi_config.json` sem hardware GPS

**O que acontece:** O config vem com `"enabled": true` e `"serial_port": "/dev/serial0"`. Tanto `monitor_ssd_mobilenet.py` quanto `update_station_location.py` abrem a UART ao iniciar. Em qualquer máquina sem NEO-6M conectado, isso gera `serial.SerialException` e o processo crasha.

**Detalhe:** `/dev/serial0` é um symlink específico do Raspberry Pi. Em PCs Linux com GPS via USB, o dispositivo costuma ser `/dev/ttyUSB0` ou `/dev/ttyACM0`.

**Correção:** Em máquinas sem GPS físico, alterar `"enabled": false` no JSON. Em Raspberry Pi com GPS, verificar o caminho correto da UART.

---

## 3. Nome do modelo com espaço: `models/best (1).pt`

**O que acontece:** O arquivo `best (1).pt` contém espaço e parênteses. O código Python via `Path(...)` lida corretamente, mas o Ultralytics internamente pode não tratar o caminho com espaços de forma confiável dependendo da versão. Além disso, qualquer comando shell nos documentos exige aspas cuidadosas.

**Correção:** Renomear para `best.pt` ou `best_model.pt` e atualizar o caminho em `raspberrypi_config.json`.

---

## 4. Documentação com `runtime/__pycache__/` e Python 3.14 fictícios

**O que acontece:** `DOCUMENTACAO_ARQUIVOS.md` (linha 145-147) afirma que existe um diretório `runtime/__pycache__/` contendo bytecode Python 3.14. Na realidade:
- O diretório `runtime/` **não existe**
- Os `.pyc` reais estão nos `__pycache__/` de cada pacote e são **Python 3.12**
- O sistema roda Python 3.12.3

**Impacto:** Qualquer pessoa que tente reproduzir o ambiente baseada nessa documentação terá informações incorretas sobre a versão do Python e a estrutura de diretórios.

**Correção:** Remover a seção `runtime/__pycache__/` da documentação ou corrigir para refletir os `__pycache__/` reais e Python 3.12.

---

## 5. Toda a documentação usa PowerShell

**O que acontece:** `README.md`, `TESTE_LOCAL.md` e trechos de `DOCUMENTACAO_ARQUIVOS.md` contêm **exclusivamente** comandos PowerShell:
```powershell
Set-Location aquamonitor
.\.venv\Scripts\python.exe
Test-Path 'RaspberryPi\models\best (1).pt'
Invoke-RestMethod -Method Post ... -InFile RaspberryPi\station\station.json
ConvertTo-Json
Set-Location C:\caminho\para\aquamonitor
```

**Impacto:** Em Mint/Debian, o usuário precisa traduzir manualmente cada comando:
- `Set-Location` → `cd`
- `.\.venv\Scripts\python.exe` → `.venv/bin/python`
- `Test-Path` → `test -f`
- `Invoke-RestMethod` → `curl` ou `httpie`
- `ConvertTo-Json` → `jq` ou nenhum equivalente direto

**Correção:** Adicionar seção equivalente em bash para cada exemplo PowerShell.

---

## 6. `_id` como MongoDB Extended JSON no `station.json` local

**O que acontece:** `station/station.json` armazena `"_id": {"$oid": "68c5d6c0a4e71b2f8d000001"}`. Isso é MongoDB Extended JSON (um objeto, não uma string). `StationDocument._validate()` verifica a estrutura mas não o tipo de `_id`. Qualquer código que espere `_id` como string (ex: serialização JSON simples, comparações) vai falhar silenciosamente ou com erro.

**Correção:** Substituir `_id` por uma string simples no `station.json` local, ou adaptar `_validate()` para aceitar o formato estendido e `_base_document()` para normalizar.

---

## 7. `monitor_ssd_mobilenet.py` importa `monitor_residuos.py` (acoplamento forçado)

**O que acontece:** O monitor SSD faz:
```python
from RaspberryPi.monitoring.monitor_residuos import (
    BASE_DIR, CONFIG_FILE, COUNTS_FILE, ...
)
```
Isso significa que `monitor_residuos.py` — e portanto `import cv2`, `import numpy`, e o carregamento do `YoloDetector` — **precisam ser importáveis** mesmo ao executar apenas o SSD. Se `ultralytics` não estiver instalado, o SSD também falha ao importar.

**Correção:** Extrair as funções compartilhadas (`load_config`, `load_counts`, `save_counts`, `draw_overlay`, constantes) para um módulo separado (ex: `monitoring/common.py`) e importar de lá em ambos os monitores.

---

## 8. Sem carregamento automático de `.env`

**O que acontece:** `backend_client.py` lê `os.getenv("AQUADETECTOR_API_URL")`, mas o projeto não implementa carregamento de arquivo `.env`. O `.gitignore` lista `.env` mas não há nenhuma implementação de `dotenv`. Se o usuário criar um `.env` com a URL do backend, ele não será lido automaticamente — é necessário `export AQUADETECTOR_API_URL=...` manualmente.

**Correção:** Adicionar `python-dotenv` como dependência e chamar `load_dotenv()` no ponto de entrada, ou documentar explicitamente que a variável deve ser exportada manualmente.

---

## 9. Diferenças de hardware: câmera USB — Windows vs Linux

**O que acontece:** `camera/webcam_config.py` usa `cv2.VideoCapture(self.device_index)` com `backend: Optional[int] = None`. O OpenCV seleciona automaticamente o backend do sistema, que é **diferente entre Windows e Linux**:

| Aspecto | Windows | Linux (Mint/Debian) |
|---------|---------|---------------------|
| Backend padrão | MSMF / DirectShow | V4L2 |
| Índice do dispositivo | Ordem de enumeração DirectShow | `/dev/video0`, `/dev/video1` (udev) |
| Permissões | Driver-level, geralmente sem restrições | Usuário precisa estar no grupo `video` |
| Negotiação de FPS/resolução | Depende do driver DirectShow | Depende do driver V4L2 e do firmware da câmera |

**Problemas específicos:**

1. **Grupo `video` não verificado** — Em Linux, se o usuário não estiver no grupo `video`, `cv2.VideoCapture(0)` abre mas `camera.isOpened()` retorna `False` ou `camera.read()` falha silenciosamente. Não há verificação do grupo no código. No Windows, isso não é um problema.

2. **`device_index` como inteiro não é consistente entre plataformas** — Na mesma máquina, conectar uma câmera USB em outra porta pode mudar o índice de `/dev/video0` para `/dev/video1`. No Windows, a enumeração DirectShow também pode variar. O código não oferece nenhum mecanismo de identificação por caminho (ex: `/dev/video/by-id/`) ou nome serial do dispositivo.

3. **`camera.set()` é uma solicitação, não uma garantia** — O comentário do código diz "A configuração é uma solicitação: o dispositivo pode aceitar valores diferentes". Em Linux com V4L2, algumas câmeras ignoram `CAP_PROP_FRAME_WIDTH/HEIGHT/FPS` e retornam a resolução nativa do sensor ou a resolução mais próxima disponível. O código não verifica se as propriedades foram realmente aplicadas após o `set()`.

4. **GPU/CUDA para YOLO** — `YoloDetector.__init__` tem `device: str | None = None`, que usa CPU. Em Windows com NVIDIA GPU, o usuário poderia passar `"cuda"`. Em Linux, isso requer drivers NVIDIA proprietários instalados e `cuda` toolkit acessível, o que não é garantido em Trixie (que tende a usar drivers open-source `nouveau`).

**Correção sugerida:**
- Adicionar verificação de grupo `video` no Linux e mensagem informativa se o usuário não pertencer a ele:
  ```python
  import os, stat
  def _check_video_group():
      if not hasattr(os, 'getgroups'): return
      gid = os.stat('/dev/video0').st_gid
      if gid not in os.getgroups():
          print(f"AVISO: usuário não está no grupo com GID {gid}. Adicione com: sudo usermod -aG video $USER")
  ```
- Verificar o retorno de `camera.set()` e, se não aplicado, listar as resoluções suportadas via `cv2.CAP_PROP_FRAME_WIDTH` após abertura.
- Permitir identificação por caminho do dispositivo (ex: `/dev/video/by-id/usb-...`) além de `device_index`.

---

## 10. Hardware: UART GPS — `/dev/serial0` é específico do Raspberry Pi

*(Expande a seção 2 com detalhes de hardware)*

**O que acontece:** `/dev/serial0` é um symlink criado pelo Raspberry Pi para a UART interna. Em qualquer outro hardware Linux (PC, notebook, Raspberry Pi CM4 com USB-serial), o dispositivo é `/dev/ttyUSB0`, `/dev/ttyACM0`, `/dev/ttyS0` ou outro. O `gps_neo6m.py` e o `raspberrypi_config.json` têm `/dev/serial0` hardcoded.

**Detalhe adicional:** Em PCs Linux modernos com kernel 6.x (Trixie), a serial USB é tipicamente `/dev/ttyACM0` para adaptadores FTDI/CP210x ou `/dev/ttyUSB0` para placas seriais genéricas. O `/dev/serial0` simplesmente não existe fora de um Raspberry Pi.

**Correção:** O `raspberrypi_config.json` deveria usar um caminho configurável com detecção automática ou pelo menos um valor padrão genérico como `/dev/ttyUSB0` com um comentário indicando a plataforma-alvo.

---

## Tabela resumo

| # | Problema | Severidade | Tipo |
|---|----------|-----------|------|
| 1 | `data/` não existe, nenhum `mkdir` | **Crash** | Código |
| 2 | `gps.enabled: true` sem hardware GPS | **Crash** | Config |
| 3 | `best (1).pt` com espaço no nome | Risco | Nome de arquivo |
| 4 | `runtime/__pycache__` + Python 3.14 | Documentação incorreta | Docs |
| 5 | Toda documentação em PowerShell | Sem equivalente Linux | Docs |
| 6 | `_id` como `{"$oid": ...}` | Comportamento inesperado | Código |
| 7 | SSD importa YOLO desnecessariamente | Falha por dependência | Código |
|| 8 | Sem `.env` loader | Risco de configuração | Código |
|| 9 | Câmera: backend OpenCV diferente, grupo `video`, `device_index` não consistente | **Crash/Falha silenciosa** | Hardware |
|| 10 | GPS: `/dev/serial0` específico do RPi | **Crash sem GPS** | Hardware |
