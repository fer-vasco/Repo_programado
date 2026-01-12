import requests
import pandas as pd
from datetime import datetime, timedelta, UTC
import os
from dotenv import load_dotenv
import sqlite3
from db import Guardar_df_en_SQL, Cargar_base_de_datos, Guardar_df_procesado_en_SQL
import pytz



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

        # Consecutivo (es verdadero cuando Aumento actual y anterior son verdaderos)
        df_moneda['consecutivo'] = (df_moneda['aumento']==True) & (df_moneda['aumento'].shift()==True)

        # Racha (shift -1 representa al valor siguiente):
            # (aumento siguiente == True) y (consecutivo 2º siguiente ==True) o x
            # (aumento siguiente == True) y (consecutivo siguiente == True) o 
            # (aumento actual == True) y (consecutivo actual ==True)
        df_moneda['racha'] = (df_moneda['aumento'].shift(-1)==True) & (df_moneda['consecutivo'].shift(-1)==True) | (df_moneda['aumento']==True) & (df_moneda['consecutivo']==True)

        # Prueba temporal de Racha
        df_moneda['inicio_racha'] = (df_moneda['racha'] == True) & (df_moneda['racha'].shift() != True)

        # Precio n-1 (shift sin valor equivale a +1)
        df_moneda['precio_n-1'] = df_moneda['price'].shift().bfill()

        # Min de racha
        lista_min_racha = []
        min_racha = 0.01
        for _, row in df_moneda.iterrows():
            if (row['racha']==True) & (row['inicio_racha']==True):
                min_racha = row['precio_n-1']
    
            elif row['racha']==False:
                min_racha = 0.01

            lista_min_racha.append(min_racha)


        df_moneda['min_de_racha'] = lista_min_racha

        # Aumento de racha (en %)
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

        # lista_cont_2 = [max(0, número-1) for número in lista_cont]
        df_moneda['contador_racha'] = lista_cont


        df_concat = pd.concat([df_concat, df_moneda])

    df_concat.reset_index(inplace=True, drop=True)
    return df_concat



def Decidir_compra_venta_01(df):

    # Si aumenta más de 5% compro. Vendo si cae menos de 2%

    lista_estr_01 = []
    acción = False
    for _, row in df.iterrows():

        accion_anterior = acción

        if row['var'] > 5:
            acción = True
        elif (row['var'] > -2) & (accion_anterior == True):
            acción = True
        else:
            acción = False

        accion_anterior = acción

        lista_estr_01.append(acción)

    df['estr_01'] = lista_estr_01

    return df


def Decidir_compra_venta_02(df):
    # Si aumenta más de 3% compro. Vendo si cae menos de 2%

    lista_estr_02 = []
    estado = 'libre'
    for _, row in df.iterrows():


        if (row['var'] > 4) & (estado == 'libre'):
            estado = 'compra'

        elif (row['var'] > 4) & (estado == 'comprado'):
            estado = 'comprado'

        elif (row['var'] > -2) & (estado == 'compra'):
            estado = 'comprado'

        elif (row['var'] > -2) & (estado == 'comprado'):
            estado = 'comprado'

        elif (row['var'] <= -2) & (estado == 'compra'):
            estado = 'venta'

        elif (row['var'] <= -2) & (estado == 'comprado'):
            estado = 'venta'

        else:
            estado = 'libre'

        lista_estr_02.append(estado)


    df['estr_02'] = lista_estr_02

    return df


def Decidir_compra_venta_03(df):
    # Si aumenta más de 3% compro. Vendo si cae menos de 2%

    lista_estr = []
    estado = 'libre'
    for _, row in df.iterrows():


        if (row['var'] > 3) & (estado == 'libre'):
            estado = 'compra'

        elif (row['var'] > 3) & (estado == 'comprado'):
            estado = 'comprado'

        elif (row['var'] > -1.5) & (estado == 'compra'):
            estado = 'comprado'

        elif (row['var'] > -1.5) & (estado == 'comprado'):
            estado = 'comprado'

        elif (row['var'] <= -1.5) & (estado == 'compra'):
            estado = 'venta'

        elif (row['var'] <= -1.5) & (estado == 'comprado'):
            estado = 'venta'

        else:
            estado = 'libre'

        lista_estr.append(estado)


    df['estr_03'] = lista_estr

    return df


def Decidir_compra_venta_04(df):
    # Si aumenta más de 3% compro. Vendo si cae menos de 2%

    lista_estr = []
    moneda = ''

    for _, row in df.iterrows():

        # El estado vuelve a cero cada vez que se cambia la moneada. Se restea de esta forma porque esta función lee todo el df sin mirar si hay cambio de moneda.
        # Se hace para que el estado no arrastre su valor del análisis de la monedas anterior.
        if row['symbol'] != moneda:
            estado = 0
            moneda = row['symbol']

        # Se pasa a cero el estado luego de cada venta. Si no se hace esto, el valor 2 queda indefinidamente.
        if estado == 2:
            estado = 0

        # El estado se pasa a 1 cada vez que la moneda aumenta 3%
        if row['var'] > 3:
            estado = 1

        # El estado se pone en 2 (venta) si baja más de 1,5% o se mantiene en cero si no había ninguna compra.
        elif row['var'] <= -1.5:
            if estado == 0:
                estado = 0
            else:
                estado = 2


        lista_estr.append(estado)


    df['estr_04'] = lista_estr

    return df



def Evaluar_estrategia(df, columna):

    # Calculo el valor_de_compra
    # ==========================
    # La lógica es la siguiente:
    # Cuando la estrategia es cero, el valor de compra es cero. Cero representa que no hay compra activa.
    # Cuando la estrategia es mayor a cero, entonces se registra el valor de compra solo si:
    #   La estrategia anterior era cero 0, o
    #   La moneda anterior era otra.

    moneda = ''
    lista_valor_compra = []

    for _, row in df.iterrows():

        if row['symbol'] != moneda:
            valor_compra = 0
            estado = 0

        if row[columna] > 0:
            if (estado == 0) | (row['symbol'] != moneda):
                valor_compra = row['price']
        else:
            valor_compra = 0

        lista_valor_compra.append(valor_compra)

        # Se actualizan los valores de estado y moneda de la fila para compararlos en la siguiente iteración.
        estado = row[columna]
        moneda = row['symbol']

    df['valor_compra'] = lista_valor_compra


    # Calculo el resultado de cada operación
    # ======================================
    # La lógica es la siguiente:
    # Si el estado es cero, el resultado es cero
    # Si el estado es mayor a cero, entonces:
    #   Si el estado siguiente es cero o la moneda siguiente cambia,
    # Entonces el resultado es el precio_actual / valor_compra -1
    # Sino, el resultado es cero.

    df['moneda_siguiente'] = df['symbol'].shift(-1).copy()
    df['estado_siguiente'] = df[columna].shift(-1).copy()

    lista_resultado = []
    resultado = 0
    for i, row in df.iterrows():
        if row[columna] == 0:
            resultado = 0
        else:
            if i == df.index[-1]:
                resultado = row['price'] / row['valor_compra'] -1
            else:
                if (row['estado_siguiente']==0) | (row['symbol']!=row['moneda_siguiente']):
                    resultado = row['price'] / row['valor_compra'] -1

        lista_resultado.append(resultado)

    df['resultado'] = lista_resultado


    # Calculo el resultado acumulado de todas las operaciones
    # =======================================================
    # La lógica es la siguiente:
    # El valor inicial es 1.
    # Luego multiplico el acumulado n-1 por el resultado n.

    lista_resultado_acumulado = []
    resultado_acumulado = 1

    for _, row in df.iterrows():
        resultado_acumulado = resultado_acumulado * (1+row['resultado'])
        lista_resultado_acumulado.append(resultado_acumulado)

    df['resultado_acumulado'] = lista_resultado_acumulado

    return df, resultado_acumulado


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


def Revisar_mercado(api_key, mercado):
    
    try:
        response = requests.get(f'https://financialmodelingprep.com/stable/exchange-market-hours?exchange={mercado}&apikey={api_key}', timeout=10)
        response.raise_for_status()
        data = response.json()
        is_open = data[0]['isMarketOpen']
        return is_open

    except Exception as e:
        print(f"Unexpected error: {e}")
        return False



# Inicio del programa
# ===================

'''
df_precios = Cargar_base_de_datos()
df_procesado = Procesar_dfs(df_precios)
df_procesado_con_estrategias = Decidir_compra_venta_01(df_procesado)
df_procesado_con_estrategias = Decidir_compra_venta_02(df_procesado)
df_procesado_con_estrategias = Decidir_compra_venta_03(df_procesado)
df_procesado_con_estrategias = Decidir_compra_venta_04(df_procesado)
df_procesado_con_estrategias, resultado_final = Evaluar_estrategia(df_procesado_con_estrategias, 'estr_04')
df_procesado_con_estrategias.to_excel('data/precios_procesados_SQL.xlsx')
print(df_procesado_con_estrategias.head(10))
print(resultado_final)
exit()
'''

# Cargo variables secretas de entorno
load_dotenv()
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
API_KEY = os.environ.get('API_KEY')
FMP_API_KEY = os.environ.get('FMP_API_KEY')


# Reviso si el mercado está abierto. Si no, no hago nada
# mercado_abierto = Revisar_mercado(FMP_API_KEY, 'NASDAQ')
# if mercado_abierto == False:
    # print('Mercado cerrado. Terminando el programad.')
    # exit()


# Defino constantes para consultar precios en línea
monedas = ['FLS', 'TER', 'STX', 'MIR', 'GH', 'FORM', 'CAH', 'INSM', 'CHRW', 'CNCK', 'ZETA', 'SGML', 'UXIN', 'CPNG', 'RZLV', 'FRMI', 'TLRY']
cryptos = ["BINANCE:BTCUSDT", "BINANCE:ETHUSDT", "BINANCE:SOLUSDT"]
url_template = "https://finnhub.io/api/v1/quote?symbol={symbol}&token=" + API_KEY
now = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires'))
now = now.replace(tzinfo=None)
resultados = consultar_valores_actuales(API_KEY, monedas, url_template, now)


# Guardo los valores descargados, cocatenándolos en la base de datos y cargo la base concatenada actualizada
Guardar_df_en_SQL(resultados)
df_concat = Cargar_base_de_datos()


# Calculo indicadores
df_procesado = Procesar_dfs(df_concat)
print(f'df procesado:')
print(df_procesado.tail(3), '\n')
Guardar_df_procesado_en_SQL(df_procesado)


# Calculo el desempeño de las estrategias
df_procesado_con_estrategias = Decidir_compra_venta_04(df_procesado)
df_procesado_con_estrategias, resultado_final = Evaluar_estrategia(df_procesado_con_estrategias, 'estr_04')
resultado_final = 'ℹ️ Desempeño: ' + str(round((resultado_final -1)*100,1)) + '% ℹ️'


# Genero alertas y envío
alertas = Generar_alertas(df_procesado, 2)
Enviar_mensaje(resultado_final, BOT_TOKEN, CHAT_ID)
for alerta in alertas:
    Enviar_mensaje(alerta, BOT_TOKEN, CHAT_ID)
