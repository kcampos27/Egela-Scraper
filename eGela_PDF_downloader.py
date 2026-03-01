import requests
import sys
import getpass
from bs4 import BeautifulSoup


def imprimir_info(metodo, uri, payload, respuesta):
    print(f"\n>>> SOLICITUD: {metodo} {uri}")
    if payload:
        print(f"CONTENIDO: {payload}")

    print(f"<<< RESPUESTA: {respuesta.status_code} {respuesta.reason}")
    if 'Location' in respuesta.headers:
        print(f"Location: {respuesta.headers['Location']}")
    if 'Set-Cookie' in respuesta.headers:
        print(f"Set-Cookie: {respuesta.headers['Set-Cookie']}")


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
        input("Pulsa ENTER para continuar...")
    else:
        print("\n[X] Error: No se ha podido verificar la identidad. Terminando programa.")
        sys.exit(1)


if __name__ == "__main__":
    main()
