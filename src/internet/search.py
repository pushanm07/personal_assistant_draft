try:
    from ddgs import DDGS as SearchClient
except ImportError:  # pragma: no cover - fallback for older environments
    from duckduckgo_search import DDGS as SearchClient


def search(query, max_results=5):
    """
    Returns a list of search result URLs and Titles too.
    """
    urls = []

    with SearchClient() as ddgs:
        results = ddgs.text(query, max_results=max_results)

        for result in results:
            href = result.get("href")

            if href:
                urls.append(href)

    return [{
    "title": result["title"],
    "url": result["href"],
    "snippet": result["body"]
} for result in results] 