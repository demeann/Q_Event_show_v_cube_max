"""Smoke-тест каркаса: проверяем, что пакет импортируется и версия задана."""

import app


def test_app_imports():
    assert app.__version__ == "0.1.0"
