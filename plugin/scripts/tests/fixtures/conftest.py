# Prevents pytest from collecting fixture files as tests


def pytest_ignore_collect(collection_path):
    """Ignore test files in fixture directories."""
    # This prevents pytest from collecting tests in the fixtures directory itself
    if collection_path.name in ("scan_samples", "full_project"):
        return True
