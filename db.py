import sqlite3
import pandas as pd


tabla = "data/precios_SQL.db"
datos_procesados = "data/precios_procesados_SQL.db"

def Conectar_con_SQL(tabla_sql=tabla):
    return sqlite3.connect(tabla_sql)


def Guardar_df_en_SQL(dataframe_para_sql, tabla_sql=tabla):
    with Conectar_con_SQL() as conn:
        dataframe_para_sql.to_sql(
            tabla_sql,
            conn,
            if_exists="append",  # o "replace"
            index=False
        )
    print(f'df guardado en {tabla_sql}')


def Cargar_base_de_datos(tabla_sql=tabla):
    cadena = "SELECT * FROM '" + tabla_sql + "'"
    with Conectar_con_SQL() as conn:
        return pd.read_sql(cadena, conn)


def Guardar_df_procesado_en_SQL(dataframe_para_sql, tabla_sql=datos_procesados):
    with Conectar_con_SQL(tabla_sql=datos_procesados) as conn:
        dataframe_para_sql.to_sql(
            tabla_sql,
            conn,
            if_exists="replace",  # o "replace"
            index=False
        )
    print(f'df guardado en {tabla_sql}')
