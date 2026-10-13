"""Smoke tests for external API connections.

Run from the project root:
    python tests/test_setup.py
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
TAVILY_URL = "https://api.tavily.com/search"
HN_URL = "https://hn.algolia.com/api/v1/search"
BLUESKY_LOGIN_URL = "https://bsky.social/xrpc/com.atproto.server.createSession"
BLUESKY_SEARCH_URL = "https://bsky.social/xrpc/app.bsky.feed.searchPosts"
YOUTUBE_URL = "https://www.googleapis.com/youtube/v3/search"
APPLE_SEARCH_URL = "https://itunes.apple.com/search"
APPLE_REVIEWS_URL = "https://itunes.apple.com/gb/rss/customerreviews/id={app_id}/sortBy=mostRecent/json"


def test_gemini():
    """Send a minimal prompt to Gemini and report whether the key is valid."""
    key = os.getenv("GEMINI_API_KEY")
    body = {"contents": [{"parts": [{"text": "Say hello in five words."}]}]}

    try:
        response = requests.post(GEMINI_URL, headers={"x-goog-api-key": key}, json=body, timeout=90)
    except requests.exceptions.RequestException as error:
        print("Gemini: NOT WORKING ->", type(error).__name__)
        return

    if response.status_code == 200:
        reply = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        print("Gemini: WORKING ->", reply.strip())
    else:
        # Truncate the error body to keep the output readable
        print("Gemini: NOT WORKING ->", response.status_code, response.text[:200])

def test_groq():
    """Send a minimal prompt to Groq and report whether the key is valid."""
    key = os.getenv("GROQ_API_KEY")
    body = {
        "model": "openai/gpt-oss-20b",
        "messages": [{"role": "user", "content": "Say hello in five words."}],
    }

    try:
        response = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {key}"}, json=body, timeout=60)
    except requests.exceptions.RequestException as error:
        print("Groq: NOT WORKING ->", type(error).__name__)
        return

    if response.status_code == 200:
        reply = response.json()["choices"][0]["message"]["content"]
        print("Groq: WORKING ->", reply.strip())
    else:
        print("Groq: NOT WORKING ->", response.status_code, response.text[:200])


def test_tavily():
    """Run one web search through Tavily and report whether the key is valid."""
    key = os.getenv("TAVILY_API_KEY")
    body = {"query": "Passenger Assistance app", "max_results": 3}

    try:
        response = requests.post(TAVILY_URL, headers={"Authorization": f"Bearer {key}"}, json=body, timeout=60)
    except requests.exceptions.RequestException as error:
        print("Tavily: NOT WORKING ->", type(error).__name__)
        return

    if response.status_code == 200:
        results = response.json()["results"]
        print(f"Tavily: WORKING -> {len(results)} results, first: {results[0]['title']}")
    else:
        print("Tavily: NOT WORKING ->", response.status_code, response.text[:200])




def test_hackernews():
    """Search Hacker News through the Algolia API, which needs no key."""
    params = {"query": "accessibility", "hitsPerPage": 3}

    try:
        response = requests.get(HN_URL, params=params, timeout=30)
    except requests.exceptions.RequestException as error:
        print("Hacker News: NOT WORKING ->", type(error).__name__)
        return

    if response.status_code == 200:
        hits = response.json()["hits"]
        print(f"Hacker News: WORKING -> {len(hits)} results, first: {hits[0]['title']}")
    else:
        print("Hacker News: NOT WORKING ->", response.status_code, response.text[:200])


def test_bluesky():
    """Log in to Bluesky with an app password, then run one post search."""
    credentials = {
        "identifier": os.getenv("BLUESKY_HANDLE"),
        "password": os.getenv("BLUESKY_APP_PASSWORD"),
    }
    params = {"q": "train accessibility", "limit": 3}

    try:
        login = requests.post(BLUESKY_LOGIN_URL, json=credentials, timeout=30)
        if login.status_code != 200:
            print("Bluesky: NOT WORKING -> login failed", login.status_code, login.text[:200])
            return

        # The login returns a short-lived token that authorises the search
        token = login.json()["accessJwt"]
        response = requests.get(
            BLUESKY_SEARCH_URL, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=30
        )
    except requests.exceptions.RequestException as error:
        print("Bluesky: NOT WORKING ->", type(error).__name__)
        return

    if response.status_code == 200:
        posts = response.json()["posts"]
        first = posts[0]["record"]["text"][:60] if posts else "no posts found"
        print(f"Bluesky: WORKING -> {len(posts)} results, first: {first}")
    else:
        print("Bluesky: NOT WORKING ->", response.status_code, response.text[:200])

def test_youtube():
    """Run one video search through the YouTube Data API."""
    params = {
        "part": "snippet",
        "q": "passenger assistance rail",
        "type": "video",
        "maxResults": 3,
        "key": os.getenv("YOUTUBE_API_KEY"),
    }

    try:
        response = requests.get(YOUTUBE_URL, params=params, timeout=30)
    except requests.exceptions.RequestException as error:
        print("YouTube: NOT WORKING ->", type(error).__name__)
        return

    if response.status_code == 200:
        items = response.json()["items"]
        first = items[0]["snippet"]["title"] if items else "no videos found"
        print(f"YouTube: WORKING -> {len(items)} results, first: {first}")
    else:
        print("YouTube: NOT WORKING ->", response.status_code, response.text[:200])


def test_langfuse():
    """Check the Langfuse keys by asking which project they belong to."""
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    keys = (os.getenv("LANGFUSE_PUBLIC_KEY"), os.getenv("LANGFUSE_SECRET_KEY"))

    try:
        response = requests.get(f"{host}/api/public/projects", auth=keys, timeout=30)
    except requests.exceptions.RequestException as error:
        print("Langfuse: NOT WORKING ->", type(error).__name__)
        return

    if response.status_code == 200:
        project = response.json()["data"][0]["name"]
        print("Langfuse: WORKING -> project:", project)
    else:
        print("Langfuse: NOT WORKING ->", response.status_code, response.text[:200])


def test_app_store():
    """Look up an app on the Apple App Store, then fetch its recent reviews."""
    params = {"term": "Passenger Assistance", "country": "gb", "entity": "software", "limit": 1}

    try:
        search = requests.get(APPLE_SEARCH_URL, params=params, timeout=30)
        apps = search.json().get("results", []) if search.status_code == 200 else []
        if not apps:
            print("App Store: NOT WORKING -> app lookup failed", search.status_code)
            return

        app = apps[0]
        response = requests.get(APPLE_REVIEWS_URL.format(app_id=app["trackId"]), timeout=30)
    except requests.exceptions.RequestException as error:
        print("App Store: NOT WORKING ->", type(error).__name__)
        return

    if response.status_code == 200:
        # The feed omits "entry" entirely when it has no reviews to return
        reviews = response.json()["feed"].get("entry", [])
        first = reviews[0]["title"]["label"] if reviews else "no reviews returned"
        print(f"App Store: WORKING -> {app['trackName']}, {len(reviews)} reviews, first: {first}")
    else:
        print("App Store: NOT WORKING ->", response.status_code, response.text[:200])



if __name__ == "__main__":
    test_gemini()
    test_groq()
    test_tavily()
    test_hackernews()
    test_bluesky()
    test_youtube()
    test_langfuse()
    test_app_store()