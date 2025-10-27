import requests
import pandas as pd
from datetime import datetime, timedelta
import os


def consultar_valores_actuales(API_KEY, monedas, url_template, now):
    resultados = ''
    for symbol in monedas:
        url = url_template.format(symbol=symbol)
        response = requests.get(url).json()
        price = response.get("c")
        cadena = f'{symbol}: {price}'
        resultados = resultados + cadena + '\n'

    return resultados


def Enviar_mensaje(mensaje, bot_token, chat_id):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": mensaje}
    response = requests.post(url, data=data)
    
    return response.status_code




# Inicio del programa
# ===================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
API_KEY = os.environ.get('API_KEY')


cryptos = ["BINANCE:BTCUSDT", "BINANCE:ETHUSDT", "BINANCE:SOLUSDT"]
url_template = "https://finnhub.io/api/v1/quote?symbol={symbol}&token=" + API_KEY
now = datetime.utcnow()

resultados = consultar_valores_actuales(API_KEY, cryptos, url_template, now)
status = Enviar_mensaje(resultados, BOT_TOKEN, CHAT_ID)


