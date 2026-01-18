"""
Async HTTP client with rate limiting, retries, and caching.

Built on httpx with:
- Per-domain rate limiting
- Exponential backoff retry
- Response caching (TTL-based)
- User-agent rotation
"""

import asyncio
import hashlib
import os
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

import httpx
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = structlog.get_logger(__name__)


# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]


@dataclass
class CacheEntry:
    """Cached HTTP response."""
    content: bytes
    status_code: int
    headers: dict
    timestamp: float
    ttl: int


@dataclass
class RateLimiter:
    """Per-domain rate limiter."""
    requests_per_second: float = 2.0
    last_request: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def acquire(self) -> None:
        """Wait for rate limit slot."""
        async with self.lock:
            now = time.monotonic()
            min_interval = 1.0 / self.requests_per_second
            elapsed = now - self.last_request

            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)

            self.last_request = time.monotonic()


class HttpClient:
    """
    Async HTTP client with rate limiting, retries, and caching.

    Usage:
        async with HttpClient() as client:
            response = await client.get("https://example.com")
            html = response.text
    """

    def __init__(
        self,
        requests_per_second: float = 2.0,
        timeout: float = 30.0,
        cache_ttl: int = 300,
        max_retries: int = 3,
        enable_cache: bool = True,
    ):
        """
        Initialize HTTP client.

        Args:
            requests_per_second: Rate limit per domain
            timeout: Request timeout in seconds
            cache_ttl: Cache TTL in seconds
            max_retries: Maximum retry attempts
            enable_cache: Enable response caching
        """
        self.requests_per_second = requests_per_second
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self.max_retries = max_retries
        self.enable_cache = enable_cache

        self._client: Optional[httpx.AsyncClient] = None
        self._rate_limiters: dict[str, RateLimiter] = {}
        self._cache: dict[str, CacheEntry] = {}
        self._user_agent_index = 0

    async def __aenter__(self) -> "HttpClient":
        """Enter async context."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
            headers={"Accept-Language": "cs,en;q=0.9"},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_rate_limiter(self, url: str) -> RateLimiter:
        """Get or create rate limiter for domain."""
        domain = urlparse(url).netloc
        if domain not in self._rate_limiters:
            self._rate_limiters[domain] = RateLimiter(
                requests_per_second=self.requests_per_second
            )
        return self._rate_limiters[domain]

    def _get_user_agent(self) -> str:
        """Get next user agent in rotation."""
        ua = USER_AGENTS[self._user_agent_index % len(USER_AGENTS)]
        self._user_agent_index += 1
        return ua

    def _cache_key(self, url: str) -> str:
        """Generate cache key for URL."""
        return hashlib.md5(url.encode()).hexdigest()

    def _get_cached(self, url: str) -> Optional[CacheEntry]:
        """Get cached response if valid."""
        if not self.enable_cache:
            return None

        key = self._cache_key(url)
        entry = self._cache.get(key)

        if entry is None:
            return None

        # Check TTL
        if time.time() - entry.timestamp > entry.ttl:
            del self._cache[key]
            return None

        return entry

    def _set_cached(self, url: str, response: httpx.Response) -> None:
        """Cache response."""
        if not self.enable_cache:
            return

        key = self._cache_key(url)
        self._cache[key] = CacheEntry(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            timestamp=time.time(),
            ttl=self.cache_ttl,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def _do_request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> httpx.Response:
        """Execute HTTP request with retry."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context.")

        # Add user agent
        headers = kwargs.pop("headers", {})
        headers["User-Agent"] = self._get_user_agent()

        response = await self._client.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()

        return response

    async def get(
        self,
        url: str,
        use_cache: bool = True,
        **kwargs,
    ) -> httpx.Response:
        """
        GET request with rate limiting and caching.

        Args:
            url: URL to fetch
            use_cache: Whether to use cache
            **kwargs: Additional httpx arguments

        Returns:
            httpx.Response object
        """
        # Check cache
        if use_cache:
            cached = self._get_cached(url)
            if cached:
                logger.debug("cache_hit", url=url)
                # Return mock response with cached data
                return httpx.Response(
                    status_code=cached.status_code,
                    headers=cached.headers,
                    content=cached.content,
                )

        # Rate limit
        limiter = self._get_rate_limiter(url)
        await limiter.acquire()

        logger.debug("http_get", url=url)

        response = await self._do_request("GET", url, **kwargs)

        # Cache successful responses
        if response.status_code == 200:
            self._set_cached(url, response)

        return response

    async def get_text(self, url: str, **kwargs) -> str:
        """GET request returning text content."""
        response = await self.get(url, **kwargs)
        return response.text

    async def get_bytes(self, url: str, **kwargs) -> bytes:
        """GET request returning bytes content."""
        response = await self.get(url, **kwargs)
        return response.content

    async def download(
        self,
        url: str,
        save_path: str,
        chunk_size: int = 8192,
    ) -> bool:
        """
        Download file to disk.

        Args:
            url: URL to download
            save_path: Path to save file
            chunk_size: Download chunk size

        Returns:
            True if successful
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context.")

        # Rate limit
        limiter = self._get_rate_limiter(url)
        await limiter.acquire()

        logger.info("downloading", url=url, path=save_path)

        try:
            async with self._client.stream("GET", url) as response:
                response.raise_for_status()

                # Ensure directory exists
                os.makedirs(os.path.dirname(save_path), exist_ok=True)

                with open(save_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size):
                        f.write(chunk)

            logger.info("download_complete", url=url, path=save_path)
            return True

        except Exception as e:
            logger.error("download_failed", url=url, error=str(e))
            return False

    def clear_cache(self) -> None:
        """Clear response cache."""
        self._cache.clear()

    @property
    def cache_size(self) -> int:
        """Return number of cached responses."""
        return len(self._cache)


# Convenience function for one-off requests
async def fetch(url: str, **kwargs) -> str:
    """
    Fetch URL content (convenience function).

    Args:
        url: URL to fetch
        **kwargs: Additional arguments for HttpClient

    Returns:
        Response text
    """
    async with HttpClient(**kwargs) as client:
        return await client.get_text(url)
