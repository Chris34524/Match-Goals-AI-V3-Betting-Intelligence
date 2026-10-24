import asyncio
import re
from pathlib import Path

from playwright.async_api import async_playwright


URL = "https://betmexico.mx/deportes"

OUT_HTML = Path("/tmp/betmexico_rendered.html")
OUT_TEXT = Path("/tmp/betmexico_rendered.txt")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True
        )

        page = await browser.new_page(
            viewport={
                "width": 1440,
                "height": 1000,
            }
        )

        print("=" * 80)
        print("BETMEXICO — PRUEBA PÚBLICA")
        print("=" * 80)
        print("URL:", URL)

        try:
            response = await page.goto(
                URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            if response:
                print(
                    "HTTP:",
                    response.status,
                )

            # Sólo esperamos a que el JS público renderice.
            # No login, no clicks, no captcha, no evasión.
            await page.wait_for_timeout(
                10000
            )

            html = await page.content()

            text = await page.locator(
                "body"
            ).inner_text()

            OUT_HTML.write_text(
                html,
                encoding="utf-8",
            )

            OUT_TEXT.write_text(
                text,
                encoding="utf-8",
            )

            low = text.lower()

            print()
            print("CARACTERES HTML:", len(html))
            print("CARACTERES TEXTO:", len(text))

            print()
            print("PALABRAS DETECTADAS:")

            for term in (
                "fútbol",
                "futbol",
                "más de",
                "menos de",
                "ambos equipos",
                "empate",
                "local",
                "visitante",
            ):
                print(
                    f"{term:20}",
                    low.count(term),
                )

            # Sólo diagnóstico de posibles cuotas decimales.
            posibles = re.findall(
                r"(?<!\d)(1\.\d{2}|[2-9]\.\d{2})(?!\d)",
                text,
            )

            print()
            print(
                "POSIBLES CUOTAS DECIMALES:",
                len(posibles),
            )

            print(
                "MUESTRA:",
                posibles[:30],
            )

            print()
            print("=" * 80)
            print("PRIMERAS LÍNEAS VISIBLES")
            print("=" * 80)

            lineas = [
                x.strip()
                for x in text.splitlines()
                if x.strip()
            ]

            for linea in lineas[:150]:
                print(linea)

            print()
            print("=" * 80)
            print("ARCHIVOS")
            print("=" * 80)
            print(OUT_TEXT)
            print(OUT_HTML)

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
