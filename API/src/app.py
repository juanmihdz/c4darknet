import base64
import os
import io
import sys
from flask import Flask, jsonify, request, Response, render_template
import numpy as np
from config import config
import pandas as pd

from pony.orm import db_session

from urllib.parse import unquote
from sqlalchemy import create_engine
import matplotlib.pyplot as plt


# Obtenemos la ruta absoluta del directorio que contiene el archivo app.py
current_directory = os.path.abspath(os.path.dirname(__file__))

# Obtenemos la ruta del directorio que contiene el módulo dbutils.py
crawler_directory = os.path.join(current_directory, '..', '..', 'crawler')

# Obtenemos la ruta del directorio que contiene el módulo dbutils.py
api_directory = os.path.join(current_directory, '..')

# Agregamos el directorio del módulo al sys.path
sys.path.append(crawler_directory)
sys.path.append(api_directory)


from pony.flask import db_session
import database.dbutils as dbutils # Importamos todo el módulo dbutils.py
import models.sites as sites# Importa el módulo sites desde la carpeta models

#--------------------------------------------------------------------------------------------------------------

# Parametros de configuracion para los graficos
# fondict for axis labels
font_labels = {'family' : 'arial',
        'weight' : 'normal',
        'size'   : 26}
# fondict for title labels
font_title = {'family' : 'arial',
        'weight' : 'bold',
        'size'   : 24}
# fontsize for tickso
ticks_fontsize=20

# legend fontsize
legend_fontsize=15

# Linewidth and markersize
lw=5
ms=10

#-----------------------------GLOBALES----------------------------------------------

logprocessing_limit = 1000000
engine = create_engine('mysql+pymysql://phpmyadmin:Juanmitigre99!@localhost:'+'3306'+'/freenet_database', echo=False)
df_site = pd.read_sql_query('select * from site', engine)
df_status = pd.read_sql_query('select * from sitestatus', engine)
df_source = pd.read_sql_query('select * from sitesource', engine)
df_logprocessing = pd.read_sql_query('select * from siteprocessinglog limit ' + str(logprocessing_limit), engine)
df_language = pd.read_sql_query('select sitelanguage.* from sitelanguage', engine)
df_sitehomeinfo = pd.read_sql_query('select sitehomeinfo.* from sitehomeinfo', engine)
df_connectivity = pd.read_sql_query('select siteconnectivitysummary.* from siteconnectivitysummary', engine)
df_src_link = pd.read_sql_query('select link_site.* from link_site', engine)
df_dst_link = pd.read_sql_query('select link_site_2.* from link_site_2', engine)

# visualizacion al maximo el tamaño de las columnas
pd.set_option('display.max_colwidth', None)

# Agregamos el dato de la duracion, en minutos, que seria la diferencia entre la fecha de inicio y la de fin
df_site['duration'] = (df_site['timestamp_s'] - df_site['timestamp']).apply(lambda x:x.total_seconds()/60)

#Agregamos una abreviatura para los sitios de freenet
df_site['abbr'] = df_site['name']
for i in range(0, len(df_site.index)):
    name = df_site['abbr'][i]
    
    #Comprobamos si acaba en barra
    if name[-1] == "/":
        name = name[:-1]
    #Comprobamos si es USK o SSK
    is_usk = False
    if "USK@" in name:
        is_usk = True
    
    #Seleccionamos lo de despues del arroba
    name = name.split("@", 1)[1]

    if is_usk:
        name = name.rsplit("/", 1)[0]
        name = name.split("/", 1)[1]
    else:
        if "/" in name:
            name = name.split("/", 1)[1]
        
    #df_site['abbr'][i] = name
    df_site.at[i, 'abbr'] = name

# Agregamos la informacion del estado del sitio
df_site_status = df_site.merge(df_status,left_on='current_status',right_on='id')
df_site_status = df_site_status.drop(labels=['type_x','id_y','description','current_status'],axis=1)
df_site_status=df_site_status.rename(columns={'type_y':'status'})

# Agregamos la infromacion de la fuente del sitio
df_site_source = df_site.merge(df_source,left_on='source',right_on='id')
df_site_source = df_site_source.drop(labels=['type_x','id_y','description','source'],axis=1)
df_site_source=df_site_source.rename(columns={'type_y':'source'})

# Unimos ambas informaciones en un mismo lugar
df_site_source_status = df_site_source.merge(df_status,left_on='current_status',right_on='id')
df_site_source_status = df_site_source_status.drop(labels=['id','current_status','description'],axis=1)
df_site_source_status = df_site_source_status.rename(columns={'type':'current_status', 'id_x':'id'})

#Unimos la informacion del sitio con las de la conectividad
df_site_conn = df_site_source_status.merge(df_connectivity,left_on='id',right_on='site')
df_site_conn = df_site_conn.drop(labels=['id_x','id_y','pages_x'],axis=1)
df_site_conn = df_site_conn.rename(columns={'pages_y':'pages'})

#Unimos la conectividad de los nodos para los grafos
df_links = df_src_link.merge(df_dst_link,left_on='link',right_on='link')
df_links = df_links.rename(columns={'site_x':'Source','site_y':'Target','link':'Label'})

#Unimos los site con la info de home
df_site_home = df_site.merge(df_sitehomeinfo,left_on='id',right_on='site')
df_site_home = df_site_home.drop(labels=['id_x','id_y'],axis=1)

#Unimos los sites con la info del home con el lenguaje
df_site_home_lan = df_site_home.merge(df_language[df_language['engine'] == 'GOOGLE'],left_on='site',right_on='site')
#Le agregamos una columna mas que usaremos para el analisis de los datos
df_site_home_lan['illicit_category'] = ""
df_site_home_lan['illicit_value'] = 0

#----------------------------------------Métodos---------------------------------------------------------

def obtenerImagenBase64(plt,fig=None):
        buffer = io.BytesIO()
        if fig == None:
            plt.savefig(buffer, format='png')
        else:
            fig.savefig(buffer,format='png')
            plt.close(fig)
        plt.close()
        buffer.seek(0)
        image_png = buffer.getvalue()
        graphic_base64 = base64.b64encode(image_png)
        
        return graphic_base64.decode()

#----------------------------------------FLASK---------------------------------------------------------

app = Flask(__name__)

@app.route("/")
def index():
    return "<h1>Hello World!</h1>"

@app.route("/getFuenteSitios") #en general
def getDistFuenteSitios():
    # Vemos la fuente de los sitios en general
    total_all_source = df_site_source_status['source'].value_counts()

    # Creamos el gráfico de pastel
    plt.figure(figsize=(8, 8))
    total_all_source.plot(kind='pie', autopct='%1.1f%%', startangle=90, fontsize=14)
    plt.title('Distribución de fuentes de los sitios')
    plt.ylabel('')

    # Obtener la imagen codificada en Base64
    img_base64 = obtenerImagenBase64(plt)

    # Devolver la imagen como JSON
    return jsonify(
        {
            "getFuenteSitiosResponse": {
                "imgb64": img_base64
            }
        }
    )


@app.route("/getFuenteSitiosActivos")
def getFuenteSitiosActivos():
    # Vemos la fuente de los sitios activos
    df_site_active = df_site_source_status[df_site_source_status['current_status'] == 'FINISHED']
    total_active_source = df_site_active['source'].value_counts()

    # Creamos el gráfico de pastel
    plt.figure(figsize=(8, 8))
    total_active_source.plot(kind='pie', autopct='%1.1f%%', startangle=90, fontsize=14)
    plt.title('Distribución de fuentes de sitios activos')
    plt.ylabel('')

    # Obtener la imagen codificada en Base64
    img_base64 = obtenerImagenBase64(plt)

    # Devolver la imagen como JSON
    return jsonify(
        {
            "getFuenteSitiosActivosResponse": {
                "imgb64": img_base64
            }
        }
    )

@app.route("/getDistSitiosPorEstado")
def getDistSitiosPorEstado():
    # Vemos la distribución de sitios por estado
    total_status_sites = df_site_status['status'].value_counts()

    # Creamos el gráfico de pastel
    plt.figure(figsize=(8, 8))
    total_status_sites.plot(kind='pie', autopct='%1.1f%%', labeldistance=None, fontsize=14)
    plt.title('Distribución de sitios por estado')
    plt.ylabel('')
    plt.legend(loc='upper right', bbox_to_anchor=(0.25, 0.25))

    # Obtener la imagen codificada en Base64
    img_base64 = obtenerImagenBase64(plt)

    # Devolver la imagen como JSON
    return jsonify(
        {
            "getDistSitiosPorEstadoResponse": {
                "imgb64": img_base64
            }
        }
    )

@app.route("/getEvolucionTempSitiosProcesados")
def getEvolucionTempSitiosProcesados():
    # Evolucion temporal de los sitios procesados
    df_ss_analysis = df_site_source_status.copy()
    df_ss_analysis['timestamp'] = pd.to_datetime(df_ss_analysis['timestamp'])

    df_ss_analysis_s = df_site_source_status.copy()
    df_ss_analysis_s['timestamp_s'] = pd.to_datetime(df_ss_analysis_s['timestamp_s'])

    df_ss_s = df_ss_analysis_s.copy()  # Con fecha de stop del crawling
    df_ss = df_ss_analysis.copy()  # Con fecha de incorporacion a la bbdd

    # Eliminar filas duplicadas para evitar KeyError
    df_ss.drop_duplicates(subset='timestamp', keep='last', inplace=True)
    df_ss_s.drop_duplicates(subset='timestamp_s', keep='last', inplace=True)

    # Verificar si hay fechas válidas en el índice
    if not df_ss.empty and not df_ss_s.empty:
        df_ss_all = df_ss[df_ss['timestamp'] >= '2020-08-04 20:19:17']
        df_ss_all_s = df_ss_s[df_ss_s['timestamp_s'] >= '2020-08-04 20:19:17']

        temp_evo_sites = df_ss_all.resample('D', on='timestamp').count()['name'].cumsum()

        # Ordenar el índice temporal de forma ascendente
        temp_evo_sites.sort_index(inplace=True)

        # Creamos el gráfico de líneas
        plt.figure(figsize=(8, 8))
        ax = temp_evo_sites.plot(kind='line', fontsize=14, style='o-')
        ax.set_ylabel('Sitios procesados')
        ax.set_xlabel('Fecha')

        # Obtener la imagen codificada en Base64
        img_base64 = obtenerImagenBase64(plt)

        # Devolver la imagen como JSON
        return jsonify(
            {
                "getEvolucionTempSitiosProcesadosResponse": {
                    "imgb64": img_base64
                }
            }
        )
    else:
        return jsonify({"error": "No hay fechas válidas en el índice o la fecha '2020-08-04 20:19:17' es la única fecha disponible."})

@app.route("/getEvolucionTempSitiosCrawleados")
def getEvolucionTempSitiosCrawleados():
    # Evolucion temporal de los sitios crawleados
    df_ss_analysis = df_site_source_status.copy()
    df_ss_analysis['timestamp_s'] = pd.to_datetime(df_ss_analysis['timestamp_s'])

    df_ss_analysis_s = df_site_source_status.copy()
    df_ss_analysis_s['timestamp_s'] = pd.to_datetime(df_ss_analysis_s['timestamp_s'])

    df_ss_s = df_ss_analysis_s.copy()  # Con fecha de stop del crawling
    df_ss = df_ss_analysis.copy()  # Con fecha de incorporacion a la bbdd

    df_ss_all_s = df_ss_s[df_ss_s['current_status'] == 'FINISHED']

    # Verificar si hay fechas válidas en el índice
    if not df_ss_all_s.empty:
        temp_evo_sites_active = df_ss_all_s.resample('D', on='timestamp_s').count()['name'].cumsum()

        # Ordenar el índice temporal de forma ascendente
        temp_evo_sites_active.sort_index(inplace=True)

        # Creamos el gráfico de líneas
        plt.figure(figsize=(8, 8))
        ax = temp_evo_sites_active.plot(kind='line', fontsize=14, style='o-')
        ax.set_ylabel('Sitios crawleados con éxito', fontsize=14)
        ax.set_xlabel('Fecha', fontsize=16)

        # Obtener la imagen codificada en Base64
        img_base64 = obtenerImagenBase64(plt)

        # Devolver la imagen como JSON
        return jsonify(
            {
                "getEvolucionTempSitiosCrawleadosResponse": {
                    "imgb64": img_base64
                }
            }
        )
    else:
        return jsonify({"error": "No hay fechas válidas en el índice de sitios crawleados con éxito."})

# Ruta para obtener la comparación del número de sitios crawleados tras el primer día y al finalizar
@app.route("/getComparacionCrawleadosFirstDayLastDay")
def getComparacionCrawleadosFirstDayLastDay():

    # Evolucion temporal de los sitios crawleados
    df_ss_analysis = df_site_source_status.copy()
    df_ss_analysis['timestamp_s'] = pd.to_datetime(df_ss_analysis['timestamp_s'])

    df_ss_analysis_s = df_site_source_status.copy()
    df_ss_analysis_s['timestamp_s'] = pd.to_datetime(df_ss_analysis_s['timestamp_s'])

    df_ss_s = df_ss_analysis_s.copy()  # Con fecha de stop del crawling
    df_ss = df_ss_analysis.copy()  # Con fecha de incorporacion a la bbdd

    # Numero de sitios con crawling finalizado tras el primer día
    df_ss_first_day = df_ss_s.loc[df_ss_s['timestamp_s'].dt.date == pd.to_datetime('2020-08-04').date()]

    site_crawled_first_day = df_ss_first_day[df_ss_first_day['current_status'] == 'FINISHED']['source'].value_counts()

    # Numero de sitios con crawling finalizado tras el último día
    site_crawled_last_day = df_ss[df_ss['current_status'] == 'FINISHED']['source'].value_counts()

    # Crear DataFrame para la comparación
    df = pd.DataFrame({'Primer día': site_crawled_first_day, 'Al finalizar': site_crawled_last_day}, index=['DISCOVERED', 'SEED'])

    # Creamos el gráfico de barras
    plt.figure(figsize=(12, 8))
    ax = df.plot(rot=0, kind='bar', fontsize=14)
    for p in ax.patches:
        ax.annotate(np.round(p.get_height(), decimals=2), (p.get_x() + p.get_width() / 2., p.get_height()),
                    ha='center', va='center', xytext=(0, 10), textcoords='offset points')

    ax.set_ylabel('Sitios correctamente crawleados')
    ax.set_xlabel('Fuente')

    # Obtener la imagen codificada en Base64
    img_base64 = obtenerImagenBase64(plt)

    print(site_crawled_first_day)
    print(site_crawled_last_day)

    # Devolver la imagen como JSON
    return jsonify(
        {
            "getComparacionCrawleadosFirstDayLastDayResponse": {
                "imgb64": img_base64
            }
        }
    )

# Ruta para obtener el histograma de intentos de descubrimientos de sitios crawleados
@app.route("/getHistogramaIntentosDescubrimientos")
def getHistogramaIntentosDescubrimientos():
    # Intentos de descubrimientos de los sitios crawleados
    df_ss_analysis = df_site_source_status.copy()
    df_ss_analysis['timestamp_s'] = pd.to_datetime(df_ss_analysis['timestamp_s'])

    df_ss_analysis_s = df_site_source_status.copy()
    df_ss_analysis_s['timestamp_s'] = pd.to_datetime(df_ss_analysis_s['timestamp_s'])

    df_ss_s = df_ss_analysis_s.copy()  # Con fecha de stop del crawling
    df_ss = df_ss_analysis.copy()  # Con fecha de incorporacion a la bbdd

    try_disc_crawled_sites = df_ss[df_ss['current_status'] == 'FINISHED']['discovering_tries']

    # Verificar si hay datos válidos para el histograma
    if not try_disc_crawled_sites.empty:
        # Creamos el histograma de intentos de descubrimientos de sitios crawleados
        plt.figure(figsize=(15, 8))
        ax = try_disc_crawled_sites.hist(bins=600, xlabelsize=18, ylabelsize=18)
        ax.set_ylabel('Sitios crawleados con éxito', fontsize=18)
        ax.set_xlabel('Intentos de descubrimiento', fontsize=18)

        # Obtener la imagen codificada en Base64
        img_base64 = obtenerImagenBase64(plt)

        # Devolver la imagen como JSON
        return jsonify(
            {
                "getHistogramaIntentosDescubrimientosResponse": {
                    "imgb64": img_base64
                }
            }
        )
    else:
        return jsonify({"error": "No hay datos válidos para generar el histograma de intentos de descubrimientos de sitios crawleados."})

# Ruta para realizar el análisis de idioma según Google
@app.route("/analisisIdiomaGoogle")
def analisisIdiomaGoogle():
    language_google = df_language[df_language['engine'] == 'GOOGLE']['language']
    language_google = language_google.replace('', 'undefined')
    language_google_count = language_google.value_counts()

    # Definir el límite para agrupar en 'others'
    # ToDo parametro 7 pasarlo por url
    condition = language_google_count < 7
    mask_obs = language_google_count[condition].index
    mask_dict = dict.fromkeys(mask_obs, 'others')

    language_google = language_google.replace(mask_dict)
    language_google_count = language_google.value_counts()

    # Obtener valores y porcentajes de cada idioma
    language_google_count_norm = language_google.value_counts(normalize=True)
    language_google_count_all = pd.concat([language_google_count, language_google_count_norm], axis=1)
    language_google_count_all.columns = ['Valores', 'Porcentaje']

    # Creamos el gráfico de pastel
    plt.figure(figsize=(8, 8))
    language_google_count.plot(kind='pie', autopct='%1.1f%%', labeldistance=None, fontsize=14)
    plt.legend(loc='upper right', bbox_to_anchor=(0.25, 0.25))

    # Obtener la imagen codificada en Base64
    img_base64 = obtenerImagenBase64(plt)

    # Devolver la tabla de valores y porcentajes y el gráfico como JSON
    return jsonify(
        {
            "analisisIdiomaGoogleResponse": {
                "tabla": language_google_count_all.to_dict(), 
                "imgb64": img_base64
            }
        }
    )

# Ruta para realizar el análisis de idioma según NLTK
@app.route("/analisisIdiomaNLTK")
def analisisIdiomaNLTK():
    language_nltk = df_language[df_language['engine'] == 'NLTK']['language']
    language_nltk_count = language_nltk.value_counts()

    # Definir el límite para agrupar en 'others'
    condition = language_nltk_count < 17
    mask_obs = language_nltk_count[condition].index
    mask_dict = dict.fromkeys(mask_obs, 'others')

    language_nltk = language_nltk.replace(mask_dict)
    language_nltk_count = language_nltk.value_counts()

    # Obtener valores y porcentajes de cada idioma
    language_nltk_count_norm = language_nltk.value_counts(normalize=True)
    language_nltk_count_all = pd.concat([language_nltk_count, language_nltk_count_norm], axis=1)
    language_nltk_count_all.columns = ['Valores', 'Porcentaje']

    # Creamos el gráfico de pastel
    plt.figure(figsize=(8, 8))
    language_nltk_count.plot(kind='pie', autopct='%1.1f%%', labeldistance=None, fontsize=14)
    plt.legend(loc='upper right', bbox_to_anchor=(0.25, 0.25))

    # Obtener la imagen codificada en Base64
    img_base64 = obtenerImagenBase64(plt)

    # Devolver la tabla de valores y porcentajes y el gráfico como JSON
    return jsonify(
        {
            "analisisIdiomaNTLKResponse": {
                "tabla": language_nltk_count_all.to_dict(),
                "imgb64": img_base64
            }
        }
    )

#ToDo mostrar un input con el numero de sitios que tienen X número de paginas 
# Ruta para realizar el análisis del número de páginas en los sitios crawleados
@app.route("/analisisNumeroPaginas")
def analisisNumeroPaginas():
    total_in_status = df_site_status[df_site_status['status'] == 'FINISHED']['pages'].count()
    value_count_pagescrawledsites = df_site_status[df_site_status['status'] == 'FINISHED']['pages'].value_counts()

    # Obtener el número de sitios con 5 páginas o menos
    num_sites_5_or_less = value_count_pagescrawledsites[value_count_pagescrawledsites.index <= 5].sum()

    # Obtener porcentajes
    percentage_pages_crawled_sites = (value_count_pagescrawledsites / total_in_status) * 100

    # Obtener valores absolutos
    absolute_values_pages_crawled_sites = value_count_pagescrawledsites

    # Creamos la tabla con valores y porcentajes
    analysis_table = pd.DataFrame({"Valores": absolute_values_pages_crawled_sites, "Porcentaje": percentage_pages_crawled_sites})

    # Creamos el histograma de número de páginas
    plt.figure(figsize=(15, 8))
    ax = df_site_status[df_site_status['status'] == 'FINISHED']['pages'].hist(bins=100, range=(0, 100), xlabelsize=18, ylabelsize=18)

    ax.set_ylabel('Sitios crawleados con éxito', fontsize=18)
    ax.set_xlabel('Número de páginas', fontsize=18)

    # Configurar el eje y en escala lineal
    ax.set_yscale('linear')

    # Obtener la imagen codificada en Base64
    img_base64 = obtenerImagenBase64(plt)

    # Devolver la tabla de valores y porcentajes y el gráfico como JSON
    return jsonify(
        {
            "analisisNumeroPaginasResponse": {
                "tabla": analysis_table.to_dict(orient="index"), 
                "imgb64": img_base64
            }
        }
    )

#ToDo meter parametro por url dentro de head() para obtener el top X de los sitios
# Ruta para obtener el análisis del TOP 5 de sitios con más páginas crawleadas con éxito
@app.route("/analisisTopPaginas")
def analisisTopPaginas():
    top_pages = df_site_status[df_site_status['status'] == 'FINISHED'][['abbr', 'pages', 'name']]
    top_pages = top_pages.sort_values(by=['pages'], ascending=False).head()

    # Creamos el gráfico de barras
    plt.figure(figsize=(12, 8))
    ax = top_pages.plot.bar(rot=45, fontsize=14, x='abbr')

    for p in ax.patches:
        ax.annotate(np.round(p.get_height(), decimals=2), (p.get_x() + p.get_width() / 2., p.get_height()), ha='center', va='center', xytext=(0, 10), textcoords='offset points')

    ax.set_ylabel('Nº de páginas')
    ax.set_xlabel('Abreviatura del sitio')

    #Para que no se corten las labels de las imagenes
    plt.tight_layout()

    # Obtener la imagen codificada en Base64
    img_base64 = obtenerImagenBase64(plt)

    # Devolver el gráfico de barras como JSON
    return jsonify(
        {
            "analisisTopPaginasResponse": {
                "imgb64": img_base64,
                "tabla": top_pages.to_dict(orient="records")
            }
        }
    )

# Ruta para realizar el análisis del tiempo que tarda en crawlear los sitios
@app.route("/analisisTiempoCrawleo")
def analisisTiempoCrawleo():
    total_in_status = df_site_status[df_site_status['status'] == 'FINISHED']['duration'].count()
    duration_crawled_sites = df_site_status[df_site_status['status'] == 'FINISHED']['duration']

    # Creamos el histograma del tiempo que tarda en crawlear los sitios
    plt.figure(figsize=(15, 8))
    ax = duration_crawled_sites.hist(bins=200, xlabelsize=18, ylabelsize=18)

    ax.set_xlabel('Tiempo (minutos)', fontsize=18)
    ax.set_ylabel('Número de sitios', fontsize=18)

    # Obtener la imagen codificada en Base64
    img_base64 = obtenerImagenBase64(plt)

    # Devolver el gráfico como JSON
    return jsonify(
        {
            "analisisTiempoCrawleoResponse": {
                "imgb64": img_base64,
            }
        }
    )

# Ruta para realizar el análisis de la relación entre duración y número de páginas
@app.route("/analisisRelacionDuracionPaginas")
def analisisRelacionDuracionPaginas():
    pages_duration = df_site_status[df_site_status['status'] == 'FINISHED'][['pages', 'duration']]

    # Creamos el gráfico de dispersión
    plt.figure(figsize=(15, 8))
    ax = pages_duration.plot.scatter(x='duration', y='pages', facecolors='none', edgecolors='deepskyblue', alpha=0.2, s=100)

    ax.set_xlabel('Tiempo (minutos)')
    ax.set_ylabel('Nº de páginas')

    # Obtener la imagen codificada en Base64
    img_base64 = obtenerImagenBase64(plt)

    # Devolver el gráfico como JSON
    return jsonify(
        {
            "analisisRelacionDuracionPaginasResponse": {
                "imgb64": img_base64,
            }
        }
    )

# Ruta para realizar el análisis de la relación entre duración e intentos de descubrimiento
@app.route("/analisisRelacionDuracionIntentos")
def analisisRelacionDuracionIntentos():
    discovering_duration = df_site_status[df_site_status['status'] == 'FINISHED'][['discovering_tries', 'duration']]

    # Creamos el gráfico de dispersión
    plt.figure(figsize=(15, 8))
    ax = discovering_duration.plot.scatter(x='duration', y='discovering_tries', facecolors='none', edgecolors='deepskyblue', alpha=0.2, s=100)

    ax.set_xlabel('Tiempo (minutos)')
    ax.set_ylabel('Intentos de descubrimiento')

    # Obtener la imagen codificada en Base64
    img_base64 = obtenerImagenBase64(plt)

    # Devolver el gráfico como JSON
    return jsonify(
        {
            "analisisRelacionDuracionIntentosResponse": {
                "imgb64": img_base64,
            }
        }
    )

# Ruta para realizar el análisis de la página principal
@app.route("/analisisPaginaPrincipal")
def analisisPaginaPrincipal():
    words_home = df_sitehomeinfo['words']
    images_home = df_sitehomeinfo['images']
    scripts_home = df_sitehomeinfo['scripts']

    # Crear histograma de palabras, imágenes y scripts en la página principal
    plt.grid()
    plt.hist(words_home, bins=4000, label="Words", hatch='/')
    plt.hist(images_home, bins=4000, label="Images", hatch='.')
    plt.hist(scripts_home, bins=100, label="Scripts", hatch='-')
    plt.legend(loc='upper right')
    plt.xscale("symlog")
    plt.xlabel("Number of words/images/scripts", fontsize=8)
    plt.ylabel("Number of sites", fontsize=8)

    # Obtener la imagen codificada en Base64
    img_base64 = obtenerImagenBase64(plt)

    # Guardar la imagen en un archivo (opcional)
    # plt.savefig('/home/emilio/Documentos/WordsScriptsImages2.svg')

    # Devolver la imagen como JSON
    return jsonify(
        {
            "analisisPaginaPrincipalResponse": {
                "imgb64": img_base64,
            }
        }
    )

# Ruta para realizar el análisis del número de palabras en los sitios
@app.route("/analisisNumeroPalabras")
def analisisNumeroPalabras():
    words_home = df_sitehomeinfo['words']
    plt.figure(figsize=(15, 8))
    ax = words_home.hist(bins=100, xlabelsize=18, ylabelsize=18)

    ax.set_xlabel('Nº de palabras', fontsize=18)
    ax.set_ylabel('Nº de sitios', fontsize=18)

    # Obtener la imagen codificada en Base64
    img_base64 = obtenerImagenBase64(plt)

    # Devolver el gráfico como JSON
    return jsonify(
        {
            "analisisNumeroPalabrasResponse": {
                "imgb64": img_base64,
            }
        }
    )

# Ruta para realizar el análisis de scripts en los sitios
@app.route("/analisisScriptsSitios")
def analisisScriptsSitios():
    scripts_home = df_sitehomeinfo['scripts']
    plt.figure(figsize=(15, 8))
    ax = scripts_home.hist(bins=5, figsize=(15,8), range=[0, 5])

    ax.set_xlabel('Nº de scripts')
    ax.set_ylabel('Nº de sitios')

    # Obtener la imagen codificada en Base64
    img_base64 = obtenerImagenBase64(plt)

    # Devolver el gráfico como JSON
    return jsonify(
        {
            "analisisScriptsSitiosResponse": {
                "imgb64": img_base64,
            }
        }
    )

# Ruta para realizar el análisis del número de imágenes en los sitios
@app.route("/analisisNumeroImagenes")
def analisisNumeroImagenes():
    images_home = df_sitehomeinfo['images']
    plt.figure(figsize=(15, 8))
    ax = images_home.hist(bins=150, figsize=(15,8))
    ax.set_xlabel('Nº de imágenes')
    ax.set_ylabel('Nº de sitios')

    # Obtener la imagen codificada en Base64
    img_base64 = obtenerImagenBase64(plt)

    # Devolver el gráfico como JSON
    return jsonify(
        {
            "analisisNumeroImagenesResponse": {
                "imgb64": img_base64,
            }
        }
    )

# Ruta para realizar el análisis de la conectividad saliente (outgoing)
@app.route("/analisisConectividadSaliente")
def analisisConectividadSaliente():
    outgoing = df_connectivity['outgoing']

    # Obtener valores y porcentajes de conectividad saliente
    outgoing_count = outgoing.value_counts()
    outgoing_count_norm = outgoing.value_counts(normalize=True)
    outgoing_all = pd.concat([outgoing_count, outgoing_count_norm], axis=1)
    outgoing_all.columns = ['Valores', 'Porcentaje']

    # Creamos el histograma de conectividad saliente
    plt.figure(figsize=(15, 8))
    ax = outgoing.hist(bins=250, xlabelsize=18, ylabelsize=18)
    ax.set_xlabel('Nº de outgoing', fontsize=18)
    ax.set_ylabel('Nº de sitios', fontsize=18)

    # Obtener la imagen codificada en Base64
    img_base64 = obtenerImagenBase64(plt)

    # Devolver la tabla de valores y porcentajes y el gráfico como JSON
    return jsonify(
        {
            "analisisConectividadSalienteResponse": {
                "imgb64": img_base64,
                "tabla": outgoing_all.to_dict(orient="index"),
            }
        }
    )

# Ruta para realizar el análisis de enlaces salientes sin contar los que tienen 0 outgoing
@app.route("/analisisEnlacesSalientes")
def analisisEnlacesSalientes():

    outgoing = df_connectivity['outgoing']

    # Obtener valores y porcentajes de conectividad saliente
    outgoing_count = outgoing.value_counts()
    outgoing_count_norm = outgoing.value_counts(normalize=True)
    outgoing_all = pd.concat([outgoing_count, outgoing_count_norm], axis=1)
    outgoing_all.columns = ['Valores', 'Porcentaje']

    outgoing_nozero = df_connectivity[df_connectivity['outgoing'] > 0]['outgoing']

    # Creamos el histograma de enlaces salientes
    plt.figure(figsize=(15, 8))
    ax = outgoing_nozero.hist(bins=250, xlabelsize=18, ylabelsize=18)
    ax.set_xlabel('Nº de enlaces salientes', fontsize=18)
    ax.set_ylabel('Nº de sitios', fontsize=18)

    # Obtener la imagen codificada en Base64
    img_base64 = obtenerImagenBase64(plt)

    # Devolver el gráfico como JSON
    return jsonify(
        {
            "analisisEnlacesSalientesResponse": {
                "imgb64": img_base64,
                "tabla": outgoing_all.to_dict(orient="index"),
            }
        }
    )

#ToDo reciba parametro para sacar el top X
# Ruta para obtener el top 10 de sitios con más conexiones salientes
@app.route("/topSitiosConexionesSalientes")
def topSitiosConexionesSalientes():
    top_outgoing = df_site_conn.sort_values(by=['outgoing'], ascending=False).head(10).reset_index(drop=True)
    
    # Convertir el DataFrame a un diccionario para el formato JSON
    top_outgoing_dict = top_outgoing.to_dict(orient='records')
    
    return jsonify(
        {
            "topSitiosConexionesSalientesResponse": {
                "top_outgoing": top_outgoing_dict
            }
        }
    )

#ToDo reciba parametro para sacar el top X
# Ruta para generar los archivos JSON de nodos y aristas para Gephi (grafo)
@app.route("/generarArchivosJSONGrafo")
def generarArchivosJSONGephi():

    top_outgoing = df_site_conn.sort_values(by=['outgoing'], ascending=False).head(10).reset_index(drop=True)

    # DataFrame df_links y top_outgoing deben estar previamente definidos

    df_links_topoutgoing = pd.DataFrame()

    # Buscamos relaciones entre los 10 sitios tops
    for i in range(0, 10):
        for j in range(0, 10):
            df_links_topoutgoing = pd.concat([df_links_topoutgoing, df_links[(df_links['Target'] == top_outgoing['site'][i]) & (df_links['Source'] == top_outgoing['site'][j])]])

    # Crear listas de nodos y aristas en formato JSON
    nodes_json = top_outgoing[['site', 'abbr']].rename(columns={'site': 'id', 'abbr': 'label'}).to_dict(orient='records')
    edges_json = df_links_topoutgoing.to_dict(orient='records')

    # Devolver el contenido de los archivos JSON como respuesta utilizando jsonify
    return jsonify({
        "topSitiosConexionesSalientesResponse": {
            "nodos": nodes_json,
            "aristas": edges_json
        }
    })

#+++++++++++++++++++++++++++++++++++++++++++ dbutils ++++++++++++++++++++++++++++++++++++++++++++++++++

@app.route('/get_sites', methods=['GET'])
def get_sites():
    # Llamamos a la función get_sites() desde el módulo dbutils.py
    sites_list = dbutils.get_sites()

    # Crear una lista de instancias de la clase SiteData con los datos de los sitios
    sites_data = [
        sites.SiteData(
            id=site.id,
            name=site.name,
            error_tries=site.error_tries,
            discovering_tries=site.discovering_tries,
            pages=site.pages,
            uuid=site.uuid,
            type=str(site.type),
            current_status=str(site.current_status),
            source=str(site.source),
            timestamp=site.timestamp,
            timestamp_s=site.timestamp_s
        ).to_dict() for site in sites_list
    ]
    total_all_source = sites_data['source'].value_counts()
    print(total_all_source)

    # Devuelve los resultados como JSON
    return jsonify(sites_data)


@app.route('/get_site_by_id/<int:s_id>', methods=['GET'])
def get_site_by_id(s_id):
    with db_session:
        # Llamamos a la función get_site_by_id() desde el módulo dbutils.py, pasando el valor de s_id como argumento
        site = dbutils.get_site_by_id(s_id)

        if site is not None:
            # Crear una instancia de la clase SiteData con los datos del sitio
            site_data = sites.SiteData(
                id=site.id,
                name=site.name,
                error_tries=site.error_tries,
                discovering_tries=site.discovering_tries,
                pages=site.pages,
                uuid=site.uuid,
                type=str(site.type),
                current_status=str(site.current_status),
                source=str(site.source),
                timestamp=site.timestamp,
                timestamp_s=site.timestamp_s
            )

            # Devolver los datos del sitio como JSON utilizando el método to_dict
            return jsonify(site_data.to_dict())
        else:
            # Si el sitio no fue encontrado, devuelve un mensaje de error
            return jsonify({"error": "Site not found"}), 404




@app.route('/get_links', methods=['GET'])
def get_links():
    with db_session:
        # Llamamos a la función get_links() desde el módulo dbutils.py
        links_list = dbutils.get_links()

        # Crear una lista de diccionarios con los datos de los enlaces
        links_data = []
        for link in links_list:
            # Convertir los objetos Multiset en listas
            dst_sites = list(link.dst_site)
            src_sites = list(link.src_site)
            
            # Crear diccionarios para los sitios de destino y origen
            dst_site_attributes = {
                "id": dst_sites[0].id if dst_sites else None,
                "name": dst_sites[0].name if dst_sites else None
            }
            src_site_attributes = {
                "id": src_sites[0].id if src_sites else None,
                "name": src_sites[0].name if src_sites else None
            }

            # Agregar los atributos a la lista de enlaces
            links_data.append({
                "id": link.id,
                "dst_site": dst_site_attributes,
                "src_site": src_site_attributes
            })

        # Devuelve los resultados como JSON
        return jsonify(links_data)



@app.route('/get_incoming_links_by_site_id/<int:ts_id>', methods=['GET'])
def get_incoming_links_by_site_id(ts_id):
    with db_session:
        # Llamamos a la función get_incoming_links_by_site_id() desde el módulo dbutils.py, pasando el valor de ts_id como argumento
        incoming_links = dbutils.get_incoming_links_by_site_id(ts_id)

        if incoming_links:
            # Crear una lista de diccionarios con los datos de los enlaces entrantes
            links_data = []
            for link in incoming_links:
                # Convertir los objetos Multiset en listas
                dst_sites = list(link.dst_site)
                src_sites = list(link.src_site)
                
                # Crear diccionarios para los sitios de destino y origen
                dst_site_attributes = {
                    "id": dst_sites[0].id if dst_sites else None,
                    "name": dst_sites[0].name if dst_sites else None
                }
                src_site_attributes = {
                    "id": src_sites[0].id if src_sites else None,
                    "name": src_sites[0].name if src_sites else None
                }

                # Agregar los atributos a la lista de enlaces
                links_data.append({
                    "id_incoming_link": link.id,
                    "dst_site": dst_site_attributes,
                    "src_site": src_site_attributes
                })

            # Devuelve los resultados como JSON
            return jsonify(links_data)
        else:
            # Si el sitio no fue encontrado, devuelve un mensaje de error
            return jsonify({"error": "Site not found"}), 404

@app.route('/get_incoming_links/<path:ts_url>', methods=['GET'], strict_slashes=False)
def get_incoming_links(ts_url):
    # Decodifica la URL para obtener la URL original
    ts_url = unquote(ts_url)

    with db_session:
        # Llamamos a la función get_incoming_links() desde el módulo dbutils.py, pasando la URL como argumento
        incoming_links = dbutils.get_incoming_links(ts_url)

        if incoming_links:
            #for attribute in dir(incoming_links[0]):
            #    print(f"{attribute}: {getattr(incoming_links[0], attribute)}")
                
            # Crear una lista de diccionarios con los datos de los enlaces entrantes
            links_data = []
            for link in incoming_links:
                # Convertir los objetos Multiset en listas
                dst_sites = list(link.dst_site)
                src_sites = list(link.src_site)
                
                # Crear diccionarios para los sitios de destino y origen
                dst_site_attributes = {
                    "id": dst_sites[0].id if dst_sites else None,
                    "name": dst_sites[0].name if dst_sites else None
                }
                src_site_attributes = {
                    "id": src_sites[0].id if src_sites else None,
                    "name": src_sites[0].name if src_sites else None
                }

                # Agregar los atributos a la lista de enlaces
                links_data.append({
                    "id": link.id,
                    "dst_site": dst_site_attributes,
                    "src_site": src_site_attributes
                })

            # Devuelve los resultados como JSON
            return jsonify(links_data)
        else:
            # Si el sitio no fue encontrado, devuelve un mensaje de error
            return jsonify({"error": "Site not found"}), 404
        




if __name__ == '__main__': 
    app.config.from_object(config['development'])
    app.run()

