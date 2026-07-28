
import pytest

from ptools.config_store import ConfigStore
from ptools.portage_adapter import MockPortageBackend
from ptools.services import MutationService


@pytest.fixture
def mock_backend():
    packages = {
        "app-editors/neovim": {
            "repo_versions": ["0.10.4"],
        }
    }
    return MockPortageBackend(packages)


def test_apply_use_set(mock_backend, tmp_path):
    store = ConfigStore()
    svc = MutationService(mock_backend, store, tmp_path)

    result = svc.apply_use("set", "app-editors/neovim", ("lua", "python"))

    assert result["operation"] == "use.set"
    assert result["changed"] is True
    assert "lua" in result["added"]
    assert (tmp_path / "package.use/ptools").exists()
    assert (tmp_path / "package.use/ptools").read_text() == "app-editors/neovim lua python\n"


def test_apply_keyword_set_exact(mock_backend, tmp_path):
    store = ConfigStore()
    svc = MutationService(mock_backend, store, tmp_path)

    result = svc.apply_keyword("set", "app-editors/neovim", ("~amd64",), exact=True)

    assert result["changed"] is True
    assert result["atom"] == "=app-editors/neovim-0.10.4"
    assert (tmp_path / "package.accept_keywords/ptools").exists()
    assert (
        tmp_path / "package.accept_keywords/ptools"
    ).read_text() == "=app-editors/neovim-0.10.4 ~amd64\n"
