# 🔍 DJE Monitor — Bot Sentinela do Diário de Justiça Eletrônico (PE)

Monitor automático do [Diário de Justiça Eletrônico do TJPE](https://www2.tjpe.jus.br/dje/) que verifica diariamente a publicação de processos vinculados a um advogado específico e envia um alerta por e-mail com link direto para o PDF assim que uma ocorrência é encontrada.

---

## 🧠 Como funciona

```
┌─────────────────────────────────────────────────────┐
│                   A cada 1 hora                     │
│                                                     │
│  DJE (TJPE) ──► Coleta links dos PDFs do dia        │
│                        │                            │
│              Filtra apenas os novos                 │
│                        │                            │
│         ┌──────────────┴──────────────┐             │
│      Thread 1      Thread 2      Thread N           │
│      Download      Download      Download           │
│      + Leitura     + Leitura     + Leitura          │
│         └──────────────┬──────────────┘             │
│                        │                            │
│              Advogado encontrado?                   │
│               ┌────────┴────────┐                   │
│              SIM               NÃO                  │
│               │                 │                   │
│         S3 + RDS             Próximo                │
│         + E-mail             PDF                    │
└─────────────────────────────────────────────────────┘
```

O script roda em segundo plano via **Agendador de Tarefas do Windows** e sobe automaticamente a cada login, sem precisar de terminal aberto.

---

## ✨ Funcionalidades

- Coleta automática dos links de PDFs publicados no DJE-PE
- Download e leitura de múltiplos PDFs em paralelo (multi-thread)
- Busca pelo nome do advogado com normalização de acentos e espaços
- Armazenamento do PDF encontrado no **AWS S3**
- Registro da ocorrência em banco **PostgreSQL (AWS RDS)**
- Envio de **e-mail de alerta via AWS SES** com link de download pré-assinado (válido 7 dias)
- Cache local para não reprocessar PDFs já verificados
- Logs em arquivo UTF-8 (`dje_monitor.log`) compatíveis com Windows
- Execução em segundo plano via `.bat` + Agendador de Tarefas

---

## 🗂️ Estrutura do projeto

```
.
├── dje_monitor.py        # Script principal
├── email_handler.py      # Envio de e-mail via AWS SES
├── instalar_monitor.bat  # Instalador: registra no Task Scheduler e inicia
├── processados.json      # Cache de PDFs já verificados (gerado automaticamente)
├── dje_monitor.log       # Log de execução (gerado automaticamente)
├── .env                  # Variáveis de ambiente (não versionar)
└── .venv/                # Ambiente virtual Python
```

---

## ⚙️ Pré-requisitos

- Python 3.11+
- Conta AWS com acesso a **S3**, **SES** e **RDS (PostgreSQL)**
- E-mail de remetente verificado no SES
- Windows 10/11 (para execução em segundo plano via `.bat`)

---

## 🚀 Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/dje-monitor.git
cd dje-monitor
```

### 2. Crie o ambiente virtual e instale as dependências

```bash
python -m venv .venv
.venv\Scripts\activate
pip install requests beautifulsoup4 pdfplumber boto3 psycopg2-binary python-dotenv urllib3
```

### 3. Configure o `.env`

Crie um arquivo `.env` na raiz do projeto com o seguinte conteúdo:

```env
# Banco de dados (AWS RDS PostgreSQL)
DB_HOST=seu-host.rds.amazonaws.com
DB_NAME=nome_do_banco
DB_USER=usuario
DB_PASSWORD=senha
DB_PORT=5432

# AWS SES
SES_REGION=us-east-1
EMAIL_REMETENTE=seu-email@dominio.com
EMAIL_DESTINO=destino@dominio.com
```

> ⚠️ Nunca versione o arquivo `.env`. Adicione-o ao `.gitignore`.

### 4. Configure as credenciais AWS

```bash
aws configure
```

Ou defina as variáveis de ambiente `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` e `AWS_DEFAULT_REGION`.

### 5. Execute o instalador

Clique com o botão direito em `instalar_monitor.bat` → **Executar como administrador**.

O instalador vai:
- Registrar o monitor no Agendador de Tarefas (inicia automaticamente a cada login)
- Iniciar o monitor imediatamente, sem precisar reiniciar

---

## 🖥️ Execução manual (opcional)

```bash
.venv\Scripts\python.exe dje_monitor.py
```

---

## 📋 Configurações principais

Todas as configurações ficam no topo do `dje_monitor.py`:

| Variável | Padrão | Descrição |
|---|---|---|
| `NOME_ADVOGADO` | `"KERISON NILSON"` | Nome buscado nos PDFs |
| `INTERVALO_VERIFICACAO` | `3600` | Intervalo entre ciclos (segundos) |
| `MAX_PDFS_POR_CICLO` | `10` | Máximo de PDFs processados por ciclo |
| `MAX_WORKERS` | `4` | Threads simultâneas de download/análise |
| `PAGINAS_INICIO` | `20` | Páginas iniciais ignoradas (capa/sumário) |

---

## 📊 Logs

O log é gravado em `dje_monitor.log` com encoding UTF-8. Para acompanhar ao vivo no PowerShell:

```powershell
Get-Content ".\dje_monitor.log" -Wait
```

Exemplo de saída:

```
2026-04-22 10:00:01 [INFO] 🕒 Verificando DJE — 10:00:01
2026-04-22 10:00:02 [INFO] ✅ 5 PDFs encontrados no DJE
2026-04-22 10:00:02 [INFO] 📬 3 diário(s) novo(s) para processar
2026-04-22 10:00:02 [INFO] Processando: DJ93_2026-ASSINADO.PDF
2026-04-22 10:00:08 [INFO] DJ93_2026-ASSINADO.PDF — 18.43 MB baixado
2026-04-22 10:00:21 [INFO] ✅ ADVOGADO ENCONTRADO em DJ93_2026-ASSINADO.PDF
2026-04-22 10:00:22 [INFO] ☁️  Enviado para S3: dje_monitor/2026/04/22/...
2026-04-22 10:00:22 [INFO] 🗄️  Registro salvo no RDS
2026-04-22 10:00:23 [INFO] 📧 E-mail enviado com sucesso!
```

---

## 🗄️ Estrutura do banco de dados

```sql
CREATE TABLE publicacoes_dje (
    id            SERIAL PRIMARY KEY,
    nome_pdf      TEXT      NOT NULL,
    chave_s3      TEXT      NOT NULL,
    advogado      TEXT      NOT NULL,
    comentario    TEXT,
    data_encontro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

A tabela é criada automaticamente na primeira execução.

---

## 🛑 Gerenciamento do serviço

| Ação | Comando (PowerShell) |
|---|---|
| Parar o monitor | `schtasks /end /tn "DJE Monitor"` |
| Iniciar manualmente | `schtasks /run /tn "DJE Monitor"` |
| Ver status | `Get-ScheduledTask -TaskName "DJE Monitor"` |
| Remover do Task Scheduler | `schtasks /delete /tn "DJE Monitor" /f` |

---

## 📦 Dependências

| Pacote | Uso |
|---|---|
| `requests` | Download dos PDFs e scraping do DJE |
| `beautifulsoup4` | Extração dos links da página do DJE |
| `pdfplumber` | Extração de texto dos PDFs |
| `boto3` | Integração com AWS S3 e SES |
| `psycopg2-binary` | Conexão com PostgreSQL (RDS) |
| `python-dotenv` | Carregamento das variáveis de ambiente |
| `urllib3` | Supressão de warnings SSL |

---

## 📄 Licença

MIT
