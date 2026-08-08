"""
Instagram data-access layer.

IMPORTANT: Instagram has no official public API for arbitrary reels/profile
scraping. This module uses Instagram's public web/mobile JSON endpoints as a
default implementation (with instaloader as a download fallback). It is
rate-limited by Instagram and can fail, or get an account flagged, if used
aggressively. This module is intentionally isolated behind a small function
surface (get_profile_reels / download_reel_video) so it can be swapped for an
official/licensed data provider, or for another platform (YouTube, X, Telegram)
later, without touching the rest of the app.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

import instaloader
import requests

from app.config import settings

_IG_APP_ID = "936619743392459"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

_session: Optional[requests.Session] = None
_L = None


def _web_session() -> requests.Session:
    """Shared anonymous web session with the headers Instagram expects."""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(
            {
                "User-Agent": _USER_AGENT,
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "X-IG-App-ID": _IG_APP_ID,
                "X-ASBD-ID": "359341",
                "X-Requested-With": "XMLHttpRequest",
            }
        )
        # Warm cookies (csrftoken / mid) — required by several endpoints.
        _session.get("https://www.instagram.com/", timeout=30)
    csrf = _session.cookies.get("csrftoken")
    if csrf:
        _session.headers["X-CSRFToken"] = csrf
    return _session


def _loader() -> instaloader.Instaloader:
    global _L
    if _L is None:
        _L = instaloader.Instaloader(
            download_videos=True,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            post_metadata_txt_pattern="",
            quiet=True,
        )
        if settings.instagram_username and settings.instagram_password:
            try:
                _L.login(settings.instagram_username, settings.instagram_password)
            except Exception as e:
                print(f"[instagram_service] login failed, continuing anonymously: {e}")
    return _L


def _thumbnail_url(item: dict) -> str:
    candidates = (item.get("image_versions2") or {}).get("candidates") or []
    if candidates:
        return candidates[0].get("url") or ""
    return item.get("display_uri") or ""


def _video_url(item: dict) -> Optional[str]:
    versions = item.get("video_versions") or []
    if not versions:
        return None
    # Prefer highest bandwidth / width when available.
    best = max(
        versions,
        key=lambda v: (v.get("bandwidth") or 0, v.get("width") or 0),
    )
    return best.get("url")


def _is_video_item(item: dict) -> bool:
    # media_type: 1=photo, 2=video, 8=carousel
    if item.get("media_type") == 2:
        return True
    if item.get("product_type") in ("clips", "reel", "igtv"):
        return True
    return bool(item.get("video_versions"))


def _feed_page(username: str, count: int = 12, max_id: Optional[str] = None) -> dict:
    """
    Fetch a page of posts via the mobile feed endpoint.

    This bypasses api/v1/users/web_profile_info/, which currently 400s for many
    business/creator accounts with the deleted ig_business_category_subvertical
    schema error.
    """
    session = _web_session()
    params: dict[str, Any] = {"count": count}
    if max_id:
        params["max_id"] = max_id
    url = f"https://www.instagram.com/api/v1/feed/user/{username}/username/"
    resp = session.get(
        url,
        params=params,
        headers={"Referer": f"https://www.instagram.com/{username}/"},
        timeout=45,
    )
    if resp.status_code == 404:
        raise ValueError(f"Profile '{username}' not found")
    if resp.status_code != 200:
        raise ValueError(
            f"Instagram feed request failed ({resp.status_code}): {resp.text[:240]}"
        )
    data = resp.json()
    if data.get("status") == "fail":
        raise ValueError(data.get("message") or "Instagram feed request failed")
    return data


def get_profile_reels(username: str, limit: int = 100):
    """Return (list of reel metadata dicts, profile display name) for a public profile."""
    username = username.strip().lstrip("@").lower()
    reels: list[dict] = []
    display_name = username
    max_id: Optional[str] = None
    pages = 0
    max_pages = max(1, (limit + 11) // 12 + 2)

    while len(reels) < limit and pages < max_pages:
        data = _feed_page(username, count=12, max_id=max_id)
        pages += 1

        user = data.get("user") or {}
        if user.get("full_name"):
            display_name = user["full_name"]
        if user.get("username"):
            # Keep canonical casing from Instagram when available.
            username = user["username"]

        if user.get("is_private") and not data.get("items"):
            raise ValueError(f"Profile '{username}' is private")

        for item in data.get("items") or []:
            if not _is_video_item(item):
                continue
            code = item.get("code")
            if not code:
                continue
            caption = ((item.get("caption") or {}).get("text") or "").strip()
            taken_at = item.get("taken_at")
            posted_at = (
                datetime.fromtimestamp(taken_at, tz=timezone.utc)
                if taken_at
                else datetime.now(timezone.utc)
            )
            reels.append(
                {
                    "reel_id": code,
                    "title": caption[:120] or "(untitled reel)",
                    "caption": caption,
                    "thumbnail": _thumbnail_url(item),
                    "reel_url": f"https://www.instagram.com/reel/{code}/",
                    "posted_at": posted_at,
                    "video_url": _video_url(item),
                    "media_pk": str(item.get("pk") or item.get("id") or ""),
                }
            )
            if len(reels) >= limit:
                break

        if not data.get("more_available") or not data.get("next_max_id"):
            break
        max_id = data["next_max_id"]

    return reels, display_name or username


def _download_url(url: str, dest_path: str) -> str:
    session = _web_session()
    with session.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)
    return dest_path


def download_reel_video(shortcode: str, dest_dir: str, video_url: Optional[str] = None) -> str:
    """Download a single reel's video by shortcode. Returns local .mp4 path."""
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, f"{shortcode}.mp4")

    if video_url:
        try:
            return _download_url(video_url, dest_path)
        except Exception as e:
            print(f"[instagram_service] stored CDN URL failed for {shortcode}: {e}")

    # Resolve via instaloader shortcode lookup (still works even when web_profile_info does not).
    L = _loader()
    post = instaloader.Post.from_shortcode(L.context, shortcode)
    if getattr(post, "video_url", None):
        return _download_url(post.video_url, dest_path)

    L.download_post(post, target=dest_dir)
    for f in os.listdir(dest_dir):
        if f.endswith(".mp4"):
            return os.path.join(dest_dir, f)
    raise FileNotFoundError(f"No video file found after downloading reel {shortcode}")
