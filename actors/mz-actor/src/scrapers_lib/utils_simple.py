"""
Simplified document utilities - only download, no conversion (MVP).
"""

import logging
from pathlib import Path

import requests

# Well-named semantic constants
DOWNLOAD_CHUNK_SIZE_BYTES = 8192
DEFAULT_DOWNLOAD_TIMEOUT_SECONDS = 30

logger = logging.getLogger(__name__)


def download_document(url: str, save_path: str, timeout: int = DEFAULT_DOWNLOAD_TIMEOUT_SECONDS) -> bool:
    """
    Download document from URL to local path.

    Args:
        url: Full URL to document
        save_path: Absolute path where file should be saved
        timeout: Request timeout in seconds

    Returns:
        True if download succeeded, False otherwise
    """
    try:
        save_path_obj = Path(save_path)
        save_path_obj.parent.mkdir(parents=True, exist_ok=True)

        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()

        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE_BYTES):
                if chunk:
                    f.write(chunk)

        logger.info(f"Downloaded: {url} → {save_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        return False
