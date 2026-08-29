from datetime import datetime, timezone
from html import escape
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


URL = "https://www.acerinox.com/es/comunicacion/noticias/ultimas-noticias/"

MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def convertir_fecha(texto):
    partes = texto.lower().strip().split()

    if len(partes) != 3:
        return datetime.now(timezone.utc)

    dia = int(partes[0])
    mes = MESES[partes[1]]
    anio = int(partes[2])

    return datetime(anio, mes, dia, 8, 0, tzinfo=timezone.utc)


sesion = requests.Session()

reintentos = Retry(
    total=3,
    connect=3,
    read=3,
    backoff_factor=5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)

sesion.mount("https://", HTTPAdapter(max_retries=reintentos))

respuesta = sesion.get(
    URL,
    headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
        )
    },
    timeout=120,
)

respuesta.raise_for_status()
soup = BeautifulSoup(respuesta.text, "html.parser")

noticias = []

for elemento in soup.select("ul.listado > li"):
    titulo_elemento = elemento.select_one(".titulo_elemento")
    enlace_elemento = elemento.select_one("a.enlace_elemento")
    fecha_elemento = elemento.select_one(".fecha_elemento span")
    descripcion_elemento = elemento.select_one(".descripcion")
    imagen_elemento = elemento.select_one(".imagen_elemento img")

    if not titulo_elemento or not enlace_elemento:
        continue

    titulo = titulo_elemento.get_text(" ", strip=True)
    enlace = urljoin(URL, enlace_elemento.get("href", ""))
    fecha_texto = (
        fecha_elemento.get_text(" ", strip=True)
        if fecha_elemento
        else ""
    )
    descripcion = (
        descripcion_elemento.get_text(" ", strip=True)
        if descripcion_elemento
        else ""
    )
    imagen = (
        urljoin(URL, imagen_elemento.get("src", ""))
        if imagen_elemento
        else ""
    )

    noticias.append({
        "titulo": titulo,
        "enlace": enlace,
        "fecha": convertir_fecha(fecha_texto),
        "fecha_texto": fecha_texto,
        "descripcion": descripcion,
        "imagen": imagen,
    })


if not noticias:
    raise RuntimeError(
        "No se encontraron noticias. Acerinox podría haber cambiado la página."
    )


feed = FeedGenerator()
feed.id(URL)
feed.title("Últimas noticias de Acerinox")
feed.description(
    "Noticias corporativas publicadas en la web oficial de Acerinox."
)
feed.link(href=URL, rel="alternate")
feed.link(href="rss.xml", rel="self")
feed.language("es")
feed.lastBuildDate(datetime.now(timezone.utc))

for noticia in noticias:
    entrada = feed.add_entry()
    entrada.id(noticia["enlace"])
    entrada.title(noticia["titulo"])
    entrada.link(href=noticia["enlace"])
    entrada.pubDate(noticia["fecha"])

    contenido = (
        f'<p><b>Fecha:</b> {escape(noticia["fecha_texto"])}</p>'
        f'<p>{escape(noticia["descripcion"])}</p>'
    )

    if noticia["imagen"]:
        contenido += (
            f'<p><img src="{escape(noticia["imagen"])}" '
            f'alt="{escape(noticia["titulo"])}"></p>'
        )

    contenido += (
        f'<p><a href="{escape(noticia["enlace"])}">'
        f'Leer la noticia en Acerinox</a></p>'
    )

    entrada.description(contenido)

feed.rss_file("rss.xml", pretty=True)

print(f"RSS creada con {len(noticias)} noticias de Acerinox")
