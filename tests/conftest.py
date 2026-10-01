"""Test helpers shared by the suite."""

import pytest


@pytest.fixture(autouse=True)
def _clear_ci_show_block(monkeypatch):
    """GitHub Actions sets CI, which would refuse --show inside the suite.

    Tests that cover the refusal set the variable themselves.
    """
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
