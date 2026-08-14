import json
import re
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin

import feedparser
import requests


SOURCES_FILE = "sources.json"
OUTPUT_FILE = "news.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def clean_text(text):
    if not text:
        return ""

    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def load_sources():
    with open(SOURCES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    return response.text


# ==========================================
# RSS
# ==========================================

def get_rss_image(entry):

    for media in entry.get("media_content", []):
        if media.get("url"):
            return media["url"]

    for media in entry.get("media_thumbnail", []):
        if media.get("url"):
            return media["url"]

    for enclosure in entry.get("enclosures", []):
        image = enclosure.get("href") or enclosure.get("url")

        if image:
            return image

    summary = entry.get("summary", "")

    match = re.search(
        r'<img[^>]+src=["\']([^"\']+)["\']',
        summary,
        re.IGNORECASE
    )

    if match:
        return match.group(1)

    return ""


def parse_rss(source, category):

    print(f"RSS: {source['name']}")

    try:

        feed = feedparser.parse(source["url"])

        items = []

        for entry in feed.entries[:15]:

            link = entry.get("link", "")

            if not link:
                continue

            items.append({
                "category": category,
                "source": source["name"],
                "title": clean_text(
                    entry.get("title", "Без наслов")
                ),
                "description": clean_text(
                    entry.get("summary", "")
                )[:300],
                "url": link,
                "image": get_rss_image(entry),
                "date": (
                    entry.get("published", "")
                    or entry.get("updated", "")
                )
            })

        return items

    except Exception as e:

        print(
            f"RSS ERROR [{source['name']}]: {e}"
        )

        return []


# ==========================================
# SIMPLE WEBSITE SCRAPER
# ==========================================

def scrape_website(source, category):

    print(f"SCRAPE: {source['name']}")

    try:

        html = get_page(source["url"])

        items = []
        seen = set()

        links = re.findall(
            r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            html,
            re.IGNORECASE | re.DOTALL
        )

        for href, content in links:

            title = clean_text(content)

            if len(title) < 25:
                continue

            if len(title) > 250:
                continue

            url = urljoin(
                source["url"],
                href
            )

            if url in seen:
                continue

            lowered = url.lower()

            if any(
                x in lowered
                for x in [
                    "javascript:",
                    "/tag/",
                    "/category/",
                    "/author/",
                    "/page/"
                ]
            ):
                continue

            seen.add(url)

            image = ""

            position = html.find(href)

            if position >= 0:

                area = html[
                    max(0, position - 2000):
                    position + 2000
                ]

                match = re.search(
                    r'<img[^>]+(?:src|data-src)=["\']([^"\']+)["\']',
                    area,
                    re.IGNORECASE
                )

                if match:

                    image = urljoin(
                        source["url"],
                        match.group(1)
                    )

            items.append({
                "category": category,
                "source": source["name"],
                "title": title,
                "description": "",
                "url": url,
                "image": image,
                "date": ""
            })

            if len(items) >= 15:
                break

        return items

    except Exception as e:

        print(
            f"SCRAPE ERROR [{source['name']}]: {e}"
        )

        return []


# ==========================================
# YOUTUBE
# ==========================================

def get_youtube_channel_id(url):

    try:

        html = get_page(url)

        patterns = [
            r'"channelId":"(UC[^"]+)"',
            r'"externalId":"(UC[^"]+)"',
            r'"browseId":"(UC[^"]+)"',
            r'itemprop="channelId" content="(UC[^"]+)"'
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                html
            )

            if match:
                return match.group(1)

    except Exception as e:

        print(
            f"YouTube ID ERROR: {e}"
        )

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
                "yt_videoid",
                ""
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

    except Exception as e:

        print(
            f"YouTube ERROR "
            f"[{source['name']}]: {e}"
        )

        return []


# ==========================================
# REMOVE DUPLICATES
# ==========================================

def remove_duplicates(items):

    result = {}
    
    for item in items:

        url = item.get("url")

        if url:
            result[url] = item

    return list(result.values())


# ==========================================
# MAIN
# ==========================================

def main():

    print("================================")
    print("YANE'S AGGREGATOR")
    print("Collector started")
    print("================================")

    sources = load_sources()

    result = {
        "updated": datetime.now(
            timezone.utc
        ).isoformat(),

        "mkd": [],
        "de": [],
        "youtube": []
    }


    # MKD

    for source in sources.get("mkd", []):

        if source.get("type") == "rss":

            items = parse_rss(
                source,
                "mkd"
            )

        else:

            items = scrape_website(
                source,
                "mkd"
            )

        result["mkd"].extend(items)


    # DE

    for source in sources.get("de", []):

        if source.get("type") == "rss":

            items = parse_rss(
                source,
                "de"
            )

        else:

            items = scrape_website(
                source,
                "de"
            )

        result["de"].extend(items)


    # YouTube

    for source in sources.get("youtube", []):

        items = parse_youtube(
            source
        )

        result["youtube"].extend(items)


    # Remove duplicates

    result["mkd"] = remove_duplicates(
        result["mkd"]
    )

    result["de"] = remove_duplicates(
        result["de"]
    )

    result["youtube"] = remove_duplicates(
        result["youtube"]
    )


    # Limit results

    result["mkd"] = result["mkd"][:30]
    result["de"] = result["de"][:30]
    result["youtube"] = result["youtube"][:30]


    # Save news.json

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            result,
            f,
            ensure_ascii=False,
            indent=2
        )


    print("================================")
    print(
        f"MKD: {len(result['mkd'])}"
    )
    print(
        f"DE: {len(result['de'])}"
    )
    print(
        f"YouTube: {len(result['youtube'])}"
    )
    print("news.json created")
    print("================================")


if __name__ == "__main__":
    main()
