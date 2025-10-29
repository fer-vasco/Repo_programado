import requests
import pandas as pd
from datetime import datetime, timedelta, UTC
import os
from dotenv import load_dotenv


def consultar_valores_actuales(API_KEY, monedas, url_template, now):
    resultados = ''
    df_precios = pd.DataFrame(columns=['symbol', 'price', 'time'])
    for symbol in monedas:
        url = url_template.format(symbol=symbol)
        response = requests.get(url).json()
        price = response.get("c")
        fila = [symbol, price, now]
        df_precios.loc[len(df_precios)] = fila
        
    return df_precios


def Enviar_mensaje(mensaje, bot_token, chat_id):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": mensaje}
    response = requests.post(url, data=data)
    
    return response.status_code


def Leer_txt(nombre_txt):
    with open(nombre_txt, 'r') as file:
        content = file.read()
        
    return content
    

def Comparar_precio(df_precios, moneda, hora_actual, precio_actual):

    df_filtrado = df_precios[df_precios['symbol'] == moneda].copy()
    df_filtrado.sort_values(by=['time'], ascending=False, inplace=True)
    ult_hora = df_filtrado.iloc[0]['time']
    ult_precio = df_filtrado.iloc[0]['price']
    
    var_precio = round((precio_actual / ult_precio -1) * 100, 1)
    var_hora = hora_actual - ult_hora
    var_hora = round(var_hora.seconds / 60, 1)

    return var_precio, var_hora



# Inicio del programa
# ===================

load_dotenv()
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
API_KEY = os.environ.get('API_KEY')
content = Leer_txt('datos.txt')

cryptos = ["BINANCE:BTCUSDT", "BINANCE:ETHUSDT", "BINANCE:SOLUSDT"]
url_template = "https://finnhub.io/api/v1/quote?symbol={symbol}&token=" + API_KEY
now = datetime.now(UTC)
now = now.replace(tzinfo=None)

resultados = consultar_valores_actuales(API_KEY, cryptos, url_template, now)
df_precios = pd.read_excel('precios.xlsx')
mensaje = ''

for _, row in resultados.iterrows():
    moneda = row['symbol']
    precio =row['price']
    hora =row['time']
    var_precio, var_hora = Comparar_precio(df_precios, moneda, hora, precio)
    mensaje = mensaje + f'{moneda} varió {var_precio}% en los últimos {var_hora} mins.' + '\n'
    

status = Enviar_mensaje(mensaje, BOT_TOKEN, CHAT_ID)

