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
    "User-Agent": "Mozilla/5.0 (compatible; YanesAggregator/1.0)"
}


# ==========================================
# BASIC HELPERS
# ==========================================

def clean_text(text):
    if not text:
        return ""

    text = unescape(text)
    text = re.sub(r"<[^>]*>", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def load_sources():
    with open(
        SOURCES_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def get_html(url):
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

    # media:content
    media_content = entry.get(
        "media_content",
        []
    )

    for media in media_content:

        image = media.get("url")

        if image:
            return image


    # media:thumbnail
    media_thumbnail = entry.get(
        "media_thumbnail",
        []
    )

    for media in media_thumbnail:

        image = media.get("url")

        if image:
            return image


    # enclosure
    enclosures = entry.get(
        "enclosures",
        []
    )

    for enclosure in enclosures:

        image = (
            enclosure.get("href")
            or enclosure.get("url")
        )

        if image:
            return image


    # image inside description
    description = entry.get(
        "summary",
        ""
    )

    match = re.search(
        r'<img[^>]+src=["\']([^"\']+)["\']',
        description,
        re.IGNORECASE
    )

    if match:
        return match.group(1)


    return ""


def parse_rss(source, category):

    print(
        f"RSS -> {source['name']}"
    )

    try:

        feed = feedparser.parse(
            source["url"]
        )

        items = []

        for entry in feed.entries[:15]:

            title = clean_text(
                entry.get(
                    "title",
                    "Без наслов"
                )
            )

            description = clean_text(
                entry.get(
                    "summary",
                    ""
                )
            )

            url = entry.get(
                "link",
                ""
            )

            date = (
                entry.get(
                    "published",
                    ""
                )
                or
                entry.get(
                    "updated",
                    ""
                )
            )

            image = get_rss_image(
                entry
            )


            if not url:
                continue


            items.append({

                "category": category,

                "source": source["name"],

                "title": title,

                "description":
                    description[:300],

                "url": url,

                "image": image,

                "date": date
            })


        return items


    except Exception as error:

        print(
            f"RSS ERROR "
            f"{source['name']}: {error}"
        )

        return []


# ==========================================
# SIMPLE HTML SCRAPER
# ==========================================

def scrape_website(
    source,
    category
):

    print(
        f"SCRAPING -> {source['name']}"
    )

    try:

        html = get_html(
            source["url"]
        )

        items = []


        # Find article-like links
        links = re.findall(
            r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            html,
            re.IGNORECASE | re.DOTALL
        )


        seen = set()


        for href, content in links:

            title = clean_text(
                content
            )


            # Remove HTML
            title = re.sub(
                r"<[^>]+>",
                " ",
                title
            )

            title = clean_text(
                title
            )


            # Ignore navigation
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


            # Ignore non article links
            if any(
                x in url.lower()
                for x in [
                    "/tag/",
                    "/category/",
                    "/author/",
                    "/page/",
                    "#",
                    "javascript:"
                ]
            ):
                continue


            seen.add(url)


            # Try to find image near the link
            image = ""


            # Search a small area around the link
            position = html.find(
                href
            )

            if position >= 0:

                area = html[
                    max(
                        0,
                        position - 1500
                    ):
                    position + 1500
                ]


                image_match = re.search(
                    r'<img[^>]+(?:src|data-src)=["\']([^"\']+)["\']',
                    area,
                    re.IGNORECASE
                )


                if image_match:

                    image = urljoin(
                        source["url"],
                        image_match.group(1)
                    )


            items.append({

                "category": category,

                "source":
                    source["name"],

                "title":
                    title,

                "description":
                    "",

                "url":
                    url,

                "image":
                    image,

                "date":
                    ""
            })


            if len(items) >= 15:
                break


        return items


    except Exception as error:

        print(
            f"SCRAPER ERROR "
            f"{source['name']}: {error}"
        )

        return []


# ==========================================
# YOUTUBE
# ==========================================

def get_youtube_channel_id(
    channel_url
):

    print(
        f"Finding YouTube ID: "
        f"{channel_url}"
    )


    try:

        html = get_html(
            channel_url
        )


        patterns = [

            r'"channelId":"(UC[^"]+)"',

            r'"externalId":"(UC[^"]+)"',

            r'<meta[^>]+itemprop="channelId"[^>]+content="(UC[^"]+)"',

            r'"browseId":"(UC[^"]+)"'
        ]


        for pattern in patterns:

            match = re.search(
                pattern,
                html
            )

            if match:

                return match.group(1)


        return None


    except Exception as error:

        print(
            f"YouTube ID ERROR: "
            f"{error}"
        )

        return None


def parse_youtube(
    source
):

    print(
        f"YouTube -> "
        f"{source['name']}"
    )


    try:

        channel_id = (
            get_youtube_channel_id(
                source["url"]
            )
        )


        if not channel_id:

            print(
                "Channel ID not found"
            )

            return []


        feed_url = (
            "https://www.youtube.com/"
            "feeds/videos.xml?"
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
                    "https://i.ytimg.com/"
                    f"vi/{video_id}/hqdefault.jpg"
                )


            items.append({

                "category":
                    "youtube",

                "source":
                    source["name"],

                "title":
                    clean_text(
                        entry.get(
                            "title",
                            "Без наслов"
                        )
                    ),

                "description":
                    "",

                "url":
                    entry.get(
                        "link",
                        ""
                    ),

                "image":
                    image,

                "date":
                    entry.get(
                        "published",
                        ""
                    )
            })


        return items


    except Exception as error:

        print(
            f"YouTube ERROR "
            f"{source['name']}: "
            f"{error}"
        )

        return []


# ==========================================
# REMOVE DUPLICATES
# ==========================================

def remove_duplicates(
    items
):

    unique = {}

    for item in items:

        url = item.get(
            "url",
            ""
        )

        if url:

            unique[url] = item


    return list(
        unique.values()
    )


# ==========================================
# MAIN
# ==========================================

def main():

    print()
    print(
        "================================"
    )
    print(
        "       YANE'S AGGREGATOR"
    )
    print(
        "       NEWS COLLECTOR"
    )
    print(
        "================================"
    )
    print()


    sources = load_sources()


    result = {

        "updated":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "mkd": [],

        "de": [],

        "youtube": []
    }


    # ======================================
    # MKD
    # ======================================

    for source in sources.get(
        "mkd",
        []
    ):

        if source["type"] == "rss":

            items = parse_rss(
                source,
                "mkd"
            )

        else:

            items = scrape_website(
                source,
                "mkd"
            )


        result["mkd"].extend(
            items
        )


    # ======================================
    # DE
    # ======================================

    for source in sources.get(
        "de",
        []
    ):

        if source["type"] == "rss":

            items = parse_rss(
                source,
                "de"
            )

        else:

            items = scrape_website(
                source,
                "de"
            )


        result["de"].extend(
            items
        )


    # ======================================
    # YOUTUBE
    # ======================================

    for source in sources.get(
        "youtube",
        []
    ):

        items = parse_youtube(
            source
        )


        result["youtube"].extend(
            items
        )


    # ======================================
    # REMOVE DUPLICATES
    # ======================================

    result["mkd"] = remove_duplicates(
        result["mkd"]
    )

    result["de"] = remove_duplicates(
        result["de"]
    )

    result["youtube"] = remove_duplicates(
        result["youtube"]
    )


    # ======================================
    # LIMIT
    # ======================================

    result["mkd"] = result["mkd"][:30]

    result["de"] = result["de"][:30]

    result["youtube"] = result["youtube"][:30]


    # ======================================
    # SAVE JSON
    # ======================================

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
    print(
        "================================"
    )

    print(
        f"MKD: "
        f"{len(result['mkd'])}"
    )

    print(
        f"DE: "
        f"{len(result['de'])}"
    )

    print(
        f"YouTube: "
        f"{len(result['youtube'])}"
    )

    print(
        "news.json created successfully!"
    )

    print(
        "================================"
    )


if __name__ == "__main__":

    main()
