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
    print("INSPECTOR DE FILAS DE CLASIFICACIÓN")
    print("=" * 70)

    print(
        f"\n{partido['local']} "
        f"vs {partido['visitante']}"
    )

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

        page.goto(
            partido["url"],
            wait_until="domcontentloaded",
            timeout=60_000,
        )

        page.wait_for_timeout(5000)

        tablas = page.locator(".ui-table")

        print(
            f"\nTablas encontradas: "
            f"{tablas.count()}"
        )

        if tablas.count() == 0:
            raise RuntimeError(
                "No encontramos .ui-table"
            )

        tabla = tablas.first

        filas = tabla.locator(
            ".ui-table__row"
        )

        print(
            f"Filas encontradas: "
            f"{filas.count()}"
        )

        salida = []

        # Solo necesitamos inspeccionar
        # las primeras tres filas.
        limite = min(
            3,
            filas.count(),
        )

        for i in range(limite):
            fila = filas.nth(i)

            texto = fila.inner_text()

            html = fila.evaluate(
                "(element) => element.outerHTML"
            )

            salida.append(
                f"\n{'=' * 70}\n"
                f"FILA {i + 1}\n"
                f"{'=' * 70}\n"
                f"\nTEXTO:\n"
                f"{texto}\n"
                f"\nHTML:\n"
                f"{html}\n"
            )

            print(
                f"\nFila {i + 1}:"
            )

            print(texto)

        ruta = Path(
            "data/standings_rows.txt"
        )

        ruta.write_text(
            "\n".join(salida),
            encoding="utf-8",
        )

        print(
            f"\nGuardado en: {ruta}"
        )

        browser.close()


if __name__ == "__main__":
    main()