"""
Grant deduplication using content hashing.

Implements hash-based deduplication with priority merge for
handling the same grant from multiple sources.
"""

import hashlib
from dataclasses import dataclass
from typing import Optional

import structlog

from .models import Grant

logger = structlog.get_logger(__name__)


def generate_content_hash(
    source_id: str,
    url: str,
    title: str,
    deadline: Optional[str] = None,
) -> str:
    """
    Generate SHA-256 hash for grant deduplication.

    Hash is based on:
    - source_id: Source identifier
    - url: Grant URL (normalized)
    - title: Grant title (normalized)
    - deadline: Deadline date (optional, ISO format)

    Args:
        source_id: Source identifier (e.g., "mzd_gov")
        url: Grant URL
        title: Grant title
        deadline: Optional deadline in ISO format

    Returns:
        SHA-256 hex digest
    """
    # Normalize inputs
    normalized_url = url.lower().rstrip("/")
    normalized_title = title.lower().strip()
    deadline_str = deadline or ""

    # Build hash content
    content = f"{source_id}|{normalized_url}|{normalized_title}|{deadline_str}"

    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass
class DeduplicationResult:
    """Result of deduplication check."""
    is_duplicate: bool
    existing_hash: Optional[str] = None
    action: str = "keep"  # keep, skip, merge


class Deduplicator:
    """
    Hash-based grant deduplicator.

    Tracks seen grants by content hash and provides merge
    strategies for handling duplicates from different sources.
    """

    # Source priority for merging (higher = preferred)
    SOURCE_PRIORITY = {
        "dotaceeu": 10,  # Aggregator - base data
        "opst": 20,
        "opzp": 20,
        "irop": 20,
        "mzd_gov": 30,
        "mze_szif": 30,
        "mfcr": 30,
        "msmt": 30,
        "mvcr": 30,
    }

    def __init__(self):
        """Initialize deduplicator with empty hash store."""
        self._seen_hashes: dict[str, Grant] = {}
        self._url_index: dict[str, str] = {}  # url -> hash

    def check(self, grant: Grant) -> DeduplicationResult:
        """
        Check if grant is a duplicate.

        Args:
            grant: Grant to check

        Returns:
            DeduplicationResult with action to take
        """
        # Generate hash if not present
        if not grant.content_hash:
            grant.content_hash = generate_content_hash(
                source_id=grant.source_id,
                url=grant.grant_url,
                title=grant.title,
                deadline=grant.deadline.isoformat() if grant.deadline else None,
            )

        content_hash = grant.content_hash

        # Check by hash
        if content_hash in self._seen_hashes:
            existing = self._seen_hashes[content_hash]
            return DeduplicationResult(
                is_duplicate=True,
                existing_hash=content_hash,
                action=self._determine_action(existing, grant),
            )

        # Check by URL (different hash but same URL)
        normalized_url = grant.grant_url.lower().rstrip("/")
        if normalized_url in self._url_index:
            existing_hash = self._url_index[normalized_url]
            existing = self._seen_hashes.get(existing_hash)
            if existing:
                return DeduplicationResult(
                    is_duplicate=True,
                    existing_hash=existing_hash,
                    action=self._determine_action(existing, grant),
                )

        return DeduplicationResult(is_duplicate=False, action="keep")

    def add(self, grant: Grant) -> None:
        """
        Add grant to deduplication index.

        Args:
            grant: Grant to add
        """
        if not grant.content_hash:
            grant.content_hash = generate_content_hash(
                source_id=grant.source_id,
                url=grant.grant_url,
                title=grant.title,
                deadline=grant.deadline.isoformat() if grant.deadline else None,
            )

        self._seen_hashes[grant.content_hash] = grant
        normalized_url = grant.grant_url.lower().rstrip("/")
        self._url_index[normalized_url] = grant.content_hash

        logger.debug(
            "grant_indexed",
            hash=grant.content_hash[:8],
            url=grant.grant_url,
            title=grant.title[:50],
        )

    def process(self, grant: Grant) -> Optional[Grant]:
        """
        Process grant through deduplication.

        Combines check and add in one operation.

        Args:
            grant: Grant to process

        Returns:
            Grant if should be kept, None if duplicate to skip
        """
        result = self.check(grant)

        if result.is_duplicate:
            if result.action == "skip":
                logger.debug(
                    "grant_skipped_duplicate",
                    hash=grant.content_hash[:8] if grant.content_hash else "N/A",
                    url=grant.grant_url,
                )
                return None
            elif result.action == "merge":
                existing = self._seen_hashes.get(result.existing_hash or "")
                if existing:
                    merged = self._merge_grants(existing, grant)
                    self._seen_hashes[result.existing_hash or ""] = merged
                    logger.info(
                        "grant_merged",
                        hash=result.existing_hash[:8] if result.existing_hash else "N/A",
                        sources=f"{existing.source_id}+{grant.source_id}",
                    )
                    return None

        self.add(grant)
        return grant

    def get_all(self) -> list[Grant]:
        """Get all unique grants."""
        return list(self._seen_hashes.values())

    def clear(self) -> None:
        """Clear deduplication index."""
        self._seen_hashes.clear()
        self._url_index.clear()

    def _determine_action(self, existing: Grant, new: Grant) -> str:
        """
        Determine action for duplicate.

        Args:
            existing: Existing grant in index
            new: New grant being checked

        Returns:
            Action: "skip" or "merge"
        """
        existing_priority = self.SOURCE_PRIORITY.get(existing.source_id, 0)
        new_priority = self.SOURCE_PRIORITY.get(new.source_id, 0)

        # If new has higher priority, merge (new data overwrites)
        if new_priority > existing_priority:
            return "merge"

        # Otherwise skip the new one
        return "skip"

    def _merge_grants(self, existing: Grant, new: Grant) -> Grant:
        """
        Merge two grants, preferring data from higher priority source.

        Args:
            existing: Existing grant
            new: New grant with higher priority

        Returns:
            Merged grant
        """
        # Start with new grant (higher priority)
        merged = Grant(
            source_id=new.source_id,
            source_name=new.source_name,
            source_url=new.source_url,
            grant_url=new.grant_url,
            title=new.title or existing.title,
            description=new.description or existing.description,
            summary=new.summary or existing.summary,
            funding_amount=new.funding_amount or existing.funding_amount,
            deadline=new.deadline or existing.deadline,
            application_start=new.application_start or existing.application_start,
            application_end=new.application_end or existing.application_end,
            grant_type=new.grant_type,
            status=new.status,
            eligibility=new.eligibility or existing.eligibility,
            eligible_recipients=new.eligible_recipients or existing.eligible_recipients,
            contact_email=new.contact_email or existing.contact_email,
            contact_phone=new.contact_phone or existing.contact_phone,
            regions=new.regions or existing.regions,
            categories=new.categories or existing.categories,
            documents=new.documents or existing.documents,
            application_url=new.application_url or existing.application_url,
            content_hash=new.content_hash,
            extracted_at=new.extracted_at,
        )

        # Merge additional metadata
        merged.additional_metadata = {
            **existing.additional_metadata,
            **new.additional_metadata,
            "_merged_from": [existing.source_id, new.source_id],
        }

        return merged

    def __len__(self) -> int:
        """Return number of unique grants."""
        return len(self._seen_hashes)
