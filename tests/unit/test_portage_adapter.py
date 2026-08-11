import pytest

from ptools.errors import AmbiguousPackageError, PackageNotFoundError, PortageIntegrationError
from ptools.portage_adapter import MockPortageBackend, get_portage_backend


def test_resolve_category_qualified(backend):
    package = backend.resolve("app-editors/neovim")

    assert package.cp == "app-editors/neovim"
    assert package.cpv == "app-editors/neovim-0.11.0"
    assert package.installed_versions == ("app-editors/neovim-0.10.4",)


def test_resolve_exact_atom(backend):
    package = backend.resolve("=app-editors/neovim-0.10.4")

    assert package.cp == "app-editors/neovim"
    assert package.cpv == "app-editors/neovim-0.10.4"


def test_resolve_version_matched_atom(backend):
    assert backend.resolve("~app-editors/neovim-0.11.0").cpv == "app-editors/neovim-0.11.0"


def test_resolve_unqualified_name(backend):
    assert backend.resolve("neovim").cp == "app-editors/neovim"


def test_resolve_unknown_package(backend):
    with pytest.raises(PackageNotFoundError):
        backend.resolve("app-editors/emacs")


def test_resolve_unknown_version(backend):
    with pytest.raises(PackageNotFoundError):
        backend.resolve("=app-editors/neovim-99.0")


def test_resolve_empty_request(backend):
    with pytest.raises(PackageNotFoundError):
        backend.resolve("")


def test_resolve_ambiguous_name(backend):
    with pytest.raises(AmbiguousPackageError, match="app-editors/vim, app-misc/vim"):
        backend.resolve("vim")


def test_metadata_accessors(backend):
    assert backend.iuse("neovim") == ("lua", "python", "tree-sitter")
    assert backend.effective_use("neovim") == ("lua", "tree-sitter")
    assert backend.installed_use("neovim") == ("lua",)
    assert backend.keywords("neovim") == ("amd64", "~arm64", "x86")
    assert backend.keywords("sys-apps/portage") == ()


def test_settings_have_defaults_and_overrides():
    assert MockPortageBackend({}).get_setting("ARCH") == "amd64"
    assert MockPortageBackend({}, {"ARCH": "arm64"}).get_setting("ARCH") == "arm64"
    assert MockPortageBackend({}).get_setting("UNSET", "fallback") == "fallback"


def test_package_without_versions_resolves_to_no_cpv():
    assert MockPortageBackend({"cat/pkg": {}}).resolve("cat/pkg").cpv is None


def test_factory_reports_a_missing_portage_module(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "ptools.portage_real":
            raise ImportError("No module named 'portage'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(PortageIntegrationError, match="portage Python API not available"):
        get_portage_backend()
