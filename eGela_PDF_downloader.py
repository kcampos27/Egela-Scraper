import os
import bs4
import csv
import re
import requests
import sys
import getpass
from bs4 import BeautifulSoup
import msvcrt

def imprimir_info(metodo, uri, payload, respuesta):
    print(f"\n>>> SOLICITUD: {metodo} {uri}")
    if payload:
        print(f"CONTENIDO: {payload}")

    print(f"<<< RESPUESTA: {respuesta.status_code} {respuesta.reason}")
    if 'Location' in respuesta.headers:
        print(f"Location: {respuesta.headers['Location']}")
    if 'Set-Cookie' in respuesta.headers:
        print(f"Set-Cookie: {respuesta.headers['Set-Cookie']}")

def procesar_carpeta_recursivo(url_carpeta, ruta_local, cabeceras):
    # Petición a la subpágina de la carpeta
    res = requests.request('GET', url_carpeta, headers=cabeceras, allow_redirects=False)
    soup_carpeta = bs4.BeautifulSoup(res.text, 'html.parser')

    # Buscamos los elementos internos
    for enlace in soup_carpeta.find_all('a', href=True, attrs={'class': 'aalink stretched-link'}):
        texto_completo = enlace.find('span').text

        # Split directo por el doble espacio
        partes = texto_completo.split(sep="  ")
        nombre_recurso = partes[0].strip()
        tipo_recurso = partes[-1].strip()  # "Archivo", "Carpeta", etc.

        url_recurso = enlace['href']

        if "Archivo" in tipo_recurso:
            descargar_fichero(url_recurso, ruta_local, cabeceras)

        elif "Carpeta" in tipo_recurso:
            nueva_ruta = os.path.join(ruta_local, nombre_recurso)
            os.makedirs(nueva_ruta, exist_ok=True)
            print(f"      [D] Subcarpeta: {nombre_recurso}")
            # Llamada recursiva
            procesar_carpeta_recursivo(url_recurso, nueva_ruta, cabeceras)


def descargar_fichero(url, ruta_carpeta, cabeceras):
    metodo = 'GET'
    uri_actual = url

    # Bucle para seguir redirecciones manualmente hasta el archivo final
    while True:
        # allow_redirects=False para controlar nosotros el flujo
        res = requests.request(metodo, uri_actual, headers=cabeceras, allow_redirects=False, stream=True)

        # Si hay un nuevo Set-Cookie en cualquier paso, lo actualizamos
        if 'Set-Cookie' in res.headers:
            moodle_cookie = [c for c in res.headers['Set-Cookie'].split(';') if 'MoodleSessionegela' in c][0].strip()
            cabeceras['Cookie'] = moodle_cookie

        # Caso A: Es una redirección (301, 302, 303)
        if res.status_code in [301, 302, 303]:
            uri_actual = res.headers['Location']
            # Si nos manda de vuelta al login, abortamos para no descargar HTML basura
            if "login/index.php" in uri_actual:
                print(f"      [!] Acceso denegado/Sesión expirada para: {url}")
                return
            continue  # Sigue a la nueva ubicación

        # Caso B: Hemos llegado al destino (200 OK)
        elif res.status_code == 200:
            cd = res.headers.get('Content-Disposition')

            if cd and "filename=" in cd:
                # Extraemos el nombre y limpiamos posibles comillas
                nombre_real = re.findall('filename="?(.+?)"?$', cd)[0]

                # REQUISITO: Solo .pdf o .py
                if nombre_real.lower().endswith(('.pdf', '.py')):
                    # Corregir codificación de caracteres especiales (tildes/eñes)
                    try:
                        nombre_real = nombre_real.encode('latin1').decode('utf-8')
                    except:
                        pass

                    path = os.path.join(ruta_carpeta, nombre_real)
                    with open(path, 'wb') as f:
                        for chunk in res.iter_content(chunk_size=8192):
                            f.write(chunk)
                    print(f"      [V] Descargado: {nombre_real}")
                return  # Finaliza tras descargar
            else:
                # Si es 200 pero no hay Content-Disposition, es una página HTML (no un archivo)
                return

        # Caso C: Error de servidor (404, 500, etc.)
        else:
            print(f"      [X] Error {res.status_code} en {uri_actual}")
            return

def main():
    # 1. Validar argumentos de terminal
    if len(sys.argv) != 3:
        print("Uso: python eGela_PDF_downloader.py usuario 'NOMBRE APELLIDO'")
        return

    usuario = sys.argv[1]
    nombre_completo = sys.argv[2]
    password = getpass.getpass(f"Introduce la contraseña para {usuario}: ")

    # --- PRIMERA PETICIÓN (GET inicial) ---
    metodo = 'GET'
    uri = "https://egela.ehu.eus/"
    cabeceras = {'Host': 'egela.ehu.eus'}

    res1 = requests.request(metodo, uri, headers=cabeceras, allow_redirects=False)
    imprimir_info(metodo, uri, None, res1)

    # Extraer solo la parte MoodleSessionegela=...
    # Buscamos en el header Set-Cookie la parte que nos interesa
    cookie_header = res1.headers.get('Set-Cookie', '')
    # Filtramos para quedarnos solo con el ID de sesión
    moodle_cookie = [c for c in cookie_header.split(';') if 'MoodleSessionegela' in c][0].strip()

    # --- SEGUNDA PETICIÓN (Ir al Location del login) ---
    uri2 = res1.headers['Location']
    cabeceras['Cookie'] = moodle_cookie

    res2 = requests.request(metodo, uri2, headers=cabeceras, allow_redirects=False)
    imprimir_info(metodo, uri2, None, res2)

    # Parsear el logintoken del HTML
    soup = BeautifulSoup(res2.text, 'html.parser')
    login_token = soup.find('input', attrs={'name': 'logintoken'})['value']

    # --- TERCERA PETICIÓN (POST de Login) ---
    metodo_post = 'POST'
    # La URI suele ser la misma que la del formulario o el Location anterior
    payload = {
        'anchor': '',
        'logintoken': login_token,
        'username': usuario,
        'password': password
    }

    res3 = requests.request(metodo_post, uri2, headers=cabeceras, data=payload, allow_redirects=False)
    imprimir_info(metodo_post, uri2, payload, res3)

    # Si hay un nuevo Set-Cookie tras el login, lo actualizamos
    if 'Set-Cookie' in res3.headers:
        moodle_cookie = [c for c in res3.headers['Set-Cookie'].split(';') if 'MoodleSessionegela' in c][0].strip()
        cabeceras['Cookie'] = moodle_cookie

    # --- CUARTA PETICIÓN (Verificar Perfil) ---
    # Según la pista, accedemos al perfil para comprobar el nombre
    uri4 = "https://egela.ehu.eus/user/profile.php"
    res4 = requests.request(metodo, uri4, headers=cabeceras, allow_redirects=False)
    imprimir_info(metodo, uri4, None, res4)

    # Comprobación final
    if nombre_completo in res4.text:
        print(f"\n[!] Autenticación correcta. Bienvenido {nombre_completo}.")
        print("Pulsa cualquier tecla para continuar...")
        msvcrt.getch()
    else:
        print("\n[X] Error: No se ha podido verificar la identidad. Terminando programa.")
        sys.exit(1)

    # Creamos el CSV único para todas las tareas
    csv_file = open('tareas.csv', mode='w', newline='', encoding='utf-8')
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(['Tarea', 'Fecha Entrega', 'Enlace'])

    # --- QUINTA PETICIÓN (Página de la Asignatura) ---
    soup4 = BeautifulSoup(res4.text, 'html.parser')

    # 1. Buscar el enlace de la asignatura
    asignatura_target = "Sistemas Web"
    enlace_asignatura = soup4.find('a', string=lambda t: t and asignatura_target in t)

    if not enlace_asignatura:
        print(f"[X] No se encontró la asignatura: {asignatura_target}")
        sys.exit(1)

    uri5 = enlace_asignatura['href']
    metodo = 'GET'

    res5 = requests.request(metodo, uri5, headers=cabeceras, allow_redirects=False)
    imprimir_info(metodo, uri5, None, res5)

    # --- Identificar Pestañas/Temas ---
    soup5 = BeautifulSoup(res5.text, 'html.parser')

    # En Moodle (eGela), las pestañas suelen estar en una lista con la clase 'nav-tabs'
    # o dentro de elementos con roles de tab.
    print(f"\n[+] Identificando secciones/pestañas en {asignatura_target}:")

    # Buscamos los enlaces que representan las pestañas de los temas
    pestanas = soup5.find_all('li', class_='nav-item')  # Estructura común en Moodle moderno

    temas_encontrados = []
    for p in pestanas:
        link = p.find('a', class_='nav-link')
        if link and link.get('title'):
            nombre_tema = link.get('title')
            url_tema = link.get('href')
            temas_encontrados.append((nombre_tema, url_tema))
            print(f" - Tema: {nombre_tema} | URI: {url_tema}")

    if not temas_encontrados:
        # Intento alternativo por si usa el formato de secciones en lista única
        print("[!] No se detectaron pestañas nav-item, buscando secciones de curso...")
        secciones = soup5.select('li.section.main')
        for s in secciones:
            nombre = s.get('aria-label')
            if nombre:
                print(f" - Sección: {nombre}")

    print("Obteniendo archivos por cada pestaña...")
    for nombre_tema, url_tema in temas_encontrados:
        os.makedirs(nombre_tema, exist_ok=True)
        doc_tema = requests.request('GET', url_tema, headers=cabeceras, allow_redirects=False)
        soup_tema = bs4.BeautifulSoup(doc_tema.text, 'html.parser')
        print(f"\n[+] Archivos de {nombre_tema}:")
        for enlace in soup_tema.find_all('a', href=True, attrs={'class': 'aalink stretched-link'}):
            fichero = enlace.find('span').text
            nombre_fichero = fichero.split(sep="  ")[0]
            tipo_fichero = fichero.split(sep="  ")[-1]
            url_fichero = enlace['href']
            if "Archivo" in tipo_fichero:
                descargar_fichero(url_fichero, nombre_tema, cabeceras)
            elif "Carpeta" in tipo_fichero:
                print(f" - Carpeta: {nombre_fichero}")
                procesar_carpeta_recursivo(url_fichero, nombre_tema, cabeceras)
            elif "Tarea" in tipo_fichero:
                csv_writer.writerow([nombre_fichero, '', url_fichero])

if __name__ == "__main__":
    main()
