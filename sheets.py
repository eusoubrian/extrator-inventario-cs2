import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# ---- AUTENTICAÇÃO ----
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(
    "credentials.json",
    scopes=scopes
)

client = gspread.authorize(creds)

# ---- ABRIR PLANILHA ----
sheet = client.open("Controle de itens CS2").sheet1  # primeira aba

# ---- LER TODAS LINHAS ----
rows = sheet.get_all_records()
print("Linhas existentes:", rows)

df = pd.DataFrame(rows)

def normalizar_data(valor):
    if not valor:
        return ""

    valor = str(valor).strip()

    try:
        # tenta formato BR: dd/mm/yyyy
        return pd.to_datetime(valor, format="%d/%m/%Y").strftime("%d/%m/%Y")
    except ValueError:
        try:
            # tenta formato US: mm/dd/yyyy
            return pd.to_datetime(valor, format="%m/%d/%Y").strftime("%d/%m/%Y")
        except ValueError:
            return valor  # mantém se não conseguir converter
        

colunas_data = ["Data de Compra", "Data de Venda"]

for col in colunas_data:
    df[col] = df[col].apply(normalizar_data)

sheet.clear()
sheet.update(
    [df.columns.values.tolist()] + df.values.tolist()
)
