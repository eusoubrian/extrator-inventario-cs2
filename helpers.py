from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from bs4 import BeautifulSoup
import pandas as pd
import requests
import logging
import time
import datetime as datetime
from dotenv import load_dotenv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import re
import os

# Configuração do logging
logging.basicConfig(level=logging.INFO)

load_dotenv()

APP_PASSWORD = os.getenv("APP_PASSWORD")
EMAIL = os.getenv("EMAIL")


ITENS_DIFERENTES = [
    'Graffiti',
    'Sticker',
    'Charm',
    'Container',
    'Agent'
]


ITENS_PARA_IGNORAR = [
    'Collectible',
    'Stock',
    'Music Kit',
    'Grade Tool'
]

DE_PARA_EXTERIOR = {
    'Factory New': 'FN',
    'Minimal Wear': 'MW',
    'Field-Tested': 'FT',
    'Well-Worn': 'WW',
    'Battle-Scarred': 'BS',
    'Not Painted': 'Not Painted'
}

HEADERS = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Host": "buff.163.com",
        "Referer": "https://buff.163.com/market/",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:145.0) Gecko/20100101 Firefox/145.0",
        "X-Requested-With": "XMLHttpRequest"
}

COOKIES = {
    "Device-Id": os.getenv("DEVICE_ID"),
    "remember_me": os.getenv("REMEMBER_ME"),
    "session": os.getenv("SESSION"),
    "csrf_token": os.getenv("CSRF_TOKEN"),
    "Locale-Supported": "en",
    "game": "csgo"
}


# ------------------------ Funções ------------------------

def rolar_para_baixo(driver, quantidade, pixels):
    """Rola a página para baixo uma quantidade de vezes especificada."""
    for _ in range(quantidade):
        driver.execute_script(f"window.scrollBy(0, {pixels});")
        time.sleep(0.1)  # Pequena pausa para evitar sobrecarga

def obter_total_paginas(driver, wait):
    """Obtém o número total de páginas do inventário."""
    try:
        page_source = driver.execute_script('return document.body.innerHTML')
        site = BeautifulSoup(page_source, 'html.parser')
        paginacao = site.find('div', attrs={'pagecontrol_element pagecounts'}).text.strip()
        total_paginas = int(paginacao.split('of')[-1].strip()) if paginacao else 1
        return total_paginas
    except Exception as e:
        logging.error(f"Erro ao obter a paginação: {e}")
        return 1
    

def cria_coluna_arma(df):
    # Criar coluna vazia inicialmente no df original
    df['Arma'] = None

    # -----------------------------
    # 1. REGRAS PARA "CAIXA" (Container)
    # -----------------------------
    mask_container = df['categoria_skin'].astype(str).str.contains("Container", case=False, na=False)
    df.loc[mask_container, 'Arma'] = "CAIXA"

    # -----------------------------
    # 2. REGRAS PARA "AGENTE" (Agentes)
    # -----------------------------
    mask_agente = df['categoria_skin'].astype(str).str.contains("Agent", case=False, na=False)
    df.loc[mask_agente, 'Arma'] = "AGENTE"

    # -----------------------------
    # 3. REGRAS PARA "ZEUS" (Zeus)
    # -----------------------------
    mask_zeus = df['nome_skin'].astype(str).str.contains("Zeus", case=False, na=False)
    df.loc[mask_zeus, 'Arma'] = "ZEUS"

    # -----------------------------
    # 4. REGRAS PARA "LUVA" (Gloves)
    # -----------------------------
    mask_luva = df['nome_skin'].astype(str).str.contains("Gloves", case=False, na=False)
    df.loc[mask_luva, 'Arma'] = "LUVA"

    # -----------------------------
    # 5. REGRAS PARA "FAIXAS" (Handwraps)
    # -----------------------------
    mask_luva = df['nome_skin'].astype(str).str.contains("Hand Wraps", case=False, na=False)
    df.loc[mask_luva, 'Arma'] = "FAIXAS"

    # -----------------------------
    # 6. REGRAS PARA "STICKER" (Sticker)
    # -----------------------------
    mask_sticker = df['categoria_skin'].astype(str).str.contains("Sticker", case=False, na=False)
    df.loc[mask_sticker, 'Arma'] = "STICKER"

    # -----------------------------
    # 6. REGRAS PARA "CHAVEIRO" (Charm)
    # -----------------------------
    mask_chaveiro = df['nome_skin'].astype(str).str.contains("Charm", case=False, na=False)
    df.loc[mask_chaveiro, 'Arma'] = "CHAVEIRO"

    # -----------------------------
    # 6. REGRAS PARA "GRAFFITI" (Graffiti)
    # -----------------------------
    mask_graffiti = df['categoria_skin'].astype(str).str.contains("Graffiti", case=False, na=False)
    df.loc[mask_graffiti, 'Arma'] = "GRAFFITI"

    # -----------------------------
    # 6. REGRAS PARA Facas sem pintura (Not Painted)
    # -----------------------------
    mask_sem_pintura = df['exterior'].astype(str).str.contains("Not Painted", case=False, na=False)
    df.loc[mask_sem_pintura, 'Arma'] = df.loc[mask_sem_pintura, 'nome_skin'].str.upper()

    # -----------------------------
    # 7. REGRAS PARA ARMAS (apenas se float não é vazio)
    # -----------------------------
    df_filtered = df[
        df['float'].notna() &
        (df['float'].astype(str).str.strip() != "") &
        (~mask_container) &   # evita sobrescrever caixa
        (~mask_sem_pintura)   # evita sobrescrever facas Not Painted
    ].copy()

    def extrair_arma(skin):
        match = re.search(r'^(.*?)\s*\|', skin)
        if match:
            nome_arma = match.group(1)
        else:
            return None

        if 'StatTrak™' in skin:
            nome_arma = nome_arma.replace("StatTrak™", "").strip().upper()
            return f"{nome_arma} STATTRAK"

        return nome_arma.upper()

    # Aplica extração
    df_filtered['Arma'] = df_filtered['nome_skin'].apply(extrair_arma)

    # Atualiza no df original
    df.loc[df_filtered.index, 'Arma'] = df_filtered['Arma']

    return df


def depara_exterior(df):

    # Criar máscara: apenas onde exterior não é nulo e não é vazio
    mask_exterior = df['exterior'].notna() & (df['exterior'].astype(str).str.strip() != "")

    # Aplicar o de-para SOMENTE nessas linhas
    df.loc[mask_exterior, 'exterior'] = df.loc[mask_exterior, 'exterior'].map(DE_PARA_EXTERIOR)

    return df


def criar_coluna_skin(df):

    # Inicializar coluna
    df['Skin'] = None

    # Máscaras básicas
    mask_caixa_agente = df['Arma'].isin(['CAIXA', 'AGENTE'])
    mask_normal = ~mask_caixa_agente

    # ---------------------------------------
    # 1. Para CAIXA ou AGENTE → nome inteiro
    # ---------------------------------------
    df.loc[mask_caixa_agente, 'Skin'] = (
        df.loc[mask_caixa_agente, 'nome_skin']
        .astype(str)
        .str.upper()
    )

    # ---------------------------------------
    # 2. Para os demais → extrair após "|"
    # ---------------------------------------
    def extrair_skin(nome):
        match = re.search(r'\|\s*(.*)$', nome)
        if match:
            return match.group(1).strip().upper()
        return None

    df.loc[mask_normal, 'Skin'] = (
        df.loc[mask_normal, 'nome_skin']
        .apply(extrair_skin)
    )

    # ---------------------------------------
    # 3. Caso especial: exterior = "Not Painted"
    # → Skin = nome_skin inteiro (upper)
    # ---------------------------------------
    mask_not_painted = (
        df['exterior']
        .astype(str)
        .str.contains("Not Painted", case=False, na=False)
    )

    df.loc[mask_not_painted, 'Skin'] = (
        df.loc[mask_not_painted, 'nome_skin']
        .astype(str)
        .str.upper()
    )

    return df


def criar_coluna_tipo(df):
    df['Tipo'] = None

    # -----------------------------
    # 1. REGRAS PARA "CAIXA" (Container)
    # -----------------------------
    mask_container = df['categoria_skin'].astype(str).str.contains("Container", case=False, na=False)
    df.loc[mask_container, 'Tipo'] = "CAIXA"

    # -----------------------------
    # 2. REGRAS PARA "AGENTE" (Agent)
    # -----------------------------
    mask_agente = df['categoria_skin'].astype(str).str.contains("Agent", case=False, na=False)
    df.loc[mask_agente, 'Tipo'] = "AGENTE"

    # -----------------------------
    # 3. REGRAS PARA "ZEUS" (Zeus)
    # -----------------------------
    mask_zeus = df['nome_skin'].astype(str).str.contains("Zeus", case=False, na=False)
    df.loc[mask_zeus, 'Tipo'] = "ZEUS"

    # -----------------------------
    # 4. REGRAS PARA "Luva" (Gloves)
    # -----------------------------
    mask_luva = df['nome_skin'].astype(str).str.contains(r"Gloves|Hand Wraps", case=False, na=False)
    df.loc[mask_luva, 'Tipo'] = "LUVA"

    # -----------------------------
    # 5. REGRAS PARA "Pistolas" (Pistol)
    # -----------------------------
    mask_luva = df['categoria_skin'].astype(str).str.contains("Pistol", case=False, na=False)
    df.loc[mask_luva, 'Tipo'] = "PISTOLA"

    # -----------------------------
    # 6. REGRAS PARA "SUB" (SMG)
    # -----------------------------
    mask_luva = df['categoria_skin'].astype(str).str.contains("SMG", case=False, na=False)
    df.loc[mask_luva, 'Tipo'] = "SUB"

    # -----------------------------
    # 7. REGRAS PARA "METRALHADORA" (Machinegun)
    # -----------------------------
    mask_luva = df['categoria_skin'].astype(str).str.contains("Machinegun", case=False, na=False)
    df.loc[mask_luva, 'Tipo'] = "METRALHADORA"

    
    # -----------------------------
    # 8. SNIPER RIFLE (categoria Sniper)
    # -----------------------------
    mask_sniper = df['categoria_skin'].astype(str).str.fullmatch(r".*Sniper Rifle.*", case=False, na=False)
    df.loc[mask_sniper, 'Tipo'] = "SNIPER"

    # -----------------------------
    # 9. RIFLE (categoria contém Rifle mas NÃO contém Sniper)
    # -----------------------------
    mask_rifle = (
        df['categoria_skin'].astype(str).str.contains(r"\bRifle\b", case=False, na=False)
        & ~mask_sniper   # evita classificar Sniper Rifle como Rifle
    )
    df.loc[mask_rifle, 'Tipo'] = "RIFLE"

    # -----------------------------
    # 10. REGRAS PARA "SHOTGUN" (shotgun)
    # -----------------------------
    mask_luva = df['categoria_skin'].astype(str).str.contains("Shotgun", case=False, na=False)
    df.loc[mask_luva, 'Tipo'] = "SHOTGUN"

    # -----------------------------
    # 11. REGRAS PARA "FACA" (Knife)
    # -----------------------------
    mask_luva = df['categoria_skin'].astype(str).str.contains("Knife", case=False, na=False)
    df.loc[mask_luva, 'Tipo'] = "FACA"

    # -----------------------------
    # 12. REGRAS PARA STICKERS (Sticker)
    # -----------------------------
    mask_sticker = df['categoria_skin'].astype(str).str.contains("Sticker", case=False, na=False)
    df.loc[mask_sticker, 'Tipo'] = "STICKER"

    # -----------------------------
    # 13. REGRAS PARA CHAVEIRO (Charm)
    # -----------------------------
    mask_chaveiro = df['nome_skin'].astype(str).str.contains("Charm", case=False, na=False)
    df.loc[mask_chaveiro, 'Tipo'] = "CHAVEIRO"

    # -----------------------------
    # 13. REGRAS PARA GRAFFITI (Charm)
    # -----------------------------
    mask_graffiti = df['categoria_skin'].astype(str).str.contains("Graffiti", case=False, na=False)
    df.loc[mask_graffiti, 'Tipo'] = "GRAFFITI"

    return df


def agrupar_itens_espec(df):
    tipos_especiais = ["STICKER", "CAIXA", "CHAVEIRO", "GRAFFITI"]

    df_espec = df[df['Tipo'].isin(tipos_especiais)].copy()
    df_restante = df[~df['Tipo'].isin(tipos_especiais)].copy()

    # Adiciona a quantidade em cada linha
    df_espec['Quantidade'] = df_espec.groupby(['nome_skin', 'Tipo'])['nome_skin'].transform('count')

    # Agora remove linhas duplicadas mantendo só uma
    df_group = df_espec.drop_duplicates(subset=['nome_skin', 'Tipo'])

    # Criar Arma como “20x CAIXA”
    df_group['Arma'] = df_group['Quantidade'].astype(str) + "x " + df_group['Tipo']

    # Junta tudo
    df_final = pd.concat([df_restante, df_group], ignore_index=True)

    return df_final



def enviar_email_com_excel(
    destinatario,
    assunto,
    corpo,
    caminho_excel
):
    """
    Envia um email com um arquivo .xlsx anexado.
    """

    # Cria estrutura do email
    msg = MIMEMultipart()
    msg["From"] = EMAIL
    msg["To"] = destinatario
    msg["Subject"] = assunto

    # Corpo do email
    msg.attach(MIMEText(corpo, "plain"))

    # Lê o arquivo Excel
    with open(caminho_excel, "rb") as f:
        excel_part = MIMEApplication(f.read(), _subtype="xlsx")

    # Nome do arquivo no anexo
    excel_part.add_header(
        "Content-Disposition",
        "attachment",
        filename=caminho_excel.split("/")[-1]
    )

    msg.attach(excel_part)

    # Envia usando SMTP do Gmail
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL, APP_PASSWORD)
        smtp.send_message(msg)

    logging.info("Email enviado com sucesso!")



def validar_link_steam(link: str) -> str | None:
    """
    Valida e normaliza um link de inventário Steam.
    Regras:
      - Garante https:// no começo
      - Requer steamcommunity.com/profiles/{algo}/inventory
      - '{algo}' precisa ter ao menos 1 char, sem barra
      - Se faltar /#730, adiciona
    """
    
    if not link:
        return None

    link = link.strip()

    # Adiciona https:// se não tiver
    if not re.match(r"^https?://", link):
        link = "https://" + link

    # Regex:
    # profiles/([^/]+)  → pelo menos 1 caractere que NÃO é "/"
    pattern = r"^https://steamcommunity\.com/profiles/([^/]+)/inventory/?(#730)?$"
    match = re.match(pattern, link)

    if not match:
        return None

    steam_id = match.group(1)
    tem_730 = match.group(2)

    # Adiciona /#730 se não tiver
    if not tem_730:
        link = f"https://steamcommunity.com/profiles/{steam_id}/inventory/#730"

    return link



def req_preco_buff(nome_completo_skin):

    nome_completo_http = nome_completo_skin.replace(' ', '%20').replace('(', '').replace(')', '')

    https_base = f"https://buff.163.com/api/market/goods?game=csgo&page_num=1&page_size=50&search={nome_completo_http}"

    resp = requests.get(https_base, headers=HEADERS, cookies=COOKIES)

    if resp.json().get('code') == 'Login Required':
        raise ConnectionError('ERRO credenciais do BUFF desatualizadas')

    lista_itens = resp.json()['data']['items']

    if len(lista_itens) > 1:
        for item in lista_itens:
            if item['market_hash_name'] == nome_completo_skin:
                preco_buff = float(item['sell_min_price'])
                buy_orders = int(item['buy_num'])
                preco_buff_real = converter_rmb_para_brl(preco_buff)
                break
    else:
        preco_buff = float(lista_itens[0]['sell_min_price'])
        buy_orders = int(lista_itens[0]['buy_num'])
        preco_buff_real = converter_rmb_para_brl(preco_buff)

    logging.info(f'{nome_completo_skin}: R${preco_buff_real}')


    return preco_buff_real, buy_orders



def converter_rmb_para_brl(valor_rmb: float) -> float:
    """
    Converte um valor de RMB (CNY) para BRL usando uma API de câmbio em tempo real.

    :param valor_rmb: Valor em RMB (Yuan chinês) a ser convertido.
    :param api_key: Sua chave de API da CurrencyAPI ou serviço semelhante.
    :return: Valor convertido em reais brasileiros (BRL).
    :raises: Exception em caso de erro na requisição.
    """
    # Endpoint de taxas (CurrencyAPI como exemplo)
    url = f"https://hexarate.paikama.co/api/rates/CNY/BRL/latest"

    response = requests.get(url)
    data = response.json()

    if response.status_code == 200:
        cotacao = float(data.get('data').get('mid'))
        valor_brl = valor_rmb * cotacao
        return round(valor_brl, 2)
    else:
        raise Exception(f"Erro ao consultar a API: {data}")
    