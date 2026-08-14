import json
import re
from datetime import datetime, timezone

import feedparser
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


SOURCES_FILE = "sources.json"
OUTPUT_FILE = "news.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; YanesAggregator/1.0)"
}


def load_sources():
    with open(SOURCES_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def clean_text(text):
    if not text:
        return ""

    text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ==========================================
# RSS
# ==========================================

def get_image(entry):

    if hasattr(entry, "media_content"):
        for media in entry.media_content:
            url = media.get("url")

            if url:
                return url

    if hasattr(entry, "media_thumbnail"):
        for media in entry.media_thumbnail:
            url = media.get("url")

            if url:
                return url

    if hasattr(entry, "enclosures"):
        for enclosure in entry.enclosures:

            url = enclosure.get("href") or enclosure.get("url")
            content_type = enclosure.get("type", "")

            if url and "image" in content_type:
                return url

    html = entry.get("summary", "")

    match = re.search(
        r'<img[^>]+src=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE
    )

    if match:
        return match.group(1)

    return ""


def get_date(entry):

    return (
        entry.get("published")
        or entry.get("updated")
        or ""
    )


def parse_rss(source, category):

    print(f"RSS: {source['name']}")

    feed = feedparser.parse(source["url"])

    items = []

    for entry in feed.entries[:15]:

        items.append({
            "category": category,
            "source": source["name"],
            "title": clean_text(
                entry.get("title", "Без наслов")
            ),
            "description": clean_text(
                entry.get("summary", "")
            )[:300],
            "url": entry.get("link", ""),
            "image": get_image(entry),
            "date": get_date(entry)
        })

    return items


# ==========================================
# WEBSITE SCRAPER
# ==========================================

def scrape_ohridnews():

    print("Scraping: OhridNews")

    url = "https://www.ohridnews.com/"

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        items = []

        # Look for article links
        for link in soup.find_all("a", href=True):

            title = clean_text(link.get_text(" ", strip=True))

            href = link.get("href")

            if not title or not href:
                continue

            # Ignore very short navigation links
            if len(title) < 20:
                continue

            article_url = urljoin(url, href)

            # Try to find image near the link
            image = ""

            parent = link

            for _ in range(3):

                if parent:

                    img = parent.find("img")

                    if img:

                        image = (
                            img.get("src")
                            or img.get("data-src")
                            or ""
                        )

                        if image:
                            image = urljoin(
                                url,
                                image
                            )

                        break

                    parent = parent.parent

            items.append({
                "category": "mkd",
                "source": "OhridNews",
                "title": title,
                "description": "",
                "url": article_url,
                "image": image,
                "date": ""
            })

            if len(items) >= 15:
                break

        return items

    except Exception as error:

        print(
            f"OhridNews error: {error}"
        )

        return []


def scrape_smartportal():

    print("Scraping: SmartPortal")

    url = "https://smartportal.mk/"

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        items = []

        # WordPress sites commonly use article headings
        for article in soup.select(
            "article, .post, .td_module_wrap"
        ):

            link = article.find(
                "a",
                href=True
            )

            if not link:
                continue

            title_element = (
                article.find("h1")
                or article.find("h2")
                or article.find("h3")
            )

            if not title_element:
                continue

            title = clean_text(
                title_element.get_text()
            )

            article_url = link.get("href")

            image = ""

            img = article.find("img")

            if img:

                image = (
                    img.get("src")
                    or img.get("data-src")
                    or ""
                )

                image = urljoin(
                    url,
                    image
                )

            if title and article_url:

                items.append({
                    "category": "mkd",
                    "source": "SmartPortal",
                    "title": title,
                    "description": "",
                    "url": article_url,
                    "image": image,
                    "date": ""
                })

            if len(items) >= 15:
                break

        return items

    except Exception as error:

        print(
            f"SmartPortal error: {error}"
        )

        return []


def scrape_tarnkappe(source):

    print("Scraping: Tarnkappe")

    try:

        response = requests.get(
            source["url"],
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        items = []

        for article in soup.select(
            "article"
        ):

            link = article.find(
                "a",
                href=True
            )

            title_element = (
                article.find("h2")
                or article.find("h3")
                or article.find("h1")
            )

            if not link or not title_element:
                continue

            title = clean_text(
                title_element.get_text()
            )

            article_url = urljoin(
                source["url"],
                link.get("href")
            )

            image = ""

            img = article.find("img")

            if img:

                image = (
                    img.get("src")
                    or img.get("data-src")
                    or ""
                )

                image = urljoin(
                    source["url"],
                    image
                )

            items.append({
                "category": "de",
                "source": source["name"],
                "title": title,
                "description": "",
                "url": article_url,
                "image": image,
                "date": ""
            })

            if len(items) >= 15:
                break

        return items

    except Exception as error:

        print(
            f"Tarnkappe error: {error}"
        )

        return []


# ==========================================
# YOUTUBE
# ==========================================

def get_youtube_channel_id(channel_url):

    response = requests.get(
        channel_url,
        headers=HEADERS,
        timeout=20
    )

    response.raise_for_status()

    html = response.text

    patterns = [
        r'"channelId":"(UC[^"]+)"',
        r'"externalId":"(UC[^"]+)"',
        r'<meta itemprop="channelId" content="(UC[^"]+)"'
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html
        )

        if match:
            return match.group(1)

    return None


def parse_youtube(source):

    print(
        f"YouTube: {source['name']}"
    )

    try:

        channel_id = get_youtube_channel_id(
            source["url"]
        )

        if not channel_id:

            print(
                f"Channel ID not found: "
                f"{source['name']}"
            )

            return []

        feed_url = (
            "https://www.youtube.com/feeds/videos.xml?"
            f"channel_id={channel_id}"
        )

        feed = feedparser.parse(
            feed_url
        )

        items = []

        for entry in feed.entries[:10]:

            video_id = entry.get(
                "yt_videoid"
            )

            image = ""

            if video_id:

                image = (
                    "https://i.ytimg.com/vi/"
                    f"{video_id}/hqdefault.jpg"
                )

            items.append({
                "category": "youtube",
                "source": source["name"],
                "title": clean_text(
                    entry.get(
                        "title",
                        "Без наслов"
                    )
                ),
                "description": "",
                "url": entry.get(
                    "link",
                    ""
                ),
                "image": image,
                "date": entry.get(
                    "published",
                    ""
                )
            })

        return items

    except Exception as error:

        print(
            f"YouTube error: {error}"
        )

        return []


# ==========================================
# MAIN
# ==========================================

def main():

    print()
    print("================================")
    print("     Yane's Aggregator")
    print("     News collector")
    print("================================")
    print()

    sources = load_sources()

    result = {
        "updated": datetime.now(
            timezone.utc
        ).isoformat(),

        "mkd": [],
        "de": [],
        "youtube": []
    }


    # --------------------------------------
    # MKD
    # --------------------------------------

    for source in sources.get(
        "mkd",
        []
    ):

        if source["name"] == "OhridNews":

            result["mkd"].extend(
                scrape_ohridnews()
            )

        elif source["name"] == "SmartPortal":

            result["mkd"].extend(
                scrape_smartportal()
            )

        elif source["type"] == "rss":

            result["mkd"].extend(
                parse_rss(
                    source,
                    "mkd"
                )
            )


    # --------------------------------------
    # DE
    # --------------------------------------

    for source in sources.get(
        "de",
        []
    ):

        if source["name"] == "Tarnkappe":

            result["de"].extend(
                scrape_tarnkappe(
                    source
                )
            )

        elif source["type"] == "rss":

            result["de"].extend(
                parse_rss(
                    source,
                    "de"
                )
            )


    # --------------------------------------
    # YouTube
    # --------------------------------------

    for source in sources.get(
        "youtube",
        []
    ):

        if source["type"] == "youtube":

            result["youtube"].extend(
                parse_youtube(
                    source
                )
            )


    # --------------------------------------
    # Remove duplicates
    # --------------------------------------

    for category in [
        "mkd",
        "de",
        "youtube"
    ]:

        unique = {}

        for item in result[category]:

            url = item.get("url")

            if url:
                unique[url] = item

        result[category] = list(
            unique.values()
        )


    # --------------------------------------
    # Save
    # --------------------------------------

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=2
        )


    print()
    print("================================")
    print("news.json created!")
    print(
        f"MKD: {len(result['mkd'])}"
    )
    print(
        f"DE: {len(result['de'])}"
    )
    print(
        f"YouTube: {len(result['youtube'])}"
    )
    print("================================")


if __name__ == "__main__":
    main()
