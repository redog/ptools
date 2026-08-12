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


def _raise_on_importing_portage_real(monkeypatch, exc):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "ptools.portage_real":
            raise exc
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_factory_reports_a_missing_portage_module(monkeypatch):
    _raise_on_importing_portage_real(monkeypatch, ImportError("No module named 'portage'"))

    with pytest.raises(PortageIntegrationError, match="portage Python API not available"):
        get_portage_backend()


def test_factory_maps_a_broken_portage_configuration_to_exit_7(monkeypatch):
    # Importing portage reads make.conf and the profile, so a broken one raises
    # a portage exception out of the import - not an ImportError.
    class ParseError(Exception):
        pass

    _raise_on_importing_portage_real(monkeypatch, ParseError("make.conf: line 3: invalid"))

    with pytest.raises(PortageIntegrationError, match="configuration failed to load") as caught:
        get_portage_backend()
    assert caught.value.exit_code == 7


def test_factory_maps_a_failing_backend_construction_to_exit_7(monkeypatch):
    import sys
    import types

    module = types.ModuleType("ptools.portage_real")

    class RealPortageBackend:
        def __init__(self):
            raise KeyError("/unexpected-root/")

    module.RealPortageBackend = RealPortageBackend
    monkeypatch.setitem(sys.modules, "ptools.portage_real", module)

    with pytest.raises(PortageIntegrationError, match="cannot initialise the portage backend"):
        get_portage_backend()
