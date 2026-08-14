import json
import re
from datetime import datetime, timezone

import feedparser
import requests


SOURCES_FILE = "sources.json"
OUTPUT_FILE = "news.json"


def load_sources():
    with open(SOURCES_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def clean_text(text):
    if not text:
        return ""

    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def get_image(entry):
    # Media RSS
    if hasattr(entry, "media_content"):
        for media in entry.media_content:
            url = media.get("url")

            if url:
                return url

    # Media thumbnail
    if hasattr(entry, "media_thumbnail"):
        for media in entry.media_thumbnail:
            url = media.get("url")

            if url:
                return url

    # Enclosure
    if hasattr(entry, "enclosures"):
        for enclosure in entry.enclosures:

            url = enclosure.get("href") or enclosure.get("url")
            content_type = enclosure.get("type", "")

            if url and "image" in content_type:
                return url

    # Try to find image inside description
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
    published = entry.get("published")

    if published:
        return published

    updated = entry.get("updated")

    if updated:
        return updated

    return ""


def parse_rss(source, category):
    print(f"RSS: {source['name']}")

    feed = feedparser.parse(source["url"])

    items = []

    for entry in feed.entries[:15]:

        title = clean_text(
            entry.get("title", "Без наслов")
        )

        description = clean_text(
            entry.get("summary", "")
        )

        url = entry.get("link", "")

        image = get_image(entry)

        date = get_date(entry)

        items.append({
            "category": category,
            "source": source["name"],
            "title": title,
            "description": description[:300],
            "url": url,
            "image": image,
            "date": date
        })

    return items


def get_youtube_channel_id(channel_url):
    """
    Gets the channel page and tries to find
    the channel ID from the HTML.
    """

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(
        channel_url,
        headers=headers,
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

        match = re.search(pattern, html)

        if match:
            return match.group(1)

    return None


def parse_youtube(source):
    print(f"YouTube: {source['name']}")

    try:

        channel_id = get_youtube_channel_id(
            source["url"]
        )

        if not channel_id:

            print(
                f"Could not find channel ID: {source['name']}"
            )

            return []

        feed_url = (
            "https://www.youtube.com/feeds/videos.xml?"
            f"channel_id={channel_id}"
        )

        feed = feedparser.parse(feed_url)

        items = []

        for entry in feed.entries[:10]:

            title = clean_text(
                entry.get("title", "Без наслов")
            )

            url = entry.get("link", "")

            published = entry.get(
                "published",
                ""
            )

            video_id = entry.get("yt_videoid")

            image = ""

            if video_id:

                image = (
                    "https://i.ytimg.com/vi/"
                    f"{video_id}/hqdefault.jpg"
                )

            items.append({
                "category": "youtube",
                "source": source["name"],
                "title": title,
                "description": "",
                "url": url,
                "image": image,
                "date": published
            })

        return items

    except Exception as error:

        print(
            f"YouTube error "
            f"{source['name']}: {error}"
        )

        return []


def main():

    print("================================")
    print("Yane's Aggregator")
    print("Starting news collector...")
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

        if source["type"] == "rss":

            result["mkd"].extend(
                parse_rss(
                    source,
                    "mkd"
                )
            )


    # DE

    for source in sources.get("de", []):

        if source["type"] == "rss":

            result["de"].extend(
                parse_rss(
                    source,
                    "de"
                )
            )


    # YouTube

    for source in sources.get("youtube", []):

        if source["type"] == "youtube":

            result["youtube"].extend(
                parse_youtube(source)
            )


    # Save JSON

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


    print("================================")
    print("news.json created successfully!")
    print("================================")


if __name__ == "__main__":
    main()
