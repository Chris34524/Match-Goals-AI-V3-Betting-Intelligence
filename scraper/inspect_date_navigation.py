import re
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright


URL = "https://www.flashscore.com.mx/"


def main():
    hoy = date.today()

    texto_fecha = hoy.strftime("%d/%m")

    print("=" * 70)
    print("INSPECTOR DE NAVEGACIÓN POR FECHA")
    print("=" * 70)

    print(f"Fecha sistema: {hoy.isoformat()}")
    print(f"Buscando texto: {texto_fecha}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
        )

        page = browser.new_page(
            viewport={
                "width": 1920,
                "height": 1080,
            },
            locale="es-MX",
        )

        response = page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60_000,
        )

        if response:
            print(
                f"HTTP: {response.status}"
            )

        page.wait_for_selector(
            ".event__match",
            timeout=30_000,
        )

        page.wait_for_timeout(5000)

        print(
            f"Partidos visibles: "
            f"{page.locator('.event__match').count()}"
        )

        print("\n" + "=" * 70)
        print("TEXTOS QUE CONTIENEN LA FECHA")
        print("=" * 70)

        candidatos = page.get_by_text(
            re.compile(
                re.escape(texto_fecha),
                re.IGNORECASE,
            )
        )

        print(
            f"Candidatos encontrados: "
            f"{candidatos.count()}"
        )

        salida = []

        for i in range(
            min(candidatos.count(), 10)
        ):
            candidato = candidatos.nth(i)

            try:
                if not candidato.is_visible():
                    continue

                texto = candidato.inner_text().strip()

                html = candidato.evaluate(
                    "(e) => e.outerHTML"
                )

                salida.append(
                    "\n"
                    + "=" * 70
                    + f"\nCANDIDATO {i + 1}\n"
                    + "=" * 70
                    + f"\nTEXTO:\n{texto}\n"
                    + f"\nHTML:\n{html}\n"
                )

                print(
                    f"\nCandidato {i + 1}: "
                    f"{texto}"
                )

                # Buscamos ancestros porque normalmente
                # las flechas y la fecha viven dentro
                # del mismo contenedor.
                ancestros = candidato.evaluate(
                    """
                    (el) => {
                        const resultado = [];
                        let actual = el;

                        for (
                            let i = 0;
                            i < 6 && actual;
                            i++
                        ) {
                            resultado.push({
                                nivel: i,
                                tag: actual.tagName,
                                clase: actual.className,
                                html: actual.outerHTML
                            });

                            actual = actual.parentElement;
                        }

                        return resultado;
                    }
                    """
                )

                for ancestro in ancestros:
                    salida.append(
                        "\n"
                        + "-" * 70
                        + f"\nANCESTRO NIVEL "
                        + f"{ancestro['nivel']}\n"
                        + "-" * 70
                        + f"\nTAG: "
                        + f"{ancestro['tag']}\n"
                        + f"CLASE: "
                        + f"{ancestro['clase']}\n"
                        + f"HTML:\n"
                        + f"{ancestro['html']}\n"
                    )

            except Exception as error:
                salida.append(
                    f"\nERROR candidato "
                    f"{i + 1}: {error}\n"
                )

        print("\n" + "=" * 70)
        print("BOTONES VISIBLES")
        print("=" * 70)

        botones = page.locator(
            "button"
        )

        print(
            f"Botones totales: "
            f"{botones.count()}"
        )

        for i in range(
            botones.count()
        ):
            boton = botones.nth(i)

            try:
                if not boton.is_visible():
                    continue

                texto = (
                    boton.inner_text()
                    .strip()
                )

                aria = boton.get_attribute(
                    "aria-label"
                )

                titulo = boton.get_attribute(
                    "title"
                )

                clase = boton.get_attribute(
                    "class"
                )

                if (
                    texto
                    or aria
                    or titulo
                ):
                    salida.append(
                        "\n"
                        + "-" * 70
                        + f"\nBOTÓN {i + 1}\n"
                        + "-" * 70
                        + f"\nTEXTO: {texto}\n"
                        + f"ARIA: {aria}\n"
                        + f"TITLE: {titulo}\n"
                        + f"CLASS: {clase}\n"
                        + "HTML:\n"
                        + boton.evaluate(
                            "(e) => e.outerHTML"
                        )
                        + "\n"
                    )

            except Exception:
                continue

        ruta = Path(
            "data/date_navigation_inspect.txt"
        )

        ruta.write_text(
            "\n".join(salida),
            encoding="utf-8",
        )

        print(
            f"\nInspector guardado en: "
            f"{ruta}"
        )

        browser.close()


if __name__ == "__main__":
    main()
