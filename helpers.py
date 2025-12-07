from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from bs4 import BeautifulSoup
import pandas as pd
import pyautogui
import logging
import time
import datetime as datetime
import tkinter as tk
import re
import os

# Configuração do logging
logging.basicConfig(level=logging.INFO)


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
        print(f"Erro ao obter a paginação: {e}")
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

    return df
    


### DUVIDAS
### O que acontece com os stickers/graffiti?
###
###
###
###
###
###
###
