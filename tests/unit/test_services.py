import pytest

from ptools.config_store import ConfigStore
from ptools.errors import PackageNotFoundError
from ptools.portage_adapter import MockPortageBackend
from ptools.services import MutationService, ReadOnlyService, keyword_target, use_target


@pytest.fixture
def mutations(backend, config_root):
    return MutationService(backend, ConfigStore(), config_root)


@pytest.fixture
def reads(backend, config_root):
    return ReadOnlyService(backend, ConfigStore(), config_root)


def test_targets_use_the_directory_layout(config_root):
    assert use_target(config_root).parts[-2:] == ("package.use", "ptools")
    assert keyword_target(config_root).parts[-2:] == ("package.accept_keywords", "ptools")


def test_target_atom_defaults_to_package_wide(mutations):
    assert mutations.target_atom("=app-editors/neovim-0.10.4") == "app-editors/neovim"


def test_target_atom_pins_the_version_when_exact(mutations):
    assert mutations.target_atom("neovim", exact=True) == "=app-editors/neovim-0.11.0"


def test_target_atom_exact_needs_a_version(config_root):
    backend = MockPortageBackend({"cat/pkg": {}})
    service = MutationService(backend, ConfigStore(), config_root)

    with pytest.raises(PackageNotFoundError, match="no version available to pin"):
        service.target_atom("cat/pkg", exact=True)


def test_apply_use_set(mutations, use_file):
    result = mutations.apply_use("set", "neovim", ("lua", "-python"))

    assert result == {
        "operation": "use.set",
        "atom": "app-editors/neovim",
        "target": str(use_file),
        "added": ["lua", "-python"],
        "removed": [],
        "changed": True,
        "dry_run": False,
    }
    assert use_file.read_text() == "app-editors/neovim lua -python\n"


def test_apply_use_unset(mutations, use_file):
    mutations.apply_use("set", "neovim", ("lua", "-python"))
    result = mutations.apply_use("unset", "neovim", ("python",))

    assert result["removed"] == ["-python"]
    assert use_file.read_text() == "app-editors/neovim lua\n"


def test_apply_keyword_exact(mutations, keyword_file):
    result = mutations.apply_keyword("set", "neovim", ("~amd64",), exact=True)

    assert result["operation"] == "keyword.set"
    assert result["atom"] == "=app-editors/neovim-0.11.0"
    assert keyword_file.read_text() == "=app-editors/neovim-0.11.0 ~amd64\n"


def test_apply_reports_dry_run(backend, config_root, use_file):
    service = MutationService(backend, ConfigStore(dry_run=True), config_root)

    result = service.apply_use("set", "neovim", ("lua",))

    assert result["dry_run"] is True
    assert result["changed"] is True
    assert not use_file.exists()


def test_use_show(reads, mutations, use_file):
    mutations.apply_use("set", "neovim", ("lua",))

    payload = reads.use_show("neovim")

    assert payload["operation"] == "use.show"
    assert payload["cp"] == "app-editors/neovim"
    assert payload["iuse"] == ["lua", "python", "tree-sitter"]
    assert payload["effective"] == ["lua", "tree-sitter"]
    assert payload["installed_use"] == ["lua"]
    assert payload["managed"] == ["lua"]
    assert payload["target"] == str(use_file)


def test_use_show_exact_reads_the_pinned_entry(reads, mutations):
    mutations.apply_use("set", "neovim", ("lua",), exact=True)

    assert reads.use_show("neovim", exact=True)["managed"] == ["lua"]
    assert reads.use_show("neovim")["managed"] == []


def test_keyword_show(reads, mutations, keyword_file, config_root):
    mutations.apply_keyword("set", "neovim", ("~arm64",))

    payload = reads.keyword_show("neovim")

    assert payload["operation"] == "keyword.show"
    assert payload["arch"] == "amd64"
    assert payload["keywords"] == ["amd64", "~arm64", "x86"]
    assert payload["managed"] == ["~arm64"]
    assert payload["target"] == str(keyword_file)
    assert payload["legacy_package_keywords"] is False


def test_keyword_show_flags_legacy_package_keywords(reads, config_root):
    (config_root / "package.keywords").write_text("app-editors/neovim ~amd64\n")

    assert reads.keyword_show("neovim")["legacy_package_keywords"] is True


def test_resolve_payload(reads):
    payload = reads.resolve("neovim")

    assert payload["cp"] == "app-editors/neovim"
    assert payload["repository"] == [
        "app-editors/neovim-0.10.4",
        "app-editors/neovim-0.11.0",
    ]
