"""Runs in an isolated subprocess; never points fixtures at the production database."""
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.mysql
def test_mysql_migration_upsert_queue_and_restore(tmp_path):
    url = os.getenv('MYSQL_TEST_URL')
    if not url:
        pytest.skip('Configure MYSQL_TEST_URL para um banco descartável de testes.')
    env = os.environ.copy()
    env['DATABASE_URL'] = url
    script = Path(__file__).with_name('mysql_scenario.py')
    result = subprocess.run([sys.executable, str(script), str(tmp_path)], env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    # Upstream exceptions can contain URLs. Report only sanitized final scenario output.
    assert result.returncode == 0, result.stdout[-4000:]
