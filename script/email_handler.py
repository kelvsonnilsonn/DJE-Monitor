import os
import logging
import time
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
from config.settings import (
    BUCKET_NAME,
    SES_REGION,
    EMAIL_REMETENTE,
    EMAIL_DESTINO,
    MAX_TENTATIVAS,
    PAUSA_RETRY
)

# =====================================
# CONFIGURAÇÃO
# =====================================

log = logging.getLogger(__name__)

s3  = boto3.client("s3")
ses = boto3.client("ses", region_name=SES_REGION)

# =====================================
# HELPERS
# =====================================

def _gerar_presigned_url(chave_s3: str) -> str | None:
    """Gera URL pré-assinada válida por 7 dias. Retorna None em caso de erro."""
    try:
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": chave_s3},
            ExpiresIn=604_800,
        )
    except Exception as e:
        log.error("❌ Erro ao gerar URL pré-assinada: %s", e)
        return None


def _corpo_texto(nome_advogado: str, nome_pdf: str, chave_s3: str,
                 s3_url: str, agora: str) -> str:
    url_linha = s3_url if s3_url else "(URL indisponível — acesse o S3 diretamente)"
    return f"""\
🚨 ALERTA DO BOT SENTINELA 🚨

O advogado {nome_advogado} foi encontrado no Diário de Justiça Eletrônico!

📄 DIÁRIO:       {nome_pdf}
📅 DATA E HORA:  {agora}
☁️  ARQUIVO S3:  {chave_s3}

🔗 LINK PARA DOWNLOAD (válido por 7 dias):
{url_linha}

=================================
Bot Sentinela — Monitoramento Automático DJE
"""


def _corpo_html(nome_advogado: str, nome_pdf: str, chave_s3: str,
                s3_url: str | None, agora: str) -> str:
    botao = (
        f'<a href="{s3_url}" class="button" target="_blank">📥 BAIXAR PDF DO DIÁRIO</a>'
        if s3_url else
        "<p style='color:#c0392b;'>⚠️ Link de download indisponível. Acesse o S3 diretamente.</p>"
    )
    url_txt = f"<small>{s3_url}</small>" if s3_url else ""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Alerta DJE</title>
<style>
  body      {{ margin:0; padding:0; background:#f0f0f0; font-family:Arial,sans-serif; }}
  .wrap     {{ max-width:600px; margin:30px auto; background:#fff;
               border-radius:10px; overflow:hidden;
               box-shadow:0 2px 8px rgba(0,0,0,.15); }}
  .header   {{ background:#2e7d32; color:#fff; padding:24px; text-align:center; }}
  .header h1{{ margin:0; font-size:22px; }}
  .body     {{ padding:24px; }}
  .row      {{ display:flex; align-items:flex-start; gap:10px;
               margin:10px 0; padding:12px;
               background:#f9f9f9; border-left:4px solid #2e7d32;
               border-radius:0 4px 4px 0; word-break:break-all; }}
  .row .lbl {{ min-width:110px; font-weight:bold; color:#333; white-space:nowrap; }}
  .row .val {{ color:#555; }}
  .cta      {{ text-align:center; margin:28px 0 10px; }}
  .button   {{ background:#2e7d32; color:#fff; padding:12px 28px;
               text-decoration:none; border-radius:6px;
               font-size:15px; display:inline-block; }}
  .url-fb   {{ color:#888; font-size:12px; word-break:break-all;
               text-align:center; margin-top:8px; }}
  .footer   {{ background:#222; color:#aaa; font-size:12px;
               text-align:center; padding:14px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <h1>🚨 Alerta do Bot Sentinela</h1>
    <p style="margin:6px 0 0;font-size:14px;">Advogado encontrado no DJE</p>
  </div>

  <div class="body">
    <div class="row"><span class="lbl">👤 Advogado</span><span class="val">{nome_advogado}</span></div>
    <div class="row"><span class="lbl">📄 Diário</span><span class="val">{nome_pdf}</span></div>
    <div class="row"><span class="lbl">📅 Data/Hora</span><span class="val">{agora}</span></div>
    <div class="row"><span class="lbl">☁️ Chave S3</span><span class="val">{chave_s3}</span></div>

    <div class="cta">
      {botao}
    </div>
    <p class="url-fb">
      Se o botão não funcionar, copie o link abaixo:<br>{url_txt}
    </p>
  </div>

  <div class="footer">
    Bot Sentinela — Monitoramento Automático do DJE<br>
    Enviado em: {agora}
  </div>
</div>
</body>
</html>"""

# =====================================
# FUNÇÃO PRINCIPAL (com retry)
# =====================================

def enviar_email_alerta(nome_pdf: str, chave_s3: str, nome_advogado: str) -> bool:
    """
    Envia e-mail de alerta via AWS SES.
    Tenta até MAX_TENTATIVAS vezes antes de desistir.
    Retorna True se o envio foi bem-sucedido.
    """
    agora  = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    s3_url = _gerar_presigned_url(chave_s3)

    assunto    = f"✅ [{nome_advogado}] Encontrado no DJE — {nome_pdf}"
    texto      = _corpo_texto(nome_advogado, nome_pdf, chave_s3, s3_url or "", agora)
    html_body  = _corpo_html (nome_advogado, nome_pdf, chave_s3, s3_url, agora)

    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            resposta = ses.send_email(
                Source=EMAIL_REMETENTE,
                Destination={"ToAddresses": [EMAIL_DESTINO]},
                Message={
                    "Subject": {"Data": assunto,   "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": texto,     "Charset": "UTF-8"},
                        "Html": {"Data": html_body, "Charset": "UTF-8"},
                    },
                },
            )
            log.info(
                "📧 E-mail enviado (tentativa %d/%d) — ID: %s → %s",
                tentativa, MAX_TENTATIVAS,
                resposta["MessageId"], EMAIL_DESTINO,
            )
            return True

        except ClientError as e:
            code = e.response["Error"]["Code"]
            log.warning(
                "⚠️  Falha SES (tentativa %d/%d) — %s: %s",
                tentativa, MAX_TENTATIVAS, code, e,
            )
            # Erros permanentes — não adianta tentar de novo
            if code in {"MessageRejected", "MailFromDomainNotVerifiedException",
                        "ConfigurationSetDoesNotExistException"}:
                log.error("❌ Erro permanente SES — abortando envio")
                return False

        except Exception as e:
            log.warning("⚠️  Erro inesperado no envio (tentativa %d/%d): %s",
                        tentativa, MAX_TENTATIVAS, e)

        if tentativa < MAX_TENTATIVAS:
            log.info("🔁 Aguardando %ds antes de tentar novamente...", PAUSA_RETRY)
            time.sleep(PAUSA_RETRY)

    log.error("❌ E-mail não enviado após %d tentativas", MAX_TENTATIVAS)
    return False