# Banco de testes AquaMonitor

O arquivo `aquamonitor_test.sql` é uma exportação SQL do banco
`aquamonitor_local_test`, feita em 16/11/2026 com PostgreSQL 16.
Ele pode ser versionado no GitHub e contém o esquema e os dados das tabelas
`public.stations` e `public.detection_events`, incluindo índices e restrições.
Não contém senhas, usuários/roles PostgreSQL, permissões, proprietário nem
configuração de conexão. O usuário e o banco de destino são criados à parte.

## Conteúdo

- 10 estações ativas: cinco na região de Campinas e cinco na Baía de Santos.
- 428 eventos sintéticos de `bottle`, gerados para demonstração, sem valor de medição real.
- Coordenadas aproximadas para os cinco pontos de demonstração na baía.
- Os IDs, horários, coordenadas e campos administrativos exportados são preservados.

| Estação da Baía de Santos | Eventos |
|---|---:|
| 1257987626 | 148 |
| 1114656919 | 189 |
| 1939472876 | 18 |
| 1675430541 | 39 |
| 1163574152 | 34 |

As outras cinco estações (IDs 1 a 5) têm zero eventos.

## Importar em Debian/Ubuntu

Execute a partir da raiz do clone. Use PostgreSQL 16, versão usada na validação.
O banco de destino deve ser novo e vazio; o arquivo cria as tabelas e não mescla
registros com uma instalação existente. Mantenha a API e os monitores sem acesso
a esse banco até concluir a importação.

1. Instale e inicie PostgreSQL:

   ```bash
   sudo apt update
   sudo apt install postgresql postgresql-client
   sudo systemctl start postgresql
   psql --version
   ```

2. Crie um usuário, somente se ele ainda não existir. Defina sua própria senha
   quando solicitado (ela não está no arquivo exportado):

   ```bash
   sudo -u postgres createuser --pwprompt aquamonitor_dev
   ```

3. Crie um banco novo para a importação:

   ```bash
   sudo -u postgres createdb --owner=aquamonitor_dev aquamonitor_test
   ```

   Se esse nome já existir, escolha outro nome e use-o em todos os comandos
   seguintes. Não é necessário apagar nem sobrescrever o banco anterior.

4. Importe o SQL; informe a senha do usuário quando solicitado:

   ```bash
   psql -X -h 127.0.0.1 -U aquamonitor_dev -d aquamonitor_test --set=ON_ERROR_STOP=1 --single-transaction --file=data/demo/aquamonitor_test.sql
   ```

   `ON_ERROR_STOP` interrompe ao primeiro erro e `--single-transaction` desfaz
   essa importação se houver falha. Não execute a importação novamente no mesmo
   banco já preenchido: haverá conflito de tabelas existentes.

5. Confira os registros:

   ```bash
   psql -X -h 127.0.0.1 -U aquamonitor_dev -d aquamonitor_test -c "SELECT (SELECT COUNT(*) FROM stations) AS stations, (SELECT COUNT(*) FROM detection_events) AS detections;"
   psql -X -h 127.0.0.1 -U aquamonitor_dev -d aquamonitor_test -c "SELECT station_id, COUNT(*) AS total FROM detection_events GROUP BY station_id ORDER BY station_id;"
   ```

   O primeiro comando deve retornar **10 estações e 428 detecções**. O segundo
   deve retornar os cinco totais da tabela acima.

## Usar o banco importado na API e no dashboard

No terminal da API, com a venv ativa, substitua `SENHA` pela sua senha.
Caracteres reservados na senha devem ser codificados na URI, conforme o README
principal. A variável precisa estar no mesmo terminal que inicia o Uvicorn:

```bash
export AQUAMONITOR_DATABASE_URL='postgresql://aquamonitor_dev:SENHA@127.0.0.1:5432/aquamonitor_test'
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Se a API anterior estiver na porta 8000, encerre-a antes de iniciar a nova.
Para a primeira instalação do service, configure essa mesma URL em
`deploy/systemd/.env.api`, criado a partir de `deploy/systemd/.env.example`.
Se o service já estiver instalado, edite a configuração efetivamente carregada:

```bash
sudoedit /etc/aquamonitor/api.env
```

Defina a senha real e o mesmo banco usado na importação:

```dotenv
AQUAMONITOR_DATABASE_URL=postgresql://aquamonitor_dev:SENHA@127.0.0.1:5432/aquamonitor_test
```

Depois execute `sudo systemctl restart aquamonitor-api.service`.
O `export` no terminal não altera um serviço existente e reinstalar as unidades
preserva o arquivo `/etc/aquamonitor/api.env`.

Em outro terminal:

```bash
curl --fail-with-body http://127.0.0.1:8000/api/stations
python serve_dashboard.py
```

Se o dashboard já estiver sendo servido, reutilize o servidor existente.
Abra http://127.0.0.1:3000/ e busque `1257987626` para centralizar a baía.
O modo Calor mostra os eventos sintéticos; Estações ou Ambos também mostram
estações zeradas. Não é necessário cadastrar as estações novamente nem executar
`populate_santos.py` após importar: o SQL já contém os dados.

## Importar no Windows (PowerShell)

Instale PostgreSQL 16 com as ferramentas de linha de comando, adicione sua pasta
`bin` ao `PATH` e confirme que o serviço está iniciado. Na raiz do clone:

```powershell
psql --version
createuser -h 127.0.0.1 -U postgres --pwprompt aquamonitor_dev
createdb -h 127.0.0.1 -U postgres --owner=aquamonitor_dev aquamonitor_test
psql -X -h 127.0.0.1 -U aquamonitor_dev -d aquamonitor_test --set=ON_ERROR_STOP=1 --single-transaction --file=data/demo/aquamonitor_test.sql
psql -X -h 127.0.0.1 -U aquamonitor_dev -d aquamonitor_test -c "SELECT (SELECT COUNT(*) FROM stations) AS stations, (SELECT COUNT(*) FROM detection_events) AS detections;"
```

Pule `createuser` se o usuário já existir. Use um nome novo se o banco já existir.
Com a venv ativa, inicie a API no mesmo PowerShell em que definir a variável:

```powershell
$env:AQUAMONITOR_DATABASE_URL='postgresql://aquamonitor_dev:SENHA@127.0.0.1:5432/aquamonitor_test'
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

## Adicionar ao GitHub

O SQL é texto e não é bloqueado pelo `.gitignore`. Para preparar os arquivos
para seu próximo commit, execute da raiz do projeto:

```bash
git add data/demo/README.md data/demo/aquamonitor_test.sql README.md
git diff --cached --stat
```

Revise os dados e faça o commit/push pelo seu fluxo habitual. Não adicione
credenciais, arquivos `.env` nem a pasta de dados interna do PostgreSQL.

## Validação da exportação

O SQL foi importado com `ON_ERROR_STOP` e transação única em um cluster PostgreSQL
16 temporário, sem conexão TCP. Os registros das duas tabelas foram comparados
integralmente com a origem. O cluster temporário foi encerrado e removido depois
da conferência; o banco original não foi alterado.
