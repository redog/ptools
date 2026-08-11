import pytest

from ptools.portage_adapter import MockPortageBackend

PACKAGES = {
    "app-editors/neovim": {
        "repo_versions": ["0.10.4", "0.11.0"],
        "installed_versions": ["0.10.4"],
        "iuse": ["lua", "python", "tree-sitter"],
        "effective_use": ["lua", "tree-sitter"],
        "installed_use": ["lua"],
        "keywords": ["amd64", "~arm64", "x86"],
    },
    "app-editors/vim": {
        "repo_versions": ["9.1.0"],
        "iuse": ["python"],
        "keywords": ["~amd64"],
    },
    "app-misc/vim": {
        "repo_versions": ["1.0"],
    },
    "sys-apps/portage": {
        "repo_versions": ["3.0.66"],
        "installed_versions": ["3.0.66"],
    },
}


@pytest.fixture
def backend() -> MockPortageBackend:
    return MockPortageBackend(PACKAGES)


@pytest.fixture
def config_root(tmp_path, monkeypatch):
    """A sandbox standing in for <PORTAGE_CONFIGROOT>/etc/portage."""
    root = tmp_path / "portage"
    root.mkdir()
    monkeypatch.setenv("PTOOLS_CONFIG_ROOT", str(root))
    monkeypatch.delenv("NO_COLOR", raising=False)
    return root


@pytest.fixture
def use_file(config_root):
    return config_root / "package.use" / "ptools"


@pytest.fixture
def keyword_file(config_root):
    return config_root / "package.accept_keywords" / "ptools"
