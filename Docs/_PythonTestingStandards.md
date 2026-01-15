# Python Testing Standards

This document defines the testing standards and conventions for the PAGDrawer project.

## Test Framework

- **pytest** - Primary test framework
- **pytest-cov** - Coverage measurement
- **pytest-asyncio** - Async test support

## File Structure

```
tests/
├── conftest.py       # Shared fixtures
├── test_builder.py   # Graph builder tests
├── test_config.py    # Configuration tests
├── test_api.py       # FastAPI endpoint tests
├── test_frontend.py  # Playwright browser tests
└── __init__.py
```

## Naming Conventions

### Test Files
- Prefix with `test_` (e.g., `test_builder.py`)
- Name should match the module being tested

### Test Classes
- Group related tests in classes
- Use descriptive names: `TestGraphBuilderInitialization`, `TestAddNodes`
- No need for `unittest.TestCase` inheritance

### Test Methods
- Prefix with `test_`
- Use descriptive names: `test_add_host_creates_node`
- Follow pattern: `test_<action>_<expected_result>`

## Fixtures

Define reusable fixtures in `conftest.py`:

```python
@pytest.fixture
def empty_graph_builder():
    """Fresh builder with no nodes."""
    return KnowledgeGraphBuilder()

@pytest.fixture
def loaded_graph_builder(default_config):
    """Builder with mock data loaded."""
    builder = KnowledgeGraphBuilder(config=default_config)
    builder.load_from_mock_data()
    return builder

@pytest.fixture
def sample_host_data():
    """Sample host data for testing."""
    return {
        "id": "test-host-001",
        "os_family": "linux",
        "criticality_score": 0.8,
        "subnet_id": "dmz"
    }
```

## Test Organization

### Unit Tests
Test individual functions/methods in isolation:

```python
class TestAddNodes:
    def test_add_host(self, empty_graph_builder, sample_host_data):
        empty_graph_builder.add_host(sample_host_data)
        stats = empty_graph_builder.get_stats()
        assert stats["node_counts"].get("HOST", 0) == 1
```

### Integration Tests
Test multiple components working together:

```python
class TestLoadFromMockData:
    def test_creates_all_node_types(self, loaded_graph_builder):
        stats = loaded_graph_builder.get_stats()
        assert stats["node_counts"].get("HOST", 0) > 0
        assert stats["node_counts"].get("CVE", 0) > 0
```

### API Tests
Use FastAPI's TestClient:

```python
from fastapi.testclient import TestClient

def test_get_graph_returns_200(client):
    response = client.get("/api/graph")
    assert response.status_code == 200
```

## Assertions

Use pytest's plain `assert`:

```python
# Good
assert result == expected
assert len(items) > 0
assert "key" in data

# Include messages for complex assertions
assert count >= 10, f"Expected at least 10 items, got {count}"
```

## Coverage Requirements

- **Target:** 80%+ overall coverage
- **Current:** 94%
- Run coverage: `pytest --cov=src --cov-report=term-missing tests/`

## Running Tests

```bash
# All tests
pytest tests/ -v

# Specific file
pytest tests/test_builder.py -v

# With coverage
pytest --cov=src tests/

# Specific test class
pytest tests/test_builder.py::TestAddNodes -v

# Frontend tests (requires servers running)
$env:PYTEST_BASE_URL='http://localhost:3000'
pytest tests/test_frontend.py -v
```

## Configuration

`pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

## Best Practices

1. **One assertion per test** (when practical)
2. **Test behavior, not implementation**
3. **Use fixtures for setup/teardown**
4. **Keep tests independent** - no test should depend on another
5. **Test edge cases** - empty inputs, null values, boundaries
6. **Use `tmp_path` fixture** for file operations
7. **Mock external services** when needed

## Example Complete Test Class

```python
class TestExportGexf:
    """Tests for GEXF export functionality."""
    
    def test_export_creates_file(self, loaded_graph_builder, tmp_path):
        """export_gexf should create a GEXF file."""
        filepath = tmp_path / "test_graph.gexf"
        loaded_graph_builder.export_gexf(str(filepath))
        
        assert filepath.exists()
        assert filepath.stat().st_size > 0
    
    def test_export_valid_xml(self, loaded_graph_builder, tmp_path):
        """GEXF file should be valid XML."""
        filepath = tmp_path / "graph.gexf"
        loaded_graph_builder.export_gexf(str(filepath))
        
        content = filepath.read_text()
        assert "<?xml" in content
```
