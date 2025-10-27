import requests
import pandas as pd
from datetime import datetime, timedelta


def Parametros_de_visualizacion():
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    pd.set_option('display.max_colwidth', 50)
    pd.set_option('display.max_rows', None)
    pd.set_option('display.float_format', '{:.5f}'.format)



def consultar_valores_actuales(API_KEY, monedas, url_template, now):
    for symbol in monedas:
        url = url_template.format(symbol=symbol)
        response = requests.get(url).json()
        price = response.get("c")
        print(price)




# Inicio del programa
# ===================


Parametros_de_visualizacion()

API_KEY = "ctas84hr01qgsps7rkhgctas84hr01qgsps7rki0"
cryptos = ["BINANCE:BTCUSDT", "BINANCE:ETHUSDT", "BINANCE:SOLUSDT"]
url_template = "https://finnhub.io/api/v1/quote?symbol={symbol}&token=" + API_KEY
now = datetime.utcnow()

consultar_valores_actuales(API_KEY, cryptos, url_template, now)
