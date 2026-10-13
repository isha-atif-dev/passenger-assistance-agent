"""Collects comments from YouTube videos about rail passenger assistance."""

import logging

import requests

from src import config
from src.models import Post

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
COMMENTS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"


def _get(url: str, params: dict) -> dict:
    # The key goes in a header so it never appears in URLs or error messages
    headers = {"x-goog-api-key": config.YOUTUBE_API_KEY}
    response = requests.get(url, headers=headers, params=params, timeout=config.REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _find_videos(query: str) -> list[str]:
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "regionCode": "GB",
        "relevanceLanguage": "en",
        "maxResults": config.YOUTUBE_VIDEOS_PER_QUERY,
    }
    return [item["id"]["videoId"] for item in _get(SEARCH_URL, params).get("items", [])]


def _fetch_comments(video_id: str) -> list[Post]:
    params = {
        "part": "snippet",
        "videoId": video_id,
        "order": "relevance",
        "textFormat": "plainText",
        "maxResults": config.YOUTUBE_COMMENTS_PER_VIDEO,
    }
    posts = []
    for thread in _get(COMMENTS_URL, params).get("items", []):
        # Only the comment text and date are kept, never the author's name
        comment = thread["snippet"]["topLevelComment"]["snippet"]
        posts.append(
            Post(
                source="youtube",
                post_id=thread["id"],
                url=f"https://www.youtube.com/watch?v={video_id}&lc={thread['id']}",
                text=comment.get("textDisplay", ""),
                created_at=comment.get("publishedAt", ""),
            )
        )
    return posts


def fetch_youtube_comments(queries: list[str] = config.YOUTUBE_QUERIES) -> list[Post]:
    """Return top comments from the most relevant videos for each query, without duplicates."""
    try:
        video_ids = list(dict.fromkeys(video for query in queries for video in _find_videos(query)))
    except requests.RequestException as error:
        logger.warning("YouTube search failed: %s", error)
        return []

    posts: dict[str, Post] = {}
    for video_id in video_ids:
        try:
            comments = _fetch_comments(video_id)
        except requests.RequestException as error:
            # Videos with comments turned off return an error, so they are skipped
            logger.warning("Skipping comments for video %s: %s", video_id, error)
            continue
        posts.update({post.post_id: post for post in comments})
    return list(posts.values())