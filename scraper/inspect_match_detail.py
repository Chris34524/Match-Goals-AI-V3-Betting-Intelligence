import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ARCHIVO_PARTIDOS = Path("data/partidos_hoy.json")


def cargar_partido():
    with ARCHIVO_PARTIDOS.open(
        encoding="utf-8"
    ) as archivo:
        partidos = json.load(archivo)

    # Buscamos primero Palmeiras vs LDU Quito.
    for partido in partidos:
        if (
            "Palmeiras" in partido["local"]
            and "LDU Quito" in partido["visitante"]
        ):
            return partido

    # Si ese partido ya no estuviera disponible,
    # usamos el primer partido que tenga URL.
    for partido in partidos:
        if partido.get("url"):
            return partido

    raise RuntimeError(
        "No encontramos un partido con URL."
    )


def main():
    partido = cargar_partido()

    print("=" * 70)
    print("INSPECCIÓN DEL DETALLE DE UN PARTIDO")
    print("=" * 70)

    print(
        f"\nPartido: "
        f"{partido['local']} vs "
        f"{partido['visitante']}"
    )

    print(f"ID: {partido['id']}")
    print(f"URL: {partido['url']}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1920,
                "height": 1080,
            },
            locale="es-MX",
        )

        print("\nAbriendo página del partido...")

        response = page.goto(
            partido["url"],
            wait_until="domcontentloaded",
            timeout=60_000,
        )

        if response:
            print(f"HTTP: {response.status}")

        print("Esperando contenido dinámico...")

        page.wait_for_timeout(8000)

        print(f"Título: {page.title()}")

        html = page.content()

        ruta_html = Path(
            "data/match_detail.html"
        )

        ruta_html.write_text(
            html,
            encoding="utf-8",
        )

        print(
            f"HTML: {len(html):,} caracteres"
        )

        print("\n" + "=" * 70)
        print("TEXTO VISIBLE")
        print("=" * 70)

        texto = page.locator("body").inner_text()

        print(texto[:15000])

        ruta_texto = Path(
            "data/match_detail.txt"
        )

        ruta_texto.write_text(
            texto,
            encoding="utf-8",
        )

        print("\n" + "=" * 70)
        print("BÚSQUEDA DE PALABRAS")
        print("=" * 70)

        palabras = [
            "H2H",
            "Últimos partidos",
            "Clasificación",
            "Forma",
            "Enfrentamientos",
            "Tabla",
            "Palmeiras",
            "LDU Quito",
        ]

        texto_lower = texto.lower()

        for palabra in palabras:
            cantidad = texto_lower.count(
                palabra.lower()
            )

            print(
                f"{palabra:<25} "
                f"{cantidad}"
            )

        print("\nArchivos guardados:")
        print(ruta_html)
        print(ruta_texto)

        browser.close()


if __name__ == "__main__":
    main()