import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
import pandas as pd
from dotenv import load_dotenv
import os
import subprocess
from dateutil import parser as date_parser

load_dotenv()


# ===========================================
# CONFIGURAÇÕES
# ===========================================
EMAIL = os.getenv("EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")
raw_from = os.getenv("FROM_ALLOWLIST", "")
FROM_ALLOWLIST = [email.strip().lower() for email in raw_from.split(",") if email.strip()]
CSV_PROCESSED = "emails_processados.csv"
MINUTOS = 9
CRAWLER_PATH = "./steam_precos_scrapping.py"
LOG_DIR = "logs_crawler"
os.makedirs(LOG_DIR, exist_ok=True)


# ===========================================
# FUNÇÃO - Carregar CSV de emails já processados
# ===========================================
def carregar_emails_processados():
    if not os.path.exists(CSV_PROCESSED):
        return pd.DataFrame(columns=["email_id"])

    df = pd.read_csv(CSV_PROCESSED)
    return df


# ===========================================
# Registrar email processado
# ===========================================
def registrar_email_processado(msg_id):
    df = carregar_emails_processados()

    if msg_id not in df["email_id"].values:
        novo = pd.DataFrame({"email_id": [msg_id]})
        df = pd.concat([df, novo], ignore_index=True)
        df.to_csv(CSV_PROCESSED, index=False)


# ===========================================
# PEGAR BODY DO EMAIL
# ===========================================
def extrair_body(msg):
    body_text = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disp = str(part.get("Content-Disposition"))

            if content_type == "text/plain" and "attachment" not in disp:
                try:
                    body_text = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                except:
                    body_text = part.get_payload(decode=True).decode("latin-1", errors="ignore")
    else:
        try:
            body_text = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
        except:
            body_text = msg.get_payload(decode=True).decode("latin-1", errors="ignore")

    return body_text.strip()


# ===========================================
# FUNÇÃO - Verifica, filtra e retorna emails
# ===========================================
def verificar_emails():

    # Carrega histórico
    df_processados = carregar_emails_processados()
    ids_processados = set(df_processados["email_id"].astype(str))

    # Conecta IMAP
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(EMAIL, APP_PASSWORD)
    print("Login OK!\n")

    mail.select("inbox")

    status, data = mail.search(None, "ALL")
    if status != "OK":
        print("Erro ao buscar emails.")
        return

    email_ids = data[0].split()
    email_ids = email_ids[-30:]
    agora = datetime.now().astimezone()

    print(f"Total de emails: {len(email_ids)}")
    print("Procurando emails válidos...\n")

    for eid in reversed(email_ids):
        eid_str = eid.decode()

        # já processado?
        if eid_str in ids_processados:
            continue

        status, msg_data = mail.fetch(eid, "(RFC822)")
        if status != "OK":
            print(f"Erro ao ler email {eid_str}")
            continue

        msg = email.message_from_bytes(msg_data[0][1])

        # SUBJECT
        subject_raw, encoding = decode_header(msg["Subject"])[0]
        if isinstance(subject_raw, bytes):
            subject = subject_raw.decode(encoding or "utf-8", errors="ignore")
        else:
            subject = subject_raw or ""

        if "extrair inv" not in subject.lower():
            continue

        # REMETENTE
        remetente = msg.get("From", "").lower()
        remetente_email = remetente.split("<")[-1].strip(">").strip()

        if remetente_email not in FROM_ALLOWLIST:
            continue

        # DATA
        date_raw = msg.get("Date")
        email_date = date_parser.parse(date_raw).astimezone()

        diff_min = (agora - email_date).total_seconds() / 60
        if diff_min > MINUTOS:
            return

        # BODY
        body_text = extrair_body(msg)

        print("✓ Email válido encontrado:")
        print("  ID:", eid_str)
        print("  De:", remetente_email)
        print("  Assunto:", subject)
        print("  Data:", email_date)
        print("  Body:", body_text[:80], "...")
        print("-" * 50)

        # === CHAMA O CRAWLER IMEDIATAMENTE
        chamar_crawler({
            "id": eid_str,
            "subject": subject,
            "from": remetente_email,
            "date": email_date,
            "body": body_text
        })

        registrar_email_processado(eid_str)

    mail.logout()


# ===========================================
# CHAMAR O CRAWLER SEM ESPERAR
# ===========================================
def chamar_crawler(params):
    """
    Recebe dict do email:
    {id, subject, from, date, body}
    Dispara o crawler em background com logs separados.
    """

    # Nome do arquivo de log baseado no timestamp e ID do email
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(LOG_DIR, f"crawler_{params['id']}_{timestamp}.log")

    # Abre arquivo de log (modo write)
    log_fp = open(log_file, "w")

    # Comando com os parâmetros na ordem que você usa
    cmd = [
        "python3",
        CRAWLER_PATH,
        params["id"],
        params["from"],
        params["subject"],
        params["body"]
    ]

    # Inicia o subprocesso sem travar o monitor
    subprocess.Popen(
        cmd,
        stdout=log_fp,   # salva saída padrão no arquivo
        stderr=log_fp,   # salva erros no arquivo
        text=True
    )

    print(f"✔ Crawler iniciado em background → log salvo em: {log_file}")


# ===========================================
# MAIN
# ===========================================
if __name__ == "__main__":
    import time

    print("\n===== MONITOR DE EMAILS INICIADO =====")

    while True:
        try:
            print("\n>>> Rodando verificação:", datetime.now())
            verificar_emails()
        except Exception as e:
            print("ERRO:", e)

        print("\nAguardando 10 minutos...\n" + "="*60)
        time.sleep(600)