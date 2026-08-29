import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

import requests
from feedgen.feed import FeedGenerator
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


SITEMAP = "https://www.acerinox.com/sitemap.xml"
SECCION = "https://www.acerinox.com/es/comunicacion/noticias/"


def crear_titulo(enlace):
    ruta = unquote(urlparse(enlace).path)
    slug = ruta.rstrip("/").split("/")[-1]

    slug = re.sub(r"-\d{5}$", "", slug)
    titulo = slug.replace("-", " ")
    titulo = re.sub(r"\s+", " ", titulo).strip()

    return titulo


sesion = requests.Session()

reintentos = Retry(
    total=4,
    connect=4,
    read=4,
    backoff_factor=5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)

sesion.mount("https://", HTTPAdapter(max_retries=reintentos))

respuesta = sesion.get(
    SITEMAP,
    headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
        )
    },
    timeout=180,
)

respuesta.raise_for_status()

raiz = ET.fromstring(respuesta.content)
espacio = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

noticias = []

for elemento in raiz.findall("sm:url", espacio):
    enlace = elemento.findtext("sm:loc", default="", namespaces=espacio)
    ultima_modificacion = elemento.findtext(
        "sm:lastmod",
        default="",
        namespaces=espacio
    )

    if not enlace.startswith(SECCION):
        continue

    if not ultima_modificacion:
        continue

    if enlace.endswith("/index.html"):
        continue

    if "/ultimas-noticias/" in enlace:
        continue

    slug = urlparse(enlace).path.rstrip("/").split("/")[-1]

    if re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        slug,
        re.IGNORECASE
    ):
        continue

    try:
        fecha = datetime.fromisoformat(
            ultima_modificacion.replace("Z", "+00:00")
        )
    except ValueError:
        continue

    noticias.append({
        "titulo": crear_titulo(enlace),
        "enlace": enlace,
        "fecha": fecha,
    })


noticias.sort(key=lambda noticia: noticia["fecha"], reverse=True)
noticias = noticias[:30]

if not noticias:
    raise RuntimeError(
        "No se encontraron noticias en el sitemap de Acerinox."
    )


feed = FeedGenerator()
feed.id(SECCION)
feed.title("Últimas noticias de Acerinox")
feed.description(
    "Nuevas noticias corporativas publicadas por Acerinox."
)
feed.link(href=SECCION, rel="alternate")
feed.link(href="rss.xml", rel="self")
feed.language("es")
feed.lastBuildDate(datetime.now(timezone.utc))

for noticia in noticias:
    entrada = feed.add_entry()
    entrada.id(noticia["enlace"])
    entrada.title(noticia["titulo"])
    entrada.link(href=noticia["enlace"])
    entrada.pubDate(noticia["fecha"])
    entrada.description(
        f'<p>Noticia publicada en la web oficial de Acerinox.</p>'
        f'<p><a href="{noticia["enlace"]}">'
        f'Leer la noticia completa</a></p>'
    )

feed.rss_file("rss.xml", pretty=True)

print(f"RSS creada con {len(noticias)} noticias de Acerinox")
