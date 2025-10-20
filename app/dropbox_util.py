# app/dropbox_util.py
from __future__ import annotations

import os
import base64
from typing import List, Dict, Optional
import dropbox

# -------------------------
# Configuration / Client
# -------------------------

# You can override these with environment variables in prod
DROPBOX_REFRESH_TOKEN = os.getenv(
    "DROPBOX_REFRESH_TOKEN",
    "YjUT_g2Om4wAAAAAAAAAATogIV7e_NrU4uRcaIfo2WUOxiTwfg-brX6-3u5M991-",
)
DROPBOX_APP_KEY = os.getenv("DROPBOX_APP_KEY", "078cfveyiewj0ay")
DROPBOX_APP_SECRET = os.getenv("DROPBOX_APP_SECRET", "9h1uxluft07vap1")

# Single shared Dropbox client (lazy-created)
_dbx_client: Optional[dropbox.Dropbox] = None


def get_dbx() -> dropbox.Dropbox:
    """Return a singleton Dropbox client."""
    global _dbx_client
    if _dbx_client is None:
        _dbx_client = dropbox.Dropbox(
            oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
            app_key=DROPBOX_APP_KEY,
            app_secret=DROPBOX_APP_SECRET,
        )
    return _dbx_client


# For legacy imports elsewhere:
dbx = get_dbx()

# -------------------------
# Path building
# -------------------------

def build_dropbox_folder_path(
    insurance: str | None,
    claim_type: str | None,
    last_name: str | None,
    first_name: str | None,
    id_number: str | None,
    claim_number: str | None,
) -> str | None:
    """
    Replicates the path convention used when the insured folder is created.
    Returns a Dropbox path like:
      /360/ביטוח/<insurance>/<claim_type>/<folder_name>
    or None when we don't know how to build it.
    """
    base_path = f"/360/ביטוח/{(insurance or '').strip()}/{(claim_type or '').strip()}"
    full_name = f"{(last_name or '').strip()} {(first_name or '').strip()}".strip()

    if not full_name:
        return None

    if insurance == "מנורה":
        if not (id_number and claim_number):
            return None
        folder_name = f"{full_name} - {id_number} - {claim_number}"
    elif insurance == "הפניקס":
        if not claim_number:
            return None
        folder_name = f"{full_name} - {claim_number}"
    elif insurance == "שלמה" and claim_type == "אכע":
        if not (id_number and claim_number):
            return None
        folder_name = f"{full_name} - {id_number} - {claim_number}"
    elif insurance == "איילון" and claim_type == "אכע":
        if not (id_number and claim_number):
            return None
        folder_name = f"{full_name} - {id_number} - {claim_number}"
    else:
        return None

    # Normalize slashes
    return "/" + "/".join(p.strip("/") for p in [base_path, folder_name] if p)

# -------------------------
# Photos listing
# -------------------------

PHOTOS_SUBFOLDER = "תמונות"
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}

# Thumbnails: ~1024px on the long side – a good compromise for speed/clarity.
THUMB_FORMAT = dropbox.files.ThumbnailFormat.jpeg
THUMB_SIZE = dropbox.files.ThumbnailSize.w1024h768  # works fine for both orientations
THUMB_MODE = dropbox.files.ThumbnailMode.strict


def _is_image_filename(name: str) -> bool:
    n = name.lower()
    return any(n.endswith(ext.lower()) for ext in ALLOWED_EXTS)


def _join_dropbox(*parts: str) -> str:
    parts = [p.strip("/") for p in parts if p and p.strip("/")]
    if not parts:
        return "/"
    out = "/".join(parts)
    return out if out.startswith("/") else "/" + out


def _make_thumb_data_url(dbx_client: dropbox.Dropbox, path_lower: str) -> Optional[str]:
    """
    Try to fetch a JPEG thumbnail from Dropbox and return it as a data URL.
    If thumbnail generation fails, return None (caller can fall back to full URL).
    """
    try:
        # files_get_thumbnail returns an HTTP-like response with .content (bytes)
        resp = dbx_client.files_get_thumbnail(
            path_lower,
            format=THUMB_FORMAT,
            size=THUMB_SIZE,
            mode=THUMB_MODE,
        )
        b64 = base64.b64encode(resp.content).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception:
        return None


def list_images_in_folder(dbx_client: dropbox.Dropbox, folder_path: str) -> List[Dict]:
    """
    Return a list of dicts for image files directly under folder_path (non-recursive):
      { 'name': <file>, 'url': <temporary link>, 'thumb_data_url': <base64 data URL (optional)> }
    If the folder doesn't exist, returns [].
    """
    images: List[Dict] = []
    try:
        res = dbx_client.files_list_folder(folder_path)
    except dropbox.exceptions.ApiError:
        return images

    entries = list(res.entries)
    while res.has_more:
        res = dbx_client.files_list_folder_continue(res.cursor)
        entries.extend(res.entries)

    for e in entries:
        if isinstance(e, dropbox.files.FileMetadata) and _is_image_filename(e.name):
            try:
                # Full-res temporary download link (unchanged behavior)
                link = dbx_client.files_get_temporary_link(e.path_lower).link
            except dropbox.exceptions.ApiError:
                continue

            item: Dict[str, str] = {"name": e.name, "url": link}

            # New: add a lightweight thumbnail to speed up the UI
            thumb = _make_thumb_data_url(dbx_client, e.path_lower)
            if thumb:
                item["thumb_data_url"] = thumb

            images.append(item)

    return images


def list_case_images(
    dbx_client: dropbox.Dropbox,
    case_root: str,
) -> List[Dict]:
    """
    Given the 'case root' (the insured's standard folder), return images from the
    fixed subfolder '<case_root>/תמונות'.
    """
    if not case_root:
        return []
    photos_path = _join_dropbox(case_root, PHOTOS_SUBFOLDER)
    return list_images_in_folder(dbx_client, photos_path)
