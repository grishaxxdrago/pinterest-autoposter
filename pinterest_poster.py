"""
Pinterest Auto-Poster
=====================
Posts 5 images per day to Pinterest from the /images folder.
Tracks what's been posted in queue.json (committed back to repo).
"""

import os
import json
import requests
from pathlib import Path
from datetime import datetime


PINTEREST_CLIENT_ID     = os.environ["PINTEREST_CLIENT_ID"]
PINTEREST_CLIENT_SECRET = os.environ["PINTEREST_CLIENT_SECRET"]
PINTEREST_REFRESH_TOKEN = os.environ["PINTEREST_REFRESH_TOKEN"]
PINTEREST_BOARD_ID      = os.environ["PINTEREST_BOARD_ID"]
GITHUB_REPOSITORY       = os.environ["GITHUB_REPOSITORY"]
GITHUB_BRANCH           = os.environ.get("GITHUB_REF_NAME", "main")

IMAGES_PER_DAY = 5
QUEUE_FILE     = "queue.json"
IMAGES_DIR     = Path("images")
SUPPORTED_EXT  = {".jpg", ".jpeg", ".png", ".webp"}


def refresh_access_token():
    resp = requests.post(
        "https://api.pinterest.com/v5/oauth/token",
        auth=(PINTEREST_CLIENT_ID, PINTEREST_CLIENT_SECRET),
        data={
            "grant_type":    "refresh_token",
            "refresh_token": PINTEREST_REFRESH_TOKEN,
            "scope":         "boards:read,pins:read,pins:write",
        },
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    print("Access token refreshed")
    return token


def raw_github_url(filename):
    return f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/{GITHUB_BRANCH}/images/{filename}"


def post_pin(access_token, image_url, title="", description=""):
    resp = requests.post(
        "https://api.pinterest.com/v5/pins",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  "application/json",
        },
        json={
            "board_id":     PINTEREST_BOARD_ID,
            "title":        title,
            "description":  description,
            "media_source": {
                "source_type": "image_url",
                "url":         image_url,
            },
        },
    )
    return resp


def load_queue():
    if Path(QUEUE_FILE).exists():
        with open(QUEUE_FILE, encoding="utf-8") as f:
            return json.load(f)
    all_images = sorted(
        p.name for p in IMAGES_DIR.iterdir()
        if p.suffix.lower() in SUPPORTED_EXT
    )
    print(f"First run - {len(all_images)} images found in /images")
    return {"pending": all_images, "posted": []}


def save_queue(data):
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    print(f"Pinterest Auto-Poster - {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    access_token = refresh_access_token()
    queue = load_queue()
    pending = queue["pending"]
    posted  = queue["posted"]

    if not pending:
        print("No more images to post!")
        return

    to_post   = pending[:IMAGES_PER_DAY]
    remaining = pending[IMAGES_PER_DAY:]
    print(f"Images to post today: {len(to_post)}")

    success_count = 0
    failed_images = []

    for filename in to_post:
        image_url = raw_github_url(filename)
        print(f"  Posting: {filename}")
        resp = post_pin(access_token, image_url)
        if resp.status_code in (200, 201):
            pin_id = resp.json().get("id", "?")
            print(f"  Success - Pin ID: {pin_id}")
            posted.append({
                "filename":  filename,
                "posted_at": datetime.utcnow().isoformat(),
                "pin_id":    pin_id,
            })
            success_count += 1
        else:
            print(f"  Failed ({resp.status_code}): {resp.text}")
            failed_images.append(filename)

    queue["pending"] = failed_images + remaining
    queue["posted"]  = posted
    save_queue(queue)
    print(f"Done: {success_count}/{len(to_post)} pins posted")

    if success_count < len(to_post):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
