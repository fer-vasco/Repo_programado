import requests
import pandas as pd
from datetime import datetime, timedelta, UTC
import os
from dotenv import load_dotenv
import sqlite3
from db import Guardar_df_en_SQL, Cargar_base_de_datos, Guardar_df_procesado_en_SQL
import pytz
import math



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



def Ejecutar_estrategias(df, estrategia, *args):
    # Esta función ejecuta otras funciones, dependiendo de la estrategia que se le indique.
    # El argumento 'estrategia' representa otras funciones.
    # El argumento *args representa argumentos que se indican cuando se llama a la función y que se transmiten a la función 'estrategia'

    desempeño = estrategia(df, *args)

    return desempeño


def Estrategia_01(df, umbral_compra, take_profit, stop_loss):

    # Etapa 1: definir id de estrategia
    id_estrategia = '01'


    # Etapa 2: definir compra y rendimiento
    # . Compro si el aumento de precio supera el umbral
    # . Compro en cualquier hora
    # . Vendo si se activan el take profit o stop loss

    estado = 0
    valor_compra = 0
    acción = ''
    lista_estado = []
    lista_rendimiento = []
    lista_valor_compra = []
    rendimiento = 0
    moneda = ''
    formato = "%Y-%m-%d %H:%M:%S.%f"

    for i, row in df.iterrows():

        if row['symbol'] != moneda:
            estado = 0
            moneda = row['symbol']
            valor_compra = 0
            rendimiento = 0


        if row['var'] >= umbral_compra:
            if estado == 0:
                valor_compra = row['price']

            estado = 1


        if estado == 0:
            rendimiento = 0
        else:
            rendimiento = (row['price'] / valor_compra -1) * 100


        lista_estado.append(estado)
        lista_rendimiento.append(rendimiento)
        lista_valor_compra.append(valor_compra)


        if (rendimiento >= take_profit) | (rendimiento <= stop_loss):
            estado = 0
            valor_compra = 0
            rendimiento = 0


    cadena_estado = 'estado_' + id_estrategia
    cadena_rendimiento = 'rendimiento_' + id_estrategia
    cadena_valor_compra = 'valor_compra_' + id_estrategia
    
    df[cadena_estado] = lista_estado
    df[cadena_rendimiento] = lista_rendimiento
    df[cadena_valor_compra] = lista_valor_compra



    # Etapa 3: evaluar desempeño acumulado total
    # Cada vez que el estado es 1 y el siguiente valor cambia.
    df['ultimos_desempeños'] = (df[cadena_estado] != df[cadena_estado].shift(periods=-1, fill_value=0)) & (df[cadena_estado]==1)
    df_desempeños = df[df['ultimos_desempeños']==True].copy()
    
    desempeño_conjunto = 1
    for i, row in df_desempeños.iterrows():
        desempeño_conjunto = desempeño_conjunto * (1+row[cadena_rendimiento]/100)
    


    # Etapa 4: evaluar el rendimiento asumiendo inversiones separadas por moneda
    lista_desempeños = []
    monedas = df_desempeños['symbol'].unique().tolist()
    for moneda in monedas:
        desempeño_moneda = 1
        df_moneda = df_desempeños[df_desempeños['symbol']==moneda]
        for i, row in df_moneda.iterrows():
            desempeño_moneda = desempeño_moneda * (1+row[cadena_rendimiento]/100)

        lista_desempeños.append(desempeño_moneda-1)

    desempeño_separado = 0
    for i in lista_desempeños:
        desempeño_separado = desempeño_separado + i



    # Etapa 5: generar información para análisis de operaciones

    moneda = ''    
    lista_contador_compra = []
    lista_hora_de_copmpra = []
    lista_hora_de_venta = []
    lista_minutos_de_compra = []
    hora_de_compra = ''

    for i, row in df.iterrows():
        if row['symbol'] != moneda:
            moneda = row['symbol']
            contador_compra = 0
            estado = 'libre'
            tiempo_de_compra = ''
            hora_de_compra = 0
            hora_de_venta = 0
            minutos_de_compra = 0


        if row[cadena_estado] == 1:
            contador_compra +=1
            if estado == 'libre':
                tiempo_de_compra = row['time']
                hora_de_compra = datetime.strptime(tiempo_de_compra, formato).hour

            estado = 'compra'
            tiempo = datetime.strptime(row['time'], formato) - datetime.strptime(tiempo_de_compra, formato)
            minutos_de_compra = tiempo.total_seconds() / 60

            if row['ultimos_desempeños'] == True:
                hora_de_venta = datetime.strptime(row['time'], formato).hour


        else:
            estado = 'libre'
            contador_compra = 0
            tiempo_de_compra = ''
            hora_de_compra = 0
            hora_de_venta = 0
            minutos_de_compra = 0

        lista_contador_compra.append(contador_compra)
        lista_hora_de_copmpra.append(hora_de_compra)
        lista_hora_de_venta.append(hora_de_venta)
        lista_minutos_de_compra.append(minutos_de_compra)



    df['contador_compra'] = lista_contador_compra
    df['hora_de_compra'] = lista_hora_de_copmpra
    df['hora_de_venta'] = lista_hora_de_venta
    df['minutos_de_compra'] = lista_minutos_de_compra
    df_estrategia = df.copy()
    
    return df_estrategia, df_desempeños, desempeño_separado



def Estrategia_02(df, umbral_compra, take_profit, stop_loss, horas, lista_negra):

    # Etapa 1: definir id de estrategia
    id_estrategia = '02'

    # Etapa 2: definir compra y rendimiento
    # . Compro si el aumento de precio supera el umbral
    # . Compro solo en las horas indicadas
    # . Vendo si se activan el take profit o stop loss

    estado = 0
    valor_compra = 0
    acción = ''
    lista_estado = []
    lista_rendimiento = []
    lista_valor_compra = []
    rendimiento = 0
    moneda = ''
    formato = "%Y-%m-%d %H:%M:%S.%f"

    for i, row in df.iterrows():

        hora = datetime.strptime(row['time'], formato).hour

        if row['symbol'] != moneda:
            estado = 0
            moneda = row['symbol']
            valor_compra = 0
            rendimiento = 0


        if (row['var'] >= umbral_compra) & (hora in horas) & (row['symbol'] not in lista_negra):
            if estado == 0:
                valor_compra = row['price']

            estado = 1


        if estado == 0:
            rendimiento = 0
        else:
            rendimiento = (row['price'] / valor_compra -1) * 100


        lista_estado.append(estado)
        lista_rendimiento.append(rendimiento)
        lista_valor_compra.append(valor_compra)


        if (rendimiento >= take_profit) | (rendimiento <= stop_loss):
            estado = 0
            valor_compra = 0
            rendimiento = 0


    cadena_estado = 'estado_' + id_estrategia
    cadena_rendimiento = 'rendimiento_' + id_estrategia
    cadena_valor_compra = 'valor_compra_' + id_estrategia
    
    df[cadena_estado] = lista_estado
    df[cadena_rendimiento] = lista_rendimiento
    df[cadena_valor_compra] = lista_valor_compra



    # Etapa 3: evaluar rendimiento acumulado total
    # Hay un desempeño cada vez que el estado es 1 y el siguiente valor cambia. Puede ser una venta o ser una inversión sin cerrarse y por lo tanto se mide su ultimo valor disponible.
    df['ultimos_desempeños'] = (df[cadena_estado] != df[cadena_estado].shift(periods=-1, fill_value=0)) & (df[cadena_estado]==1)
    df_desempeños = df[df['ultimos_desempeños']==True].copy()
    
    desempeño_conjunto = 1
    for i, row in df_desempeños.iterrows():
        desempeño_conjunto = desempeño_conjunto * (1+row[cadena_rendimiento]/100)
    


    # Etapa 4: evaluar el rendimiento asumiendo inversiones separadas por moneda
    lista_desempeños = []
    monedas = df_desempeños['symbol'].unique().tolist()
    for moneda in monedas:
        desempeño_moneda = 1
        df_moneda = df_desempeños[df_desempeños['symbol']==moneda].copy()
        for i, row in df_moneda.iterrows():
            desempeño_moneda = desempeño_moneda * (1+row[cadena_rendimiento]/100)

        lista_desempeños.append(desempeño_moneda-1)

    desempeño_separado = 0
    for i in lista_desempeños:
        desempeño_separado = desempeño_separado + i



    # Etapa 5: generar información para análisis de operaciones
    # Genero indicadores que voy a enviar por mensaje.
    indicadores = []
    operaciones = len(df_desempeños)
    fecha_min = datetime.strptime(df['time'].min(), formato)
    fecha_max = datetime.strptime(df['time'].max(), formato)
    días = fecha_max - fecha_min
    días = math.ceil(días.total_seconds() / (60*60*24))
    op_por_día = round(operaciones / días,1)
    operaciones_positivas = len(df_desempeños[df_desempeños[cadena_rendimiento]>0])
    operaciones_negativas = len(df_desempeños[df_desempeños[cadena_rendimiento]<0])
    rendimiendo_positivo_promedio = round(df_desempeños[df_desempeños[cadena_rendimiento]>0][cadena_rendimiento].mean(), 1)
    rendimiendo_negativo_promedio = abs(round(df_desempeños[df_desempeños[cadena_rendimiento]<0][cadena_rendimiento].mean(), 1))
    relación_PL = round(rendimiendo_positivo_promedio / rendimiendo_negativo_promedio, 1)

    # Genero indicadores que voy a usar en el power BI.
    moneda = ''    
    lista_contador_compra = []
    lista_hora_de_copmpra = []
    lista_hora_de_venta = []
    lista_minutos_de_compra = []
    hora_de_compra = ''
    formato = "%Y-%m-%d %H:%M:%S.%f"

    for i, row in df.iterrows():
        if row['symbol'] != moneda:
            moneda = row['symbol']
            contador_compra = 0
            estado = 'libre'
            tiempo_de_compra = ''
            hora_de_compra = 0
            hora_de_venta = 0
            minutos_de_compra = 0


        if row[cadena_estado] == 1:
            contador_compra +=1
            if estado == 'libre':
                tiempo_de_compra = row['time']
                hora_de_compra = datetime.strptime(tiempo_de_compra, formato).hour

            estado = 'compra'
            tiempo = datetime.strptime(row['time'], formato) - datetime.strptime(tiempo_de_compra, formato)
            minutos_de_compra = tiempo.total_seconds() / 60

            if row['ultimos_desempeños'] == True:
                hora_de_venta = datetime.strptime(row['time'], formato).hour


        else:
            estado = 'libre'
            contador_compra = 0
            tiempo_de_compra = ''
            hora_de_compra = 0
            hora_de_venta = 0
            minutos_de_compra = 0

        lista_contador_compra.append(contador_compra)
        lista_hora_de_copmpra.append(hora_de_compra)
        lista_hora_de_venta.append(hora_de_venta)
        lista_minutos_de_compra.append(minutos_de_compra)


    df['contador_compra'] = lista_contador_compra
    df['hora_de_compra'] = lista_hora_de_copmpra
    df['hora_de_venta'] = lista_hora_de_venta
    df['minutos_de_compra'] = lista_minutos_de_compra
    df_estrategia = df.copy()
    

    # Preparo el mensaje que voy a enviar al celu
    desempeño_separado = round(desempeño_separado*100,1)
    indicadores.append(f'🎲 Desempeño: {desempeño_separado}% 🎲')
    indicadores.append(f'🪲 {operaciones} operaciones en {días} días ({op_por_día} op/día)')
    indicadores.append(f'🪲 Operaciones positivas/negativas: {operaciones_positivas}/{operaciones_negativas}')
    indicadores.append(f'🪲 Relación P/L promedio: {rendimiendo_positivo_promedio}%/{rendimiendo_negativo_promedio}% ({relación_PL})')
    mensaje = ''
    for indicador in indicadores:
        mensaje = mensaje + indicador + '\n'

    return mensaje, df_estrategia


# Inicio del programa
# ===================

'''
df_precios = Cargar_base_de_datos()
df_procesado = Procesar_dfs(df_precios)
horas = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
horas = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
lista_negra = ['ANPA', 'CNCK']
mensaje, df_estrategia = Ejecutar_estrategias(df_procesado, Estrategia_02, 3, 4, -1.5, horas, lista_negra)
df_estrategia.to_excel('data/df_estrategia.xlsx')
print(mensaje)
exit()
'''

# Cargo variables secretas de entorno
load_dotenv()
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
API_KEY = os.environ.get('API_KEY')
FMP_API_KEY = os.environ.get('FMP_API_KEY')

'''
# Reviso si el mercado está abierto. Si no, no hago nada
mercado_abierto = Revisar_mercado(FMP_API_KEY, 'NASDAQ')
if mercado_abierto == False:
    print('Mercado cerrado. Terminando el programa.')
    exit()
'''

monedas = [
'FLS', 'TER', 'STX', 'MIR', 'GH',  
'FORM', 'CAH', 'INSM', 'CHRW', 'CNCK', 
'ZETA', 'SGML', 'UXIN', 'CPNG', 'RZLV', 
'FRMI', 'TLRY', 'VISN', 'ANPA', 'CRML', 
'ALT5', 'AHMA', 'AMN', 'WSHP', 'SLV', 
'GLD', 'IBRX' 'RILY', 'JELD', 'BNR', 
'AXTI', 'ERAS', 'IPSC', 'GLXY', 'NEOV'
'TYGO', 'CTMX','NUAI', 'HYMC', 'DAWN', 
'ROMA', 'NVAX']


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


# Calculo el desempeño de las estrategias asumiendo inversiones separadas para cada moneda
umbral_compra = 3
take_profit = 4
stop_loss = -1.5
horas = [11, 13, 14]
lista_negra = ['ANPA', 'CNCK']
mensaje = Ejecutar_estrategias(df_procesado, Estrategia_02, umbral_compra, take_profit, stop_loss, horas, lista_negra)


# Genero alertas y envío
Enviar_mensaje(mensaje, BOT_TOKEN, CHAT_ID)
alertas = Generar_alertas(df_procesado, 3)
for alerta in alertas:

    Enviar_mensaje(alerta, BOT_TOKEN, CHAT_ID)
