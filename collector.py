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
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    )
}

MAX_RSS_ITEMS = 20
MAX_SECTION_ITEMS = 20


# =========================================================
# DEFAULT IMAGES
# =========================================================

DEFAULT_IMAGES = {
    "mkd": (
        "https://upload.wikimedia.org/wikipedia/commons/"
        "7/79/Flag_of_North_Macedonia.svg"
    ),

    "de": (
        "https://upload.wikimedia.org/wikipedia/commons/"
        "b/ba/Flag_of_Germany.svg"
    ),

    "eng": (
        "https://upload.wikimedia.org/wikipedia/commons/"
        "4/4a/English_language.svg"
    ),

    "starwars": (
        "https://upload.wikimedia.org/wikipedia/commons/"
        "6/6c/Star_Wars_Logo.svg"
    ),
}


# =========================================================
# SESSION
# =========================================================

session = requests.Session()
session.headers.update(HEADERS)


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
# GET WEB PAGE
# =========================================================

def get_page(url):

    response = session.get(
        url,
        timeout=30,
        allow_redirects=True
    )

    response.raise_for_status()

    return response.text


# =========================================================
# CLEAN URL
# =========================================================

def clean_url(url, base_url=""):

    if not url:
        return ""

    url = str(url).strip()

    url = (
        url
        .replace("&amp;", "&")
        .replace("&#038;", "&")
        .strip("'\"")
    )

    if url.startswith("//"):
        url = "https:" + url

    if base_url:
        url = urljoin(
            base_url,
            url
        )

    return url


# =========================================================
# CHECK IMAGE URL
# =========================================================

def looks_like_image(url):

    if not url:
        return False

    url_lower = url.lower()

    image_extensions = (
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
        ".avif",
        ".svg"
    )

    if any(
        ext in url_lower
        for ext in image_extensions
    ):
        return True

    image_words = (
        "/image",
        "/images/",
        "/img/",
        "/uploads/",
        "/media/",
        "/wp-content/uploads/"
    )

    if any(
        word in url_lower
        for word in image_words
    ):
        return True

    return False


# =========================================================
# FIND IMAGE IN HTML
# =========================================================

def find_image_in_html(
    html,
    article_url
):

    if not html:
        return ""

    # -----------------------------------------------------
    # 1. OpenGraph
    # -----------------------------------------------------

    patterns = [

        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',

        r'<meta[^>]+property=["\']og:image:url["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image:url["\']',

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.IGNORECASE
        )

        if match:

            image = clean_url(
                match.group(1),
                article_url
            )

            if image:
                return image


    # -----------------------------------------------------
    # 2. Twitter image
    # -----------------------------------------------------

    patterns = [

        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',

        r'<meta[^>]+name=["\']twitter:image:src["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image:src["\']',

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.IGNORECASE
        )

        if match:

            image = clean_url(
                match.group(1),
                article_url
            )

            if image:
                return image


    # -----------------------------------------------------
    # 3. JSON-LD image
    # -----------------------------------------------------

    json_ld_patterns = [

        r'"image"\s*:\s*"([^"]+)"',

        r'"image"\s*:\s*\[\s*"([^"]+)"',

        r'"thumbnailUrl"\s*:\s*"([^"]+)"',

    ]

    for pattern in json_ld_patterns:

        match = re.search(
            pattern,
            html,
            re.IGNORECASE
        )

        if match:

            image = clean_url(
                match.group(1),
                article_url
            )

            if image:
                return image


    # -----------------------------------------------------
    # 4. IMG tags
    # -----------------------------------------------------

    img_tags = re.findall(
        r"<img\b[^>]*>",
        html,
        re.IGNORECASE
    )

    attributes = [
        "src",
        "data-src",
        "data-original",
        "data-lazy-src",
        "data-image",
        "data-url",
        "data-original-src",
        "data-fallback-src"
    ]

    for tag in img_tags:

        for attribute in attributes:

            pattern = (
                rf'{attribute}\s*=\s*'
                rf'["\']([^"\']+)["\']'
            )

            match = re.search(
                pattern,
                tag,
                re.IGNORECASE
            )

            if match:

                image = clean_url(
                    match.group(1),
                    article_url
                )

                if (
                    image
                    and looks_like_image(image)
                ):
                    return image


        # -------------------------------------------------
        # srcset
        # -------------------------------------------------

        match = re.search(
            r'srcset\s*=\s*["\']([^"\']+)["\']',
            tag,
            re.IGNORECASE
        )

        if match:

            srcset = match.group(1)

            candidates = [
                x.strip().split(" ")[0]
                for x in srcset.split(",")
            ]

            for candidate in reversed(candidates):

                image = clean_url(
                    candidate,
                    article_url
                )

                if (
                    image
                    and looks_like_image(image)
                ):
                    return image


    return ""


# =========================================================
# GET ARTICLE IMAGE
# =========================================================

def get_article_image(url):

    if not url:
        return ""

    try:

        print(
            f"    IMAGE FALLBACK: {url}"
        )

        html = get_page(url)

        image = find_image_in_html(
            html,
            url
        )

        if image:

            print(
                f"    IMAGE FOUND: {image}"
            )

            return image

    except Exception as e:

        print(
            f"    IMAGE ERROR: {e}"
        )

    return ""


# =========================================================
# RSS IMAGE
# =========================================================

def get_rss_image(entry):

    # -----------------------------------------------------
    # media:content
    # -----------------------------------------------------

    for media in entry.get(
        "media_content",
        []
    ):

        if isinstance(media, dict):

            url = (
                media.get("url")
                or media.get("href")
            )

            if url:

                return clean_url(url)


    # -----------------------------------------------------
    # media:thumbnail
    # -----------------------------------------------------

    for media in entry.get(
        "media_thumbnail",
        []
    ):

        if isinstance(media, dict):

            url = (
                media.get("url")
                or media.get("href")
            )

            if url:

                return clean_url(url)


    # -----------------------------------------------------
    # enclosure
    # -----------------------------------------------------

    for enclosure in entry.get(
        "enclosures",
        []
    ):

        if isinstance(enclosure, dict):

            url = (
                enclosure.get("href")
                or enclosure.get("url")
            )

            if url:

                return clean_url(url)


    # -----------------------------------------------------
    # image field
    # -----------------------------------------------------

    image_field = entry.get(
        "image"
    )

    if isinstance(
        image_field,
        dict
    ):

        url = (
            image_field.get("href")
            or image_field.get("url")
        )

        if url:

            return clean_url(url)


    # -----------------------------------------------------
    # RSS HTML content
    # -----------------------------------------------------

    html_fields = [

        entry.get("summary", ""),

        entry.get("description", ""),

        entry.get("content", ""),

        entry.get(
            "content:encoded",
            ""
        )

    ]

    for html in html_fields:

        if isinstance(
            html,
            list
        ):

            for part in html:

                if isinstance(
                    part,
                    dict
                ):

                    html_text = (
                        part.get("value", "")
                    )

                    match = re.search(
                        r'<img[^>]+(?:src|data-src)=["\']([^"\']+)["\']',
                        html_text,
                        re.IGNORECASE
                    )

                    if match:

                        return clean_url(
                            match.group(1)
                        )

        elif isinstance(
            html,
            str
        ):

            match = re.search(
                r'<img[^>]+(?:src|data-src)=["\']([^"\']+)["\']',
                html,
                re.IGNORECASE
            )

            if match:

                return clean_url(
                    match.group(1)
                )


    return ""


# =========================================================
# RSS PARSER
# =========================================================

def parse_rss(
    source,
    category
):

    print(
        f"RSS: {source['name']}"
    )

    try:

        feed = feedparser.parse(
            source["url"]
        )

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
            )[:500]


            image = get_rss_image(
                entry
            )


            # -------------------------------------------------
            # IMPORTANT:
            # If RSS has no image, visit the article
            # -------------------------------------------------

            if not image:

                image = get_article_image(
                    link
                )


            # -------------------------------------------------
            # Final fallback
            # -------------------------------------------------

            if not image:

                image = DEFAULT_IMAGES.get(
                    category,
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


            items.append({

                "category": category,

                "source":
                    source["name"],

                "title":
                    title,

                "description":
                    description,

                "url":
                    link,

                "image":
                    image,

                "date":
                    date

            })


        return items


    except Exception as e:

        print(
            f"RSS ERROR "
            f"[{source['name']}]: {e}"
        )

        return []


# =========================================================
# SIMPLE WEBSITE SCRAPER
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


            # -------------------------------------------------
            # Try to find image near link
            # -------------------------------------------------

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


                match = re.search(
                    r'<img[^>]+(?:src|data-src|data-lazy-src)=["\']([^"\']+)["\']',
                    area,
                    re.IGNORECASE
                )


                if match:

                    image = clean_url(
                        match.group(1),
                        source["url"]
                    )


            # -------------------------------------------------
            # If not found, visit article
            # -------------------------------------------------

            if not image:

                image = get_article_image(
                    url
                )


            # -------------------------------------------------
            # Default image
            # -------------------------------------------------

            if not image:

                image = DEFAULT_IMAGES.get(
                    category,
                    ""
                )


            items.append({

                "category":
                    category,

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


            if len(items) >= MAX_RSS_ITEMS:
                break


        return items


    except Exception as e:

        print(
            f"SCRAPE ERROR "
            f"[{source['name']}]: {e}"
        )

        return []


# =========================================================
# YOUTUBE CHANNEL ID
# =========================================================

def get_youtube_channel_id(
    url
):

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

def parse_youtube(
    source
):

    print(
        f"YouTube: {source['name']}"
    )


    try:

        channel_id = (
            get_youtube_channel_id(
                source["url"]
            )
        )


        if not channel_id:

            print(
                "Channel ID not found: "
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

                "category":
                    "youtube",

                "source":
                    source["name"],

                "title":
                    clean_text(
                        entry.get(
                            "title",
                            "Untitled"
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


    except Exception as e:

        print(
            f"YouTube ERROR "
            f"[{source['name']}]: {e}"
        )

        return []


# =========================================================
# REMOVE DUPLICATES
# =========================================================

def remove_duplicates(
    items
):

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

def sort_items(
    items
):

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

    for source in sources.get(
        "mkd",
        []
    ):

        if source.get(
            "type"
        ) == "rss":

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


    # =====================================================
    # DE
    # =====================================================

    for source in sources.get(
        "de",
        []
    ):

        if source.get(
            "type"
        ) == "rss":

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


    # =====================================================
    # ENG
    # =====================================================

    for source in sources.get(
        "eng",
        []
    ):

        if source.get(
            "type"
        ) == "rss":

            items = parse_rss(
                source,
                "eng"
            )

        else:

            items = scrape_website(
                source,
                "eng"
            )


        result["eng"].extend(
            items
        )


    # =====================================================
    # STAR WARS
    # =====================================================

    for source in sources.get(
        "starwars",
        []
    ):

        if source.get(
            "type"
        ) == "rss":

            items = parse_rss(
                source,
                "starwars"
            )

        else:

            items = scrape_website(
                source,
                "starwars"
            )


        result["starwars"].extend(
            items
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


    # =====================================================
    # REMOVE DUPLICATES
    # =====================================================

    for category in [
        "mkd",
        "de",
        "eng",
        "starwars",
        "youtube"
    ]:

        result[category] = remove_duplicates(
            result[category]
        )


    # =====================================================
    # SORT
    # =====================================================

    for category in [
        "mkd",
        "de",
        "eng",
        "starwars",
        "youtube"
    ]:

        result[category] = sort_items(
            result[category]
        )


    # =====================================================
    # LIMIT
    # =====================================================

    result["mkd"] = result[
        "mkd"
    ][:MAX_SECTION_ITEMS]


    result["de"] = result[
        "de"
    ][:MAX_SECTION_ITEMS]


    result["eng"] = result[
        "eng"
    ][:MAX_SECTION_ITEMS]


    result["starwars"] = result[
        "starwars"
    ][:MAX_SECTION_ITEMS]


    result["youtube"] = result[
        "youtube"
    ][:30]


    # =====================================================
    # SAVE
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


    # =====================================================
    # REPORT
    # =====================================================

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
        f"Star Wars: {len(result['starwars'])}"
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
# START
# =========================================================

if __name__ == "__main__":

    main()
