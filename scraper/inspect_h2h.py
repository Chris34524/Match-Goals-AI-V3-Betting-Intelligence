import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ARCHIVO_PARTIDOS = Path("data/partidos_hoy.json")


def cargar_partido():
    with ARCHIVO_PARTIDOS.open(
        encoding="utf-8"
    ) as archivo:
        partidos = json.load(archivo)

    for partido in partidos:
        if (
            "Palmeiras" in partido["local"]
            and "LDU Quito" in partido["visitante"]
        ):
            return partido

    raise RuntimeError(
        "No encontramos Palmeiras vs LDU Quito."
    )


def main():
    partido = cargar_partido()

    print("=" * 70)
    print("INSPECTOR H2H")
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

        page.goto(
            partido["url"],
            wait_until="domcontentloaded",
            timeout=60_000,
        )

        page.wait_for_timeout(5000)

        print("Buscando pestaña H2H...")

        h2h = page.get_by_text(
            "H2H",
            exact=True,
        )

        print(
            f"Elementos H2H encontrados: "
            f"{h2h.count()}"
        )

        if h2h.count() == 0:
            print("No encontramos la pestaña H2H.")
            browser.close()
            return

        print("Haciendo click en H2H...")

        h2h.first.click()

        page.wait_for_timeout(5000)

        print(
            f"URL después del click: "
            f"{page.url}"
        )

        texto = page.locator(
            "body"
        ).inner_text()

        html = page.content()

        ruta_texto = Path(
            "data/h2h_page.txt"
        )

        ruta_html = Path(
            "data/h2h_page.html"
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
        print("TEXTO H2H")
        print("=" * 70)

        print(texto[:20000])

        print("\n" + "=" * 70)
        print("SELECTORES POTENCIALES")
        print("=" * 70)

        selectores = [
            ".h2h",
            ".h2h__section",
            ".h2h__row",
            ".h2h__participant",
            ".h2h__result",
            ".showMore",
            ".event__match",
        ]

        for selector in selectores:
            cantidad = page.locator(
                selector
            ).count()

            print(
                f"{selector:<25} "
                f"{cantidad}"
            )

        print("\nArchivos guardados:")
        print(ruta_texto)
        print(ruta_html)

        browser.close()


if __name__ == "__main__":
    main()