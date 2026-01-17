"""
Storage managers for Dataset and Key-Value Store.

Handles interaction with Apify storage systems for dataset records
and metadata (lastFetchedAt timestamps).
"""

import os
from typing import Dict, List, Optional
from datetime import datetime, timezone

from apify import Actor


# Configurable dataset name
DATASET_NAME = os.getenv('DATASET_NAME', 'czech-grants')


class DatasetManager:
    """Manager for Apify Dataset operations"""

    def __init__(self, dataset_name: str = DATASET_NAME):
        """
        Initialize dataset manager.

        Args:
            dataset_name: Name of the dataset (default from env or 'czech-grants')
        """
        self.dataset_name = dataset_name

    async def push(self, record: Dict) -> None:
        """
        Push record to named dataset.

        Args:
            record: PRD grant record dictionary
        """
        try:
            await Actor.push_data(record)
            Actor.log.debug(f"Pushed record to dataset: {record.get('title', 'unknown')}")
        except Exception as e:
            Actor.log.error(f"Failed to push record to dataset: {e}")
            raise

    async def push_many(self, records: List[Dict]) -> None:
        """
        Push multiple records to dataset.

        Args:
            records: List of PRD grant records
        """
        for record in records:
            await self.push(record)

    async def get_all(self) -> List[Dict]:
        """
        Get all records from dataset.

        Note: For large datasets, this should use pagination.
        For MVP, we load all records into memory.

        Returns:
            List of all dataset records
        """
        try:
            # Get default dataset
            dataset = await Actor.open_dataset()

            # Iterate all items
            items = []
            async for item in dataset.iterate_items():
                items.append(item)

            Actor.log.info(f"Loaded {len(items)} items from dataset")
            return items

        except Exception as e:
            Actor.log.error(f"Failed to load dataset: {e}")
            return []

    async def exists(self, content_hash: str) -> bool:
        """
        Check if record with given content hash exists in dataset.

        Args:
            content_hash: SHA256 content hash

        Returns:
            True if record exists, False otherwise
        """
        items = await self.get_all()

        for item in items:
            if item.get('contentHash') == content_hash:
                return True

        return False


class KVStoreManager:
    """Manager for Key-Value Store operations"""

    @staticmethod
    async def get_last_fetched(source_id: str) -> Optional[datetime]:
        """
        Get lastFetchedAt timestamp for a source.

        Args:
            source_id: Source identifier (e.g., "mz-grants")

        Returns:
            Datetime object or None if not found
        """
        try:
            key = f"lastFetchedAt-{source_id}"
            value = await Actor.get_value(key)

            if value:
                # Parse ISO timestamp
                return datetime.fromisoformat(value)

            return None

        except Exception as e:
            Actor.log.error(f"Failed to get lastFetchedAt for {source_id}: {e}")
            return None

    @staticmethod
    async def set_last_fetched(source_id: str, timestamp: datetime) -> None:
        """
        Update lastFetchedAt timestamp for a source.

        Args:
            source_id: Source identifier
            timestamp: Datetime object to store
        """
        try:
            key = f"lastFetchedAt-{source_id}"
            value = timestamp.isoformat()

            await Actor.set_value(key, value)
            Actor.log.debug(f"Updated lastFetchedAt for {source_id}: {value}")

        except Exception as e:
            Actor.log.error(f"Failed to set lastFetchedAt for {source_id}: {e}")
            raise

    @staticmethod
    async def set_run_summary(summary: Dict) -> None:
        """
        Store run summary in KV Store.

        Args:
            summary: Dictionary with run statistics
        """
        try:
            await Actor.set_value('runSummary', summary)
            Actor.log.info(f"Stored run summary: {summary}")
        except Exception as e:
            Actor.log.error(f"Failed to store run summary: {e}")
            raise
