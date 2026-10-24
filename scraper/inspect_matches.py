from pathlib import Path

from playwright.sync_api import sync_playwright


URL = "https://www.flashscore.com.mx/"


def main():
    print("=" * 70)
    print("INSPECTOR DE ESTRUCTURA DE PARTIDOS")
    print("=" * 70)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            viewport={
                "width": 1920,
                "height": 1080,
            },
            locale="es-MX",
        )

        print(f"\nAbriendo: {URL}")

        response = page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60_000,
        )

        if response:
            print(f"HTTP: {response.status}")

        print("Esperando contenido dinámico...")

        try:
            page.wait_for_selector(
                ".event__match",
                timeout=20_000,
            )
        except Exception:
            print("No apareció .event__match")
            browser.close()
            return

        partidos = page.locator(".event__match")

        cantidad = partidos.count()

        print(f"\nPartidos encontrados: {cantidad}")

        limite = min(cantidad, 5)

        salida = []

        for i in range(limite):
            partido = partidos.nth(i)

            print("\n" + "=" * 70)
            print(f"PARTIDO #{i + 1}")
            print("=" * 70)

            try:
                texto = partido.inner_text()
            except Exception as error:
                texto = f"ERROR: {error}"

            print("\nTEXTO:")
            print(texto)

            try:
                html = partido.evaluate(
                    "(element) => element.outerHTML"
                )
            except Exception as error:
                html = f"ERROR: {error}"

            print("\nHTML:")
            print(html)

            salida.append(
                f"""
============================================================
PARTIDO #{i + 1}
============================================================

TEXTO:
{texto}

HTML:
{html}

"""
            )

        ruta = Path("data/inspect_matches.txt")

        ruta.write_text(
            "\n".join(salida),
            encoding="utf-8",
        )

        print("\n" + "=" * 70)
        print(f"Resultado guardado en: {ruta}")
        print("=" * 70)

        browser.close()


if __name__ == "__main__":
    main()