import requests
from bs4 import BeautifulSoup
import pdfplumber
import html
import os
import sys
import json
import re
import unicodedata
import time
from io import BytesIO
from datetime import datetime
import boto3
import gc
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from email_handler import *
import psycopg2
import urllib3
from config.settings import *

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =====================================
# CONFIGURAÇÃO - V7
# =====================================

# resource não existe no Windows — importa só se Linux/Mac
if os.name != "nt":
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (600 * 1024 * 1024, -1))
    except Exception:
        pass

gc.enable()

# ------------------------------------------------------------------
# Logging — FileHandler em UTF-8 + StreamHandler forçado em UTF-8
# para não quebrar no terminal Windows (cp1252 não suporta emojis).
# ------------------------------------------------------------------
_file_handler   = logging.FileHandler("dje_monitor.log", encoding="utf-8")
_stream_handler = logging.StreamHandler(
    stream=open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1, closefd=False)
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[_file_handler, _stream_handler],
)
log = logging.getLogger(__name__)

# =====================================
# CONSTANTES
# =====================================

DB_CONFIG = {
    "host":     DB_HOST,
    "database": DB_NAME,
    "user":     DB_USER,
    "password": DB_PASSWORD,
    "port":     int(DB_PORT),
}

HEADERS = {"User-Agent": "Mozilla/5.0"}

_cache_lock = Lock()
_db_lock    = Lock()

# =====================================
# BANCO DE DADOS
# =====================================

def conectar_db():
    return psycopg2.connect(**DB_CONFIG)


def criar_tabela():
    conn = conectar_db()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS publicacoes_dje (
            id            SERIAL PRIMARY KEY,
            nome_pdf      TEXT      NOT NULL,
            chave_s3      TEXT      NOT NULL,
            advogado      TEXT      NOT NULL,
            comentario    TEXT,
            data_encontro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_advogado ON publicacoes_dje(advogado);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_data     ON publicacoes_dje(data_encontro DESC);")
    conn.commit()
    cur.close()
    conn.close()
    log.info("✅ Tabela verificada/criada")


def salvar_no_banco(nome_pdf: str, chave_s3: str):
    try:
        with _db_lock:
            conn = conectar_db()
            cur  = conn.cursor()
            cur.execute(
                "INSERT INTO publicacoes_dje (nome_pdf, chave_s3, advogado) VALUES (%s, %s, %s)",
                (nome_pdf, chave_s3, NOME_ADVOGADO),
            )
            conn.commit()
            cur.close()
            conn.close()
        log.info("🗄️  Registro salvo no RDS: %s", nome_pdf)
    except Exception as e:
        log.error("Erro banco: %s", e)

# =====================================
# AWS S3
# =====================================

s3 = boto3.client("s3")


def enviar_para_s3(pdf_bytes: bytes, nome_pdf: str) -> str | None:
    try:
        agora     = datetime.now()
        timestamp = agora.strftime("%Y%m%d_%H%M%S")
        chave     = f"dje_monitor/{agora:%Y}/{agora:%m}/{agora:%d}/{timestamp}_{nome_pdf}"
        s3.put_object(Bucket=BUCKET_NAME, Key=chave, Body=pdf_bytes, ContentType="application/pdf")
        log.info("☁️  Enviado para S3: %s", chave)
        return chave
    except Exception as e:
        log.error("Erro upload S3: %s", e)
        return None

# =====================================
# UTILIDADES
# =====================================

def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    return re.sub(r"\s+", " ", texto).upper()


def carregar_cache() -> set:
    if os.path.exists(ARQUIVO_CACHE):
        with open(ARQUIVO_CACHE, "r") as f:
            return set(json.load(f))
    return set()


def salvar_cache(cache: set):
    with open(ARQUIVO_CACHE, "w") as f:
        json.dump(list(cache)[-500:], f)

# =====================================
# COLETA DE LINKS
# =====================================

def obter_links_pdf() -> list[str]:
    sess = requests.Session()
    sess.headers.update(HEADERS)
    resp = sess.get(URL_DJE, timeout=30, verify=False)
    soup = BeautifulSoup(resp.text, "html.parser")
    links = set()
    for a in soup.find_all("a"):
        href = a.get("href", "")
        if "DownloadServlet" in href and ".P7S" not in href:
            href = html.unescape(href)
            if not href.startswith("http"):
                href = "https://www2.tjpe.jus.br" + href
            links.add(href)
    log.info("✅ %d PDFs encontrados no DJE", len(links))
    return list(links)

# =====================================
# ANÁLISE DE PDF
# =====================================

def pdf_contem_advogado(pdf_bytes: bytes, nome_normalizado: str) -> bool:
    try:
        if not pdf_bytes.startswith(b"%PDF"):
            return False
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            total = len(pdf.pages)
            for i in range(20, total):
                texto = pdf.pages[i].extract_text() or ""
                if nome_normalizado in normalizar(texto):
                    return True
                pdf.pages[i].flush_cache()
        return False
    except Exception as e:
        log.warning("Erro lendo PDF: %s", e)
        return False
    finally:
        gc.collect()

# =====================================
# WORKER
# =====================================

def processar_pdf(link: str, nome_normalizado: str) -> str:
    nome_pdf  = link.split("dj=")[-1].split("&")[0]
    pdf_bytes = None                          # garante que a variável existe no finally

    log.info("Processando: %s", nome_pdf)

    try:
        sess = requests.Session()
        sess.headers.update(HEADERS)

        with sess.get(link, timeout=60, stream=True, verify=False) as resp:
            resp.raise_for_status()
            buf = BytesIO()
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    buf.write(chunk)
            pdf_bytes = buf.getvalue()

        log.info("%s — %.2f MB", nome_pdf, len(pdf_bytes) / 1024 / 1024)

        if pdf_contem_advogado(pdf_bytes, nome_normalizado):
            log.info("✅ ADVOGADO ENCONTRADO em %s", nome_pdf)
            chave_s3 = enviar_para_s3(pdf_bytes, nome_pdf)
            if chave_s3:
                salvar_no_banco(nome_pdf, chave_s3)
                enviar_email_alerta(nome_pdf, chave_s3, NOME_ADVOGADO)
            else:
                log.warning("Upload S3 falhou — banco/e-mail ignorados")
        else:
            log.info("Nao contém advogado: %s", nome_pdf)

    except requests.RequestException as e:
        log.error("Erro HTTP em %s: %s", nome_pdf, e)
    except Exception as e:
        log.error("Erro inesperado em %s: %s", nome_pdf, e)
    finally:
        if pdf_bytes is not None:             # só deleta se foi criado
            del pdf_bytes
        gc.collect()

    return link

# =====================================
# LOOP PRINCIPAL
# =====================================

def monitorar_dje():
    nome_normalizado = normalizar(NOME_ADVOGADO)
    cache = carregar_cache()
    criar_tabela()

    log.info("🚀 Monitor DJE iniciado (workers=%d, max_pdfs=%d)", MAX_WORKERS, MAX_PDFS_POR_CICLO)

    while True:
        try:
            log.info("🕒 Verificando DJE — %s", datetime.now().strftime("%H:%M:%S"))

            links = obter_links_pdf()
            novos = [l for l in links if l not in cache][:MAX_PDFS_POR_CICLO]

            if not novos:
                log.info("📭 Nenhum diário novo encontrado")
            else:
                log.info("📬 %d diário(s) novo(s) para processar", len(novos))

                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    futuros = {
                        executor.submit(processar_pdf, link, nome_normalizado): link
                        for link in novos
                    }
                    for futuro in as_completed(futuros):
                        try:
                            link_concluido = futuro.result()
                            with _cache_lock:
                                cache.add(link_concluido)
                        except Exception as e:
                            log.error("Erro ao recuperar resultado da thread: %s", e)

                with _cache_lock:
                    salvar_cache(cache)

            log.info("⏳ Aguardando %ds até o próximo ciclo...", INTERVALO_VERIFICACAO)
            time.sleep(INTERVALO_VERIFICACAO)

        except KeyboardInterrupt:
            log.info("Monitor interrompido pelo usuário")
            break
        except Exception as e:
            log.error("Erro geral: %s — tentando novamente em 60s", e)
            time.sleep(60)


if __name__ == "__main__":
    monitorar_dje()