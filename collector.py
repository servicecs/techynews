import json
import re
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin

import feedparser
import requests


SOURCES_FILE = "sources.json"
OUTPUT_FILE = "news.json"

MAX_ITEMS_PER_CATEGORY = 100
MAX_ITEMS_PER_FEED = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36"
    )
}


# ============================================================
# TEXT
# ============================================================

def clean_text(text):
    if not text:
        return ""

    text = unescape(str(text))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# LOAD SOURCES
# ============================================================

def load_sources():
    with open(
        SOURCES_FILE,
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)


# ============================================================
# HTTP
# ============================================================

def get_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    return response.text


# ============================================================
# IMAGE URL
# ============================================================

def clean_image_url(url, base_url=""):
    if not url:
        return ""

    url = str(url).strip()
    url = url.strip("\"'")

    if url.startswith("//"):
        url = "https:" + url

    if base_url:
        url = urljoin(
            base_url,
            url
        )

    return url


# ============================================================
# EXTRACT IMAGE FROM HTML
# ============================================================

def extract_image_from_html(
    html,
    base_url=""
):
    if not html:
        return ""

    patterns = [

        # OpenGraph
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',

        # Twitter
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',

        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',

        # Images
        r'<img[^>]+src=["\']([^"\']+)["\']',

        r'<img[^>]+data-src=["\']([^"\']+)["\']',

        r'<img[^>]+data-lazy-src=["\']([^"\']+)["\']',

        r'<img[^>]+data-original=["\']([^"\']+)["\']'
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.IGNORECASE
        )

        if match:

            image = clean_image_url(
                match.group(1),
                base_url
            )

            if image:
                return image

    return ""


# ============================================================
# RSS IMAGE
# ============================================================

def get_rss_image(
    entry,
    feed_url=""
):

    # --------------------------------------------------------
    # media:content
    # --------------------------------------------------------

    for media in entry.get(
        "media_content",
        []
    ):

        if not isinstance(
            media,
            dict
        ):
            continue

        url = (
            media.get("url")
            or media.get("href")
        )

        if url:

            image = clean_image_url(
                url,
                feed_url
            )

            if image:
                return image


    # --------------------------------------------------------
    # media:thumbnail
    # --------------------------------------------------------

    for media in entry.get(
        "media_thumbnail",
        []
    ):

        if not isinstance(
            media,
            dict
        ):
            continue

        url = (
            media.get("url")
            or media.get("href")
        )

        if url:

            image = clean_image_url(
                url,
                feed_url
            )

            if image:
                return image


    # --------------------------------------------------------
    # enclosure
    # --------------------------------------------------------

    for enclosure in entry.get(
        "enclosures",
        []
    ):

        if not isinstance(
            enclosure,
            dict
        ):
            continue

        url = (
            enclosure.get("href")
            or enclosure.get("url")
        )

        if url:

            image = clean_image_url(
                url,
                feed_url
            )

            if image:
                return image


    # --------------------------------------------------------
    # image field
    # --------------------------------------------------------

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
            or image_field.get("src")
        )

        if url:

            image = clean_image_url(
                url,
                feed_url
            )

            if image:
                return image

    elif isinstance(
        image_field,
        str
    ):

        image = clean_image_url(
            image_field,
            feed_url
        )

        if image:
            return image


    # --------------------------------------------------------
    # summary
    # --------------------------------------------------------

    summary = entry.get(
        "summary",
        ""
    )

    image = extract_image_from_html(
        summary,
        feed_url
    )

    if image:
        return image


    # --------------------------------------------------------
    # description
    # --------------------------------------------------------

    description = entry.get(
        "description",
        ""
    )

    image = extract_image_from_html(
        description,
        feed_url
    )

    if image:
        return image


    # --------------------------------------------------------
    # content
    # --------------------------------------------------------

    for content in entry.get(
        "content",
        []
    ):

        if not isinstance(
            content,
            dict
        ):
            continue

        value = content.get(
            "value",
            ""
        )

        image = extract_image_from_html(
            value,
            feed_url
        )

        if image:
            return image


    # --------------------------------------------------------
    # content:encoded
    # --------------------------------------------------------

    encoded = entry.get(
        "content:encoded",
        ""
    )

    image = extract_image_from_html(
        encoded,
        feed_url
    )

    if image:
        return image


    return ""


# ============================================================
# RSS PARSER
# ============================================================

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

        if feed.bozo:

            print(
                f"RSS warning [{source['name']}]: "
                f"{feed.bozo_exception}"
            )


        items = []


        for entry in feed.entries[
            :MAX_ITEMS_PER_FEED
        ]:

            link = (
                entry.get("link")
                or ""
            )

            if not link:
                continue


            title = clean_text(
                entry.get(
                    "title",
                    "Untitled"
                )
            )

            if not title:
                continue


            description = clean_text(
                entry.get(
                    "summary",
                    ""
                )
            )

            if not description:

                description = clean_text(
                    entry.get(
                        "description",
                        ""
                    )
                )


            image = get_rss_image(
                entry,
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


            # ------------------------------------------------
            # Timestamp for sorting
            # ------------------------------------------------

            timestamp = 0

            try:

                parsed_time = (
                    entry.get(
                        "published_parsed"
                    )
                    or
                    entry.get(
                        "updated_parsed"
                    )
                )

                if parsed_time:

                    timestamp = datetime(
                        *parsed_time[:6],
                        tzinfo=timezone.utc
                    ).timestamp()

            except Exception:

                timestamp = 0


            items.append({

                "category": category,

                "source": source["name"],

                "title": title,

                "description": description[:500],

                "url": link,

                "image": image,

                "date": date,

                "_timestamp": timestamp
            })


        print(
            f"  Articles found: {len(items)}"
        )

        return items


    except Exception as e:

        print(
            f"RSS ERROR [{source['name']}]: {e}"
        )

        return []


# ============================================================
# REMOVE DUPLICATES
# ============================================================

def remove_duplicates(items):

    result = {}

    for item in items:

        url = (
            item.get("url")
            or ""
        ).strip()

        if not url:
            continue


        if url not in result:

            result[url] = item

        else:

            existing = result[url]

            # Prefer item which has an image
            if (
                not existing.get("image")
                and item.get("image")
            ):

                result[url] = item


    return list(
        result.values()
    )


# ============================================================
# SORT NEWS
# ============================================================

def sort_items(items):

    return sorted(
        items,
        key=lambda item:
            item.get(
                "_timestamp",
                0
            ),
        reverse=True
    )


# ============================================================
# REMOVE INTERNAL FIELDS
# ============================================================

def clean_output(items):

    result = []

    for item in items:

        result.append({

            "category":
                item.get(
                    "category",
                    ""
                ),

            "source":
                item.get(
                    "source",
                    ""
                ),

            "title":
                item.get(
                    "title",
                    ""
                ),

            "description":
                item.get(
                    "description",
                    ""
                ),

            "url":
                item.get(
                    "url",
                    ""
                ),

            "image":
                item.get(
                    "image",
                    ""
                ),

            "date":
                item.get(
                    "date",
                    ""
                )
        })


    return result


# ============================================================
# COLLECT CATEGORY
# ============================================================

def collect_category(
    sources,
    category
):

    all_items = []


    for source in sources:

        source_type = (
            source.get("type")
        )


        if source_type != "rss":

            print(
                f"Skipping non-RSS source: "
                f"{source.get('name')}"
            )

            continue


        items = parse_rss(
            source,
            category
        )


        all_items.extend(
            items
        )


    # Remove duplicate URLs

    all_items = remove_duplicates(
        all_items
    )


    # Newest first

    all_items = sort_items(
        all_items
    )


    # Maximum 100 per category

    all_items = all_items[
        :MAX_ITEMS_PER_CATEGORY
    ]


    # Remove internal timestamp

    all_items = clean_output(
        all_items
    )


    return all_items


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("========================================")
    print("       YANE'S AGGREGATOR")
    print("       RSS COLLECTOR")
    print("========================================")
    print()


    sources = load_sources()


    result = {

        "updated":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "mkd": [],

        "de": [],

        "eng": [],

        "starwars": []
    }


    # ========================================================
    # MKD
    # ========================================================

    print("🇲🇰 MKD")

    result["mkd"] = collect_category(
        sources.get(
            "mkd",
            []
        ),
        "mkd"
    )

    print(
        f"MKD saved: "
        f"{len(result['mkd'])}"
    )

    print()


    # ========================================================
    # DE
    # ========================================================

    print("🇩🇪 DE")

    result["de"] = collect_category(
        sources.get(
            "de",
            []
        ),
        "de"
    )

    print(
        f"DE saved: "
        f"{len(result['de'])}"
    )

    print()


    # ========================================================
    # ENG
    # ========================================================

    print("🇬🇧 ENG")

    result["eng"] = collect_category(
        sources.get(
            "eng",
            []
        ),
        "eng"
    )

    print(
        f"ENG saved: "
        f"{len(result['eng'])}"
    )

    print()


    # ========================================================
    # STAR WARS
    # ========================================================

    print("⭐ STAR WARS")

    result["starwars"] = collect_category(
        sources.get(
            "starwars",
            []
        ),
        "starwars"
    )

    print(
        f"Star Wars saved: "
        f"{len(result['starwars'])}"
    )

    print()


    # ========================================================
    # SAVE JSON
    # ========================================================

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


    # ========================================================
    # SUMMARY
    # ========================================================

    print("========================================")
    print("COLLECTION COMPLETE")
    print("========================================")

    print(
        f"🇲🇰 MKD: "
        f"{len(result['mkd'])}"
    )

    print(
        f"🇩🇪 DE: "
        f"{len(result['de'])}"
    )

    print(
        f"🇬🇧 ENG: "
        f"{len(result['eng'])}"
    )

    print(
        f"⭐ Star Wars: "
        f"{len(result['starwars'])}"
    )

    print()
    print(
        f"Maximum per category: "
        f"{MAX_ITEMS_PER_CATEGORY}"
    )

    print(
        "news.json created successfully"
    )

    print("========================================")


if __name__ == "__main__":
    main()
