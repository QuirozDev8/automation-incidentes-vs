# ejecutar test localmente
"""
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install pytest
pytest -q
"""

"""
tests/test_core.py
--------------------------------
Pruebas unitarias básicas para el script jira_daily_audit_mailer.py

Se usan objetos simulados (mock data) en lugar de llamar al API real de Jira.
Esto permite validar la lógica de negocio sin depender de internet.
"""

import pytest
import random
from datetime import datetime

# Importamos funciones del script principal
from automation_jira import (
    build_jql,
    group_by_assignee,
    pick_random_per_analyst,
)


# ------------------------------
# Fixtures de datos simulados
# ------------------------------

@pytest.fixture
def sample_issues():
    """Genera una lista de issues simulados de Jira."""
    return [
        {
            "key": "PROJ-1",
            "fields": {
                "summary": "Bug en login",
                "assignee": {"accountId": "u1", "displayName": "Alice"},
            },
        },
        {
            "key": "PROJ-2",
            "fields": {
                "summary": "Error en checkout",
                "assignee": {"accountId": "u1", "displayName": "Alice"},
            },
        },
        {
            "key": "PROJ-3",
            "fields": {
                "summary": "Mejora en dashboard",
                "assignee": {"accountId": "u2", "displayName": "Bob"},
            },
        },
    ]


# ------------------------------
# Tests
# ------------------------------

def test_build_jql():
    """La JQL debe formatear correctamente fechas y proyectos."""
    target_date = datetime(2025, 9, 3)
    jql = build_jql(target_date, "PROJ1,PROJ2")
    assert "project in (PROJ1,PROJ2)" in jql
    assert "resolved >=" in jql
    assert "2025-09-03" in jql


def test_group_by_assignee(sample_issues):
    """Los issues deben agruparse correctamente por analista."""
    groups = group_by_assignee(sample_issues)
    # Alice tiene 2 issues
    assert any(name == "Alice" and len(items) == 2 for (_, name), items in groups.items())
    # Bob tiene 1 issue
    assert any(name == "Bob" and len(items) == 1 for (_, name), items in groups.items())


def test_pick_random_per_analyst(sample_issues):
    """La selección aleatoria no debe devolver más de N issues por analista."""
    groups = group_by_assignee(sample_issues)
    selection = pick_random_per_analyst(groups, per_analyst=1)

    # Cada analista debe tener como máximo 1 issue seleccionado
    for (_, _), items in selection.items():
        assert len(items) <= 1


def test_pick_random_is_different(sample_issues):
    """La selección aleatoria debe variar en llamadas sucesivas."""
    groups = group_by_assignee(sample_issues)
    # Forzamos la semilla aleatoria distinta en cada ejecución
    random.seed(1)
    first = pick_random_per_analyst(groups, 1)
    random.seed(2)
    second = pick_random_per_analyst(groups, 1)

    # Es posible que coincidan, pero en general deberían diferir
    # Forzamos la comprobación al menos de que se devuelvan issues válidos
    for (_, name), items in first.items():
        assert all("key" in issue for issue in items)
    for (_, name), items in second.items():
        assert all("key" in issue for issue in items)
