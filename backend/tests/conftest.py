"""Shared test setup.

The app defaults to CONTROLLER_MODE="agent", which consults an LLM. Tests
must never depend on a live model, so every test runs in "rules" mode
unless it opts in to agent mode itself (test_controller.py does, with the
LLM call replaced by a stub).
"""
import pytest

from app import config


@pytest.fixture(autouse=True)
def rules_mode_by_default(monkeypatch):
    monkeypatch.setattr(config, "CONTROLLER_MODE", "rules")
