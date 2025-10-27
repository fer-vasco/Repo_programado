import requests
import pandas as pd
from datetime import datetime, timedelta


def consultar_valores_actuales(API_KEY, monedas, url_template, now):
    resultados = []
    for symbol in monedas:
        url = url_template.format(symbol=symbol)
        response = requests.get(url).json()
        price = response.get("c")
        cadena = f'{symbol}: {price}'
        resultados.append(cadena)

    return resultados


def Enviar_mensaje(mensaje, bot_token, chat_id):
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": mensaje}
    response = requests.post(url, data=data)
    
    return response.status_code



# Inicio del programa
# ===================
API_KEY = "ctas84hr01qgsps7rkhgctas84hr01qgsps7rki0"
cryptos = ["BINANCE:BTCUSDT", "BINANCE:ETHUSDT", "BINANCE:SOLUSDT"]
url_template = "https://finnhub.io/api/v1/quote?symbol={symbol}&token=" + API_KEY
now = datetime.utcnow()
bot_token = "8440738820:AAEctzmHPPg9fvCdP2jrxLJATk3I5bfgT-8"
chat_id = "7564739690"

resultados = consultar_valores_actuales(API_KEY, cryptos, url_template, now)
status = Enviar_mensaje(resultados, bot_token, chat_id)


