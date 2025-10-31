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


def Procesar_dfs(df):
    df.sort_values(by=['time'], ascending=True, inplace=True)
    monedas = df['symbol'].unique().tolist()
    df_concat = pd.DataFrame()
    for moneda in monedas:
        df_moneda = df[df['symbol']==moneda].copy()
        
        # Cambio %
        df_moneda['var'] = df_moneda['price'].pct_change()*100

        # Aumento
        df_moneda['aumento'] = df_moneda['var'] >= 0

        # prueba de shift
        df_moneda['consecutivo'] = (df_moneda['aumento']==True) & (df_moneda['aumento'].shift())

        # Racha 
        df_moneda['racha'] = (df_moneda['aumento'].shift(-1)==True) & (df_moneda['consecutivo'].shift(-2)==True) | (df_moneda['aumento'].shift(-1)==True) & (df_moneda['consecutivo'].shift(-1)==True) | (df_moneda['aumento']==True) & (df_moneda['consecutivo']==True)

        # Precio n-1
        df_moneda['precio_n-1'] = df_moneda['price'].shift().bfill()

        # Min de racha
        lista_min_racha = []
        min_racha = 0.01
        for _, row in df_moneda.iterrows():
            if row['racha']==True:
                if min_racha == 0.01:
                    min_racha = row['price']
                
                lista_min_racha.append(min_racha)

            else:
                lista_min_racha.append(0.01)

        df_moneda['min_de_racha'] = lista_min_racha

        # Aumento de racha
        df_moneda['aumento_de_racha'] = (df_moneda['price'] / df_moneda['min_de_racha'] -1)*100

        # Contador de racha
        lista_cont = []
        cont = 0
        for _, row in df_moneda.iterrows():
            if row['racha'] == True:
                cont += 1
            else:
                cont = 0

            lista_cont.append(cont)

        df_moneda['contador_racha'] = lista_cont


        df_concat = pd.concat([df_concat, df_moneda])

    df_concat.reset_index(inplace=True, drop=True)
    return df_concat



def Generar_alertas(df_entrada, var_minima):
    alertas = []
    df_ult = pd.DataFrame()

    for moneda in df_entrada['symbol'].unique():
        df_temp = df_entrada[df_entrada['symbol']==moneda].tail(1).copy()
        df_ult = pd.concat([df_ult, df_temp])

    for _, row in df_ult.iterrows():

        moneda = row['symbol']
        var = round(row['var'],1)
        contador_racha = row['contador_racha']
        aumento_de_racha = round(row['aumento_de_racha'],1)
        racha = row['racha']

        # Aumento > 3%
        if var > var_minima:
            mensaje = f'{moneda} aumentó {var}%.'
            alertas.append([mensaje])

        # Racha con aumento >3%
        if (racha==True) & (aumento_de_racha>var_minima):
            mensaje = f'{moneda} lleva una racha de {contador_racha} con aumento de {aumento_de_racha}%'
            alertas.append([mensaje])

    return alertas



# Inicio del programa
# ===================

# Cargo variables secretas de entorno
load_dotenv()
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
API_KEY = os.environ.get('API_KEY')

# Defino constantes para consultar precios en línea
monedas = ['FLS', 'TER', 'STX', 'MIR', 'BE']
cryptos = ["BINANCE:BTCUSDT", "BINANCE:ETHUSDT", "BINANCE:SOLUSDT"]
url_template = "https://finnhub.io/api/v1/quote?symbol={symbol}&token=" + API_KEY
now = datetime.now(UTC)
now = now.replace(tzinfo=None)
resultados = consultar_valores_actuales(API_KEY, cryptos, url_template, now)

# Cargo valores guardados, concateno los nuevos y guardo
df_precios = pd.read_excel('precios-2.xlsx')
df_concat = pd.concat([df_precios, resultados])
df_concat.to_excel('precios-2.xlsx', index=False)

# Calculo indicadores
df_procesado = Procesar_dfs(df_concat)

# Genero alertas
alertas = Generar_alertas(df_procesado, 2)

# Envío alertas
for alerta in alertas:

    Enviar_mensaje(alerta, BOT_TOKEN, CHAT_ID)



