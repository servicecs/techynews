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
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    )
}


# =========================================================
# CLEAN TEXT
# =========================================================

def clean_text(text):

    if not text:
        return ""

    text = unescape(str(text))

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# =========================================================
# LOAD SOURCES
# =========================================================

def load_sources():

    with open(
        SOURCES_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


# =========================================================
# GET PAGE
# =========================================================

def get_page(url):

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    return response.text


# =========================================================
# IMAGE FROM HTML
# =========================================================

def extract_image_from_html(html):

    if not html:
        return ""

    patterns = [

        r'<img[^>]+src=["\']([^"\']+)["\']',

        r'<img[^>]+data-src=["\']([^"\']+)["\']',

        r'<img[^>]+data-lazy-src=["\']([^"\']+)["\']',

        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',

        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']'
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.IGNORECASE | re.DOTALL
        )

        if match:

            image = match.group(1)

            if image:

                return image.strip()


    return ""


# =========================================================
# RSS IMAGE
# =========================================================

def get_rss_image(entry):

    # media:content
    for media in entry.get(
        "media_content",
        []
    ):

        if isinstance(media, dict):

            image = (
                media.get("url")
                or media.get("href")
            )

            if image:
                return image


    # media:thumbnail
    for media in entry.get(
        "media_thumbnail",
        []
    ):

        if isinstance(media, dict):

            image = (
                media.get("url")
                or media.get("href")
            )

            if image:
                return image


    # enclosure
    for enclosure in entry.get(
        "enclosures",
        []
    ):

        if isinstance(enclosure, dict):

            image = (
                enclosure.get("href")
                or enclosure.get("url")
            )

            if image:
                return image


    # image field
    image = entry.get(
        "image"
    )

    if isinstance(image, dict):

        image = (
            image.get("href")
            or image.get("url")
        )

        if image:
            return image


    if isinstance(image, str):

        if image:
            return image


    # summary
    summary = entry.get(
        "summary",
        ""
    )

    image = extract_image_from_html(
        summary
    )

    if image:
        return image


    # content
    content = entry.get(
        "content",
        []
    )

    if isinstance(content, list):

        for item in content:

            if isinstance(item, dict):

                html = item.get(
                    "value",
                    ""
                )

                image = extract_image_from_html(
                    html
                )

                if image:
                    return image


    # content:encoded
    encoded = entry.get(
        "content:encoded",
        ""
    )

    image = extract_image_from_html(
        encoded
    )

    if image:
        return image


    return ""


# =========================================================
# RSS PARSER
# =========================================================

def parse_rss(
    source,
    category
):

    print(
        f"RSS: {source['name']} -> {source['url']}"
    )


    try:

        feed = feedparser.parse(
            source["url"]
        )


        if feed.bozo and not feed.entries:

            print(
                f"RSS FAILED: {source['name']}"
            )

            return []


        items = []


        for entry in feed.entries[:20]:

            link = entry.get(
                "link",
                ""
            )


            if not link:
                continue


            title = clean_text(
                entry.get(
                    "title",
                    "Untitled"
                )
            )


            description = clean_text(
                entry.get(
                    "summary",
                    ""
                )
            )


            image = get_rss_image(
                entry
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


            items.append({

                "category": category,

                "source": source["name"],

                "title": title,

                "description": description[:500],

                "url": link,

                "image": image,

                "date": date

            })


        print(
            f"  -> {len(items)} articles"
        )


        return items


    except Exception as e:

        print(
            f"RSS ERROR [{source['name']}]: {e}"
        )

        return []


# =========================================================
# WEBSITE SCRAPER
# =========================================================

def scrape_website(
    source,
    category
):

    print(
        f"SCRAPE: {source['name']}"
    )


    try:

        html = get_page(
            source["url"]
        )


        items = []

        seen = set()


        links = re.findall(

            r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',

            html,

            re.IGNORECASE | re.DOTALL

        )


        for href, content in links:

            title = clean_text(
                content
            )


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
                    "/page/",
                    "#"
                ]
            ):

                continue


            seen.add(url)


            image = ""


            position = html.find(
                href
            )


            if position >= 0:

                area = html[
                    max(
                        0,
                        position - 3000
                    ):
                    position + 3000
                ]


                image = extract_image_from_html(
                    area
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


            if len(items) >= 20:
                break


        print(
            f"  -> {len(items)} articles"
        )


        return items


    except Exception as e:

        print(
            f"SCRAPE ERROR [{source['name']}]: {e}"
        )

        return []


# =========================================================
# YOUTUBE CHANNEL ID
# =========================================================

def get_youtube_channel_id(url):

    try:

        html = get_page(
            url
        )


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


# =========================================================
# YOUTUBE
# =========================================================

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
                        "Untitled"
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


# =========================================================
# REMOVE DUPLICATES
# =========================================================

def remove_duplicates(items):

    result = {}

    for item in items:

        url = item.get(
            "url"
        )


        if url:

            result[url] = item


    return list(
        result.values()
    )


# =========================================================
# SORT BY DATE
# =========================================================

def sort_items(items):

    def get_date(item):

        value = item.get(
            "date",
            ""
        )


        try:

            parsed = feedparser._parse_date(
                value
            )

            if parsed:

                return datetime(
                    *parsed[:6],
                    tzinfo=timezone.utc
                )

        except Exception:
            pass


        return datetime(
            1970,
            1,
            1,
            tzinfo=timezone.utc
        )


    return sorted(
        items,
        key=get_date,
        reverse=True
    )


# =========================================================
# LOAD CATEGORY
# =========================================================

def load_category(
    sources,
    category
):

    result = []


    for source in sources:

        source_type = source.get(
            "type"
        )


        if source_type == "rss":

            items = parse_rss(
                source,
                category
            )


        elif source_type == "website":

            items = scrape_website(
                source,
                category
            )


        else:

            items = []


        result.extend(
            items
        )


    result = remove_duplicates(
        result
    )


    result = sort_items(
        result
    )


    return result[:30]


# =========================================================
# ENGADGET FALLBACK
# =========================================================

def load_eng_sources(
    sources
):

    result = []


    for source in sources:

        items = parse_rss(
            source,
            "eng"
        )


        # If Engadget /feed/ fails,
        # try official rss.xml
        if (
            source["name"] == "Engadget"
            and not items
        ):

            print(
                "Engadget /feed/ failed."
            )

            print(
                "Trying official rss.xml..."
            )


            fallback_source = {
                "name": "Engadget",
                "type": "rss",
                "url": "https://www.engadget.com/rss.xml"
            }


            items = parse_rss(
                fallback_source,
                "eng"
            )


        result.extend(
            items
        )


    result = remove_duplicates(
        result
    )


    result = sort_items(
        result
    )


    return result[:30]


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "========================================"
    )

    print(
        "YANE'S AGGREGATOR"
    )

    print(
        "Collector started"
    )

    print(
        "========================================"
    )


    sources = load_sources()


    result = {

        "updated":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "mkd": [],

        "de": [],

        "eng": [],

        "starwars": [],

        "youtube": []

    }


    # =====================================================
    # MKD
    # =====================================================

    result["mkd"] = load_category(
        sources.get(
            "mkd",
            []
        ),
        "mkd"
    )


    # =====================================================
    # DE
    # =====================================================

    result["de"] = load_category(
        sources.get(
            "de",
            []
        ),
        "de"
    )


    # =====================================================
    # ENG
    # =====================================================

    result["eng"] = load_eng_sources(
        sources.get(
            "eng",
            []
        )
    )


    # =====================================================
    # STAR WARS
    # =====================================================

    result["starwars"] = load_category(
        sources.get(
            "starwars",
            []
        ),
        "starwars"
    )


    # =====================================================
    # YOUTUBE
    # =====================================================

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


    result["youtube"] = remove_duplicates(
        result["youtube"]
    )


    result["youtube"] = result[
        "youtube"
    ][:30]


    # =====================================================
    # SAVE NEWS.JSON
    # =====================================================

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


    print(
        "========================================"
    )

    print(
        f"MKD:       {len(result['mkd'])}"
    )

    print(
        f"DE:        {len(result['de'])}"
    )

    print(
        f"ENG:       {len(result['eng'])}"
    )

    print(
        f"STAR WARS: {len(result['starwars'])}"
    )

    print(
        f"YouTube:   {len(result['youtube'])}"
    )

    print(
        "news.json created"
    )

    print(
        "========================================"
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    main()
