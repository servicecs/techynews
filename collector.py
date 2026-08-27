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

MAX_RSS_ITEMS = 20
MAX_CATEGORY_ITEMS = 30


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
        timeout=20,
        allow_redirects=True
    )

    response.raise_for_status()

    return response.text


# =========================================================
# CLEAN IMAGE URL
# =========================================================

def clean_image_url(url, base_url=""):

    if not url:
        return ""

    url = unescape(str(url)).strip()

    url = url.strip("'\"")

    if url.startswith("//"):
        url = "https:" + url

    if base_url:
        url = urljoin(base_url, url)

    return url


# =========================================================
# CHECK IMAGE URL
# =========================================================

def looks_like_image(url):

    if not url:
        return False

    value = url.lower().split("?")[0].split("#")[0]

    extensions = (
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
        ".avif",
        ".svg"
    )

    if value.endswith(extensions):
        return True

    image_words = (
        "/image/",
        "/images/",
        "/img/",
        "/uploads/",
        "/media/",
        "/thumbnail/",
        "/thumbnails/",
        "image=",
        "image_url=",
        "imageurl="
    )

    return any(
        word in value
        for word in image_words
    )


# =========================================================
# EXTRACT OG IMAGE
# =========================================================

def extract_meta_image(html, base_url=""):

    if not html:
        return ""

    patterns = [

        # og:image
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',

        # og:image:url
        r'<meta[^>]+property=["\']og:image:url["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image:url["\']',

        # twitter:image
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',

        # twitter:image:src
        r'<meta[^>]+name=["\']twitter:image:src["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image:src["\']'
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.IGNORECASE | re.DOTALL
        )

        if not match:
            continue

        image = clean_image_url(
            match.group(1),
            base_url
        )

        if image:
            return image

    return ""


# =========================================================
# EXTRACT IMAGE FROM IMG TAG
# =========================================================

def extract_img_image(html, base_url=""):

    if not html:
        return ""

    patterns = [

        r'<img[^>]+data-src=["\']([^"\']+)["\']',

        r'<img[^>]+data-lazy-src=["\']([^"\']+)["\']',

        r'<img[^>]+data-original=["\']([^"\']+)["\']',

        r'<img[^>]+data-image=["\']([^"\']+)["\']',

        r'<img[^>]+src=["\']([^"\']+)["\']'
    ]

    candidates = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            html,
            re.IGNORECASE | re.DOTALL
        )

        candidates.extend(matches)

    for candidate in candidates:

        image = clean_image_url(
            candidate,
            base_url
        )

        if not image:
            continue

        if image.startswith("data:"):
            continue

        lowered = image.lower()

        # Ignore obvious site UI images
        ignored = [
            "logo",
            "avatar",
            "icon",
            "favicon",
            "sprite",
            "placeholder",
            "loader",
            "loading",
            "emoji"
        ]

        if any(
            word in lowered
            for word in ignored
        ):
            continue

        if looks_like_image(image):
            return image

    return ""


# =========================================================
# EXTRACT IMAGE FROM HTML
# =========================================================

def extract_image_from_html(
    html,
    base_url=""
):

    if not html:
        return ""

    # IMPORTANT:
    # Metadata first because the first <img>
    # is often a logo/banner.

    image = extract_meta_image(
        html,
        base_url
    )

    if image:
        return image

    image = extract_img_image(
        html,
        base_url
    )

    if image:
        return image

    return ""


# =========================================================
# RSS IMAGE
# =========================================================

def get_rss_image(
    entry,
    base_url=""
):

    # -----------------------------------------------------
    # media:content
    # -----------------------------------------------------

    media_content = entry.get(
        "media_content",
        []
    )

    if isinstance(
        media_content,
        dict
    ):
        media_content = [
            media_content
        ]

    for media in media_content:

        if not isinstance(
            media,
            dict
        ):
            continue

        image = (
            media.get("url")
            or media.get("href")
            or media.get("src")
        )

        image = clean_image_url(
            image,
            base_url
        )

        if image:
            return image

    # -----------------------------------------------------
    # media:thumbnail
    # -----------------------------------------------------

    media_thumbnail = entry.get(
        "media_thumbnail",
        []
    )

    if isinstance(
        media_thumbnail,
        dict
    ):
        media_thumbnail = [
            media_thumbnail
        ]

    for media in media_thumbnail:

        if not isinstance(
            media,
            dict
        ):
            continue

        image = (
            media.get("url")
            or media.get("href")
            or media.get("src")
        )

        image = clean_image_url(
            image,
            base_url
        )

        if image:
            return image

    # -----------------------------------------------------
    # enclosure
    # -----------------------------------------------------

    enclosures = entry.get(
        "enclosures",
        []
    )

    if isinstance(
        enclosures,
        dict
    ):
        enclosures = [
            enclosures
        ]

    for enclosure in enclosures:

        if not isinstance(
            enclosure,
            dict
        ):
            continue

        image = (
            enclosure.get("href")
            or enclosure.get("url")
        )

        image = clean_image_url(
            image,
            base_url
        )

        if not image:
            continue

        mime = str(
            enclosure.get(
                "type",
                ""
            )
        ).lower()

        if (
            mime.startswith("image/")
            or looks_like_image(image)
        ):
            return image

    # -----------------------------------------------------
    # image field
    # -----------------------------------------------------

    image = entry.get(
        "image"
    )

    if isinstance(
        image,
        dict
    ):

        image = (
            image.get("href")
            or image.get("url")
            or image.get("src")
        )

    image = clean_image_url(
        image,
        base_url
    )

    if image:
        return image

    # -----------------------------------------------------
    # summary
    # -----------------------------------------------------

    summary = entry.get(
        "summary",
        ""
    )

    image = extract_image_from_html(
        summary,
        base_url
    )

    if image:
        return image

    # -----------------------------------------------------
    # content
    # -----------------------------------------------------

    content = entry.get(
        "content",
        []
    )

    if isinstance(
        content,
        list
    ):

        for content_item in content:

            if not isinstance(
                content_item,
                dict
            ):
                continue

            html = content_item.get(
                "value",
                ""
            )

            image = extract_image_from_html(
                html,
                base_url
            )

            if image:
                return image

    # -----------------------------------------------------
    # content:encoded
    # -----------------------------------------------------

    encoded = entry.get(
        "content:encoded",
        ""
    )

    image = extract_image_from_html(
        encoded,
        base_url
    )

    if image:
        return image

    # Some feeds expose it with another key
    encoded = entry.get(
        "content_encoded",
        ""
    )

    image = extract_image_from_html(
        encoded,
        base_url
    )

    if image:
        return image

    return ""


# =========================================================
# IMAGE FROM ORIGINAL ARTICLE
# =========================================================

def get_article_image(
    article_url
):

    if not article_url:
        return ""

    try:

        print(
            f"    IMAGE LOOKUP: {article_url}"
        )

        html = get_page(
            article_url
        )

        image = extract_meta_image(
            html,
            article_url
        )

        if image:
            return image

        image = extract_img_image(
            html,
            article_url
        )

        if image:
            return image

    except Exception as e:

        print(
            f"    IMAGE LOOKUP FAILED: {e}"
        )

    return ""


# =========================================================
# FIND BEST RSS IMAGE
# =========================================================

def find_best_image(
    entry,
    article_url,
    feed_url
):

    # 1. RSS
    image = get_rss_image(
        entry,
        feed_url
    )

    if image:
        return image

    # 2. Original article
    image = get_article_image(
        article_url
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

        if (
            feed.bozo
            and not feed.entries
        ):

            print(
                f"RSS FAILED: {source['name']}"
            )

            return []

        items = []

        for entry in feed.entries[
            :MAX_RSS_ITEMS
        ]:

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

            image = find_best_image(
                entry,
                link,
                source["url"]
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
                        position - 4000
                    ):
                    position + 4000
                ]

                image = extract_image_from_html(
                    area,
                    source["url"]
                )

            # If local page scan did not find image,
            # open the actual article.
            if not image:

                image = get_article_image(
                    url
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

            if len(items) >= MAX_RSS_ITEMS:
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

        print(
            f"  -> {len(items)} videos"
        )

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

    return result[:MAX_CATEGORY_ITEMS]


# =========================================================
# ENG SOURCES
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

        # Engadget fallback
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

                "url":
                    "https://www.engadget.com/rss.xml"

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

    return result[:MAX_CATEGORY_ITEMS]


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
