"""Shared fixtures for backend unit tests."""

import sys
import os
import pytest

# Add backend/app to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
# Add project root for evaluation imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


@pytest.fixture
def sample_markdown_sections():
    """Multi-section markdown text for testing section extraction."""
    return """## Business Objectives
Reduce scrap rate from 4.2% to under 2%.
Achieve IATF 16949 compliance.

## Situation Assessment
Company uses paper-based quality documentation.
No digital defect tracking system in place.

## AI Goals
Implement visual defect detection using cameras.
Integrate measurement device data automatically.

## Project Plan
Phase 1: Tablet-based documentation (2-3 weeks).
Phase 2: Camera deployment at inspection stations.
"""


@pytest.fixture
def sample_markdown_sections_de():
    """German multi-section markdown text."""
    return """## Geschäftsziele
Ausschussrate von 4,2% auf unter 2% senken.

## Situationsanalyse
Papierbasierte Qualitätsdokumentation.

## KI-Ziele
Visuelle Fehlererkennung mit Kameras.
"""
