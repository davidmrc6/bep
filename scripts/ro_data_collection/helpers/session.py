import os

from dotenv import load_dotenv
from requests import Session


def create_session() -> Session:
    load_dotenv()
    token = os.getenv("GH_TOKEN")
    session = Session()
    session.headers.update({
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
        "Authorization": f"Bearer {token}",
    })
    return session
