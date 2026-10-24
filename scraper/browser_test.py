from pathlib import Path

from playwright.sync_api import sync_playwright


URL = "https://www.flashscore.com.mx/"


def main():
    print("=" * 60)
    print("PRUEBA DE NAVEGADOR - FLASHSCORE")
    print("=" * 60)

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

        print(f"\nAbriendo: {URL}")

        response = page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60_000,
        )

        if response:
            print(f"HTTP status: {response.status}")
        else:
            print("No se obtuvo objeto response.")

        print("\nEsperando ejecución de JavaScript...")

        page.wait_for_timeout(8000)

        print(f"Título: {page.title()}")

        html = page.content()

        print(
            f"HTML renderizado: "
            f"{len(html):,} caracteres"
        )

        ruta = Path("data/flashscore_rendered.html")

        ruta.write_text(
            html,
            encoding="utf-8",
        )

        print(f"Guardado en: {ruta}")

        selectors = [
            ".event__match",
            ".event__participant",
            ".event__participant--home",
            ".event__participant--away",
        ]

        print("\n--- SELECTORES ---")

        for selector in selectors:
            cantidad = page.locator(selector).count()

            print(
                f"{selector:<30} "
                f"{cantidad}"
            )

        print("\n--- TEXTO DE LA PÁGINA ---")

        body_text = page.locator("body").inner_text()

        print(body_text[:3000])

        browser.close()


if __name__ == "__main__":
    main()