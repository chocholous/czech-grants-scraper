"""
Navigator strategies for grant discovery.

Navigators handle the discovery phase - finding all grant URLs
from a source's listing page(s).

Strategies:
- SingleLevelNavigator: list → detail (most common)
- MultiLevelNavigator: L1 → L2 → ... → detail
- DocumentNavigator: list → PDF/Excel
- StaticNavigator: single page = single grant
- HybridNavigator: combination of strategies
"""

from .base import NavigatorStrategy
from .single_level import SingleLevelNavigator
from .multi_level import MultiLevelNavigator
from .static import StaticNavigator

__all__ = [
    "NavigatorStrategy",
    "SingleLevelNavigator",
    "MultiLevelNavigator",
    "StaticNavigator",
]
