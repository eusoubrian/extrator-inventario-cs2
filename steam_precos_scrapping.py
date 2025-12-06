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
from helpers import *
# 76561199124145415

# Configuração do logging
logging.basicConfig(level=logging.INFO)


def extrair_inventario_steam(driver, wait):
    """Extrai o inventário do Steam e retorna um DataFrame com os dados."""
    try:
        rolar_para_baixo(driver, 3, 100)
        time.sleep(2)
        paginas = obter_total_paginas(driver, wait)
        all_df = []

        for pagina in range(1, paginas + 1):
            time.sleep(3)
            logging.info(f"Extraindo dados da página {pagina} de {paginas}...")

            page_source = driver.execute_script('return document.body.innerHTML')
            site = BeautifulSoup(page_source, 'html.parser')
            boxes = site.find_all('div', attrs={'class': 'itemHolder'})

            try:
                first_box = wait.until(EC.presence_of_element_located(
                    (By.XPATH, f'/html/body/div[1]/div[7]/div[4]/div/div[2]/div/div[4]/div[9]/div[2]/div[1]/div/div[{pagina}]/div[1]/div/a')
                ))
                time.sleep(2)
                ActionChains(driver).double_click(first_box).perform()
            except:
                pass

            for index, box in enumerate(boxes, start=1):
                time.sleep(2)

                column_df = {
                    'nome_skin': [],
                    'categoria_skin': [],
                    'exterior': [],
                    'float': [],
                    'pattern': [],
                    'run_game_link': []
                }

                page_source = driver.execute_script('return document.body.innerHTML')
                site = BeautifulSoup(page_source, 'html.parser')

                nome_skin = site.find('h1', attrs={'class': 'R1W-zMFN4WGw9JK48Yqez _12ldq1_X5RuLWAAs_ODwt7'}).text.strip()
                column_df['nome_skin'] = nome_skin
                logging.info(f'Skin: {nome_skin}')

                categoria_text = site.find('span', attrs={'class': '_1maNP9UvDekHzld1kwwQnw f6hU22EA7Z8peFWZVBJU'}).text.strip()

                if any(item in categoria_text for item in ITENS_PARA_IGNORAR):
                    logging.info('Medalha ou ítem não precificável')
                    try:
                        pyautogui.moveRel(1, 0)
                        pyautogui.moveRel(-1, 0)
                        time.sleep(5)
                        next_box = wait.until(EC.presence_of_element_located(
                            (By.XPATH, f'/html/body/div[1]/div[7]/div[4]/div/div[2]/div/div[4]/div[9]/div[2]/div[1]/div/div[{pagina}]/div[{index + 1}]/div/a')
                        ))
                        ActionChains(driver).double_click(next_box).perform()
                    except:
                        logging.info(f"Não há mais boxes para clicar. Parando na posição {index}")
                        break
                    continue
                elif not categoria_text:
                    logging.error('Item não tem categoria')
                    raise KeyError('Item não tem categoria')
                elif any(item in categoria_text for item in ITENS_DIFERENTES):
                    column_df['categoria_skin'] = categoria_text
                    column_df['exterior'] = ''
                    column_df['float'] = ''
                    column_df['pattern'] = ''
                else:
                    column_df['categoria_skin'] = categoria_text

                    lista_att = site.find_all('div', attrs={'class': 'FYJ4NYxpWeIha0N1-jUcm _1maNP9UvDekHzld1kwwQnw f6hU22EA7Z8peFWZVBJU'})
                    
                    # Procurar o exterior corretamente
                    exterior = None
                    for l in lista_att:
                        text = l.text.strip()
                        if text.startswith("Exterior:"):
                            exterior = text.replace("Exterior:", "").strip()
                            break
                    column_df['exterior'] = exterior
                    if exterior is None and "Knife" in nome_skin:
                        column_df['exterior'] = 'Not Painted'

                    div = site.find('div', attrs={'class': 'Cgo8G5L7D0oP0OHVGcq_D _3JCkAyd9cnB90tRcDLPp4W _38cfDT7owcq-7PHlx-Bx2j _3nHL7awgK1Qei1XivGvHMK'})
                    lista_info = div.find_all('div', attrs={'class': 'f6hU22EA7Z8peFWZVBJU'})

                    # Procurar pattern e wear rating independentemente da ordem
                    pattern = None
                    float_str = None
                    
                    for l in lista_info:
                        text = l.text.strip()
                    
                        if text.startswith("Pattern Template:"):
                            pattern = text.replace("Pattern Template:", "").strip()
                    
                        elif text.startswith("Wear Rating:"):
                            float_str = text.replace("Wear Rating:", "").strip()
                    
                    column_df['pattern'] = pattern
                    column_df['float'] = float_str

                run_game_link = site.find('a', attrs={'class': '_1QAy1Cc-ZLMZh5eTmrOl56 _3tzhYVET7ZK7wJDcq-fTqL _1Lj8DZ5OwROQBTPVOJcAY _3A_c3YHYd4YIjA8Y-olnPl'})
                href_run_game_link = run_game_link['href'] if run_game_link else None
                column_df['run_game_link'] = href_run_game_link


                all_df.append(column_df)

                # Clica no próximo box
                try:
                    pyautogui.moveRel(1, 0)
                    pyautogui.moveRel(-1, 0)
                    time.sleep(3)
                    next_box = wait.until(EC.presence_of_element_located(
                        (By.XPATH, f'/html/body/div[1]/div[7]/div[4]/div/div[2]/div/div[4]/div[9]/div[2]/div[1]/div/div[{pagina}]/div[{index + 1}]/div/a')
                    ))
                    ActionChains(driver).double_click(next_box).perform()
                except:
                    logging.info(f"Não há mais boxes para clicar. Parando na posição {index}")
                    break


            # Se houver mais páginas, clica na próxima
            if pagina < paginas:
                try:
                    logging.info(f"Clicando na página {pagina + 1}...")
                    proxima_pagina = wait.until(EC.presence_of_element_located((By.XPATH, f'//*[@id="pagebtn_next"]')))
                    proxima_pagina = wait.until(EC.element_to_be_clickable((By.XPATH, f'//*[@id="pagebtn_next"]')))
                    proxima_pagina.click()
                    time.sleep(3)
                except Exception as e:
                    logging.info(f"Erro ao clicar na próxima página: {e}")
                    break

        df = pd.DataFrame(all_df)
        return df

    except Exception as e:
        logging.error(f"Erro ao extrair dados: {e}")
        raise e


# ------------------------ Main ------------------------

def main(link_inv):

    driver_path = os.path.abspath("geckodriver")

    logging.info('Iniciando service')
    firefox_service = Service(executable_path=driver_path)
    options = Options()
    # options.add_argument('--headless')

    driver = webdriver.Firefox(service=firefox_service, options=options)
    wait = WebDriverWait(driver, 10)
    logging.info('Driver setado')

    driver.maximize_window()
    driver.get(link_inv)

    df_steam = extrair_inventario_steam(driver, wait)

    df_coluna_arma = cria_coluna_arma(df_steam)

    df_exterior = depara_exterior(df_coluna_arma)

    df_coluna_skin = criar_coluna_skin(df_exterior)

    df_coluna_tipo = criar_coluna_tipo(df_coluna_skin)

    logging.info(df_coluna_tipo)

    df_coluna_skin.to_excel('relatorio.xlsx')

    driver.quit()


if __name__ == '__main__':
    link_inv = 'https://steamcommunity.com/profiles/76561198799627985/inventory/#730'

    main(link_inv)