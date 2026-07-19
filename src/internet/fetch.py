import requests


HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def download(url):
    """
    Downloads one webpage.
    """

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=10
        )

        response.raise_for_status()

        return response.text

    except Exception:
        return None