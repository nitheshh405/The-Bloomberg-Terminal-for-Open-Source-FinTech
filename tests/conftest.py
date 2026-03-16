"""
Shared pytest configuration and fixtures.
"""

import sys
import os

# Add project root to path so imports work without installing the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: pure unit tests with no external dependencies")
    config.addinivalue_line("markers", "integration: tests requiring the FastAPI app")
    config.addinivalue_line("markers", "neo4j: tests requiring a live Neo4j instance")
    config.addinivalue_line("markers", "slow: tests that take more than 5 seconds")
