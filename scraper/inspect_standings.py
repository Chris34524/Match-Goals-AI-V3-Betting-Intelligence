import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ARCHIVO_PARTIDOS = Path("data/partidos_hoy.json")


def cargar_partido():
    with ARCHIVO_PARTIDOS.open(
        encoding="utf-8"
    ) as archivo:
        partidos = json.load(archivo)

    # Usamos un partido de liga como laboratorio.
    for partido in partidos:
        if (
            "Chicago Fire" in partido["local"]
            and "Inter Miami" in partido["visitante"]
        ):
            return partido

    raise RuntimeError(
        "No encontramos Chicago Fire vs Inter Miami."
    )


def main():
    partido = cargar_partido()

    print("=" * 70)
    print("INSPECTOR DE CLASIFICACIÓN")
    print("=" * 70)

    print(
        f"\n{partido['local']} "
        f"vs {partido['visitante']}"
    )

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

        print("\nAbriendo partido...")

        response = page.goto(
            partido["url"],
            wait_until="domcontentloaded",
            timeout=60_000,
        )

        if response:
            print(f"HTTP: {response.status}")

        page.wait_for_timeout(5000)

        print(f"Título: {page.title()}")

        print("\nBuscando posibles pestañas...")

        nombres = [
            "CLASIFICACIÓN",
            "CLASIFICACION",
            "TABLA",
            "POSICIONES",
        ]

        encontrado = None

        for nombre in nombres:
            elementos = page.get_by_text(
                nombre,
                exact=True,
            )

            print(
                f"{nombre:<20} "
                f"{elementos.count()}"
            )

            if (
                encontrado is None
                and elementos.count() > 0
            ):
                encontrado = elementos.first

        if encontrado is not None:
            print(
                "\nAbriendo pestaña de clasificación..."
            )

            encontrado.click()

            page.wait_for_timeout(4000)

            print(
                f"URL después del click: "
                f"{page.url}"
            )

        else:
            print(
                "\nNo encontramos una pestaña "
                "de clasificación exacta."
            )

        texto = page.locator(
            "body"
        ).inner_text()

        html = page.content()

        ruta_texto = Path(
            "data/standings_page.txt"
        )

        ruta_html = Path(
            "data/standings_page.html"
        )

        ruta_texto.write_text(
            texto,
            encoding="utf-8",
        )

        ruta_html.write_text(
            html,
            encoding="utf-8",
        )

        print("\n" + "=" * 70)
        print("SELECTORES POTENCIALES")
        print("=" * 70)

        selectores = [
            ".ui-table",
            ".ui-table__row",
            ".tableWrapper",
            ".table__row",
            ".tableCellParticipant",
            "[data-testid*='stand']",
            "[class*='standings']",
            "[class*='table']",
        ]

        for selector in selectores:
            try:
                cantidad = page.locator(
                    selector
                ).count()
            except Exception:
                cantidad = -1

            print(
                f"{selector:<35} "
                f"{cantidad}"
            )

        print("\n" + "=" * 70)
        print("TEXTO VISIBLE")
        print("=" * 70)

        print(texto[:20000])

        print("\nArchivos guardados:")
        print(ruta_texto)
        print(ruta_html)

        browser.close()


if __name__ == "__main__":
    main()