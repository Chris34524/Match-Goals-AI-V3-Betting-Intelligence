from urllib.parse import urljoin
import requests

SITES = {
    "PLAYDOIT": "https://www.playdoit.mx/",
    "BETMEXICO": "https://betmexico.mx/",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 MatchGoalsAI/1.0 "
        "(public-access compatibility check)"
    )
}

TIMEOUT = 20


def check_url(name, url):
    print()
    print("=" * 90)
    print(name)
    print(url)
    print("=" * 90)

    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True,
        )

        text = r.text or ""

        print("STATUS:", r.status_code)
        print("FINAL :", r.url)
        print("BYTES :", len(r.content))

        low = text.lower()

        print(
            "REQUIERE JS:",
            (
                "enable javascript" in low
                or "active javascript" in low
                or "javascript para utilizar" in low
                or "javascript enabled" in low
            ),
        )

        for palabra in (
            "fútbol",
            "futbol",
            "deportes",
            "momio",
            "cuota",
            "odds",
            "over",
            "under",
        ):
            if palabra in low:
                print(
                    "TEXTO DETECTADO:",
                    palabra,
                )

    except Exception as e:
        print(
            "ERROR:",
            type(e).__name__,
            str(e),
        )


def check_robots(name, base):
    url = urljoin(
        base,
        "/robots.txt",
    )

    print()
    print("-" * 90)
    print(name, "ROBOTS")
    print(url)
    print("-" * 90)

    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True,
        )

        print("STATUS:", r.status_code)
        print("CONTENT-TYPE:", r.headers.get("content-type"))

        if r.status_code == 200:
            print()
            print(r.text[:6000])
        else:
            print(
                "robots.txt no recuperado."
            )

    except Exception as e:
        print(
            "ERROR:",
            type(e).__name__,
            str(e),
        )


def main():
    for name, base in SITES.items():
        check_robots(
            name,
            base,
        )

        check_url(
            name + " HOME",
            base,
        )

    check_url(
        "PLAYDOIT REGLAS",
        "https://www.playdoit.mx/reglasDeJuego",
    )

    check_url(
        "BETMEXICO DEPORTES",
        "https://betmexico.mx/deportes",
    )


if __name__ == "__main__":
    main()
