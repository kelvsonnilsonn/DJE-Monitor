import os
from dotenv import load_dotenv

load_dotenv()

# =====================================
# CONFIGURAÇÃO (ENV)
# =====================================

BUCKET_NAME     = os.getenv("BUCKET_NAME")
SES_REGION      = os.getenv("SES_REGION")
EMAIL_REMETENTE = os.getenv("BOT_EMAIL")
EMAIL_DESTINO   = os.getenv("CLIENTE")
NOME_ADVOGADO   = os.getenv("NOME_ADVOGADO")
DB_HOST         = os.getenv("DB_HOST")
DB_NAME         = os.getenv("DB_NAME")
DB_USER         = os.getenv("DB_USER")
DB_PASSWORD     = os.getenv("DB_PASSWORD")
DB_PORT         = os.getenv("DB_PORT")

# =====================================
# SISTEMA
# =====================================

URL_DJE = "https://www2.tjpe.jus.br/dje/djeletronico?visaoId=tjdf.djeletronico.comum.internet.apresentacao.VisaoDiarioEletronicoInternetPorData"
ARQUIVO_CACHE = "processados.json"
INTERVALO_VERIFICACAO = 3600

# =====================================
# CONTROLE
# =====================================

MAX_TENTATIVAS = 3
PAUSA_RETRY = 5
MAX_PDFS_POR_CICLO = 10
MAX_WORKERS = 4