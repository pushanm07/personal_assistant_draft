import trafilatura


def clean(html):
    """
    Extract readable article text.
    """

    if not html:
        return None

    extracted = trafilatura.extract(html)

    return extracted