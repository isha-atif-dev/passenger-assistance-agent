"""Central settings: API keys, model names, paths, search terms and run limits."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
INPUTS_DIR = ROOT_DIR / "inputs"
OUTPUTS_DIR = ROOT_DIR / "outputs"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE")
BLUESKY_APP_PASSWORD = os.getenv("BLUESKY_APP_PASSWORD")

GEMINI_MODEL = "gemini-flash-lite-latest"
GROQ_MODEL = "openai/gpt-oss-20b"

REQUEST_TIMEOUT = 60
LLM_TIMEOUT = 30
MAX_ITEMS_PER_SOURCE = 15
BLUESKY_RESULTS_PER_QUERY = 10

# Passenger Assistance app on the UK App Store
APP_STORE_APP_ID = 1542190496

BLUESKY_QUERIES = [
    '"passenger assist"',
    '"assisted travel" train',
    "wheelchair train assistance",
    '"Passenger Assistance" app',
]

WEB_QUERIES = [
    "Passenger Assist UK rail assistance did not turn up passenger experience",
    "UK train wheelchair assistance left stranded forum",
    "Passenger Assistance app review problems rail",
]

YOUTUBE_QUERIES = [
    "Passenger Assist train wheelchair assistance UK",
    "Passenger Assistance app rail",
]
YOUTUBE_VIDEOS_PER_QUERY = 3
YOUTUBE_COMMENTS_PER_VIDEO = 10