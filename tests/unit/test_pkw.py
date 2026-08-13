import json

import pytest

from ptools import pkw
from ptools.portage_adapter import MockPortageBackend

ATOM = "app-editors/neovim"


def run(backend, *argv):
    return pkw.main(list(argv), backend=backend)


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        pkw.main(["--help"])
    assert exc.value.code == 0
    assert "pkw [OPTIONS] PACKAGE" in capsys.readouterr().out


def test_show_is_the_default_form(backend, config_root, capsys):
    assert run(backend, ATOM) == 0

    out = capsys.readouterr().out
    assert "amd64 ~arm64 x86" in out
    assert "(none)" in out


def test_show_json(backend, config_root, keyword_file, capsys):
    assert run(backend, "--json", ATOM) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["operation"] == "keyword.show"
    assert payload["arch"] == "amd64"
    assert payload["target"] == str(keyword_file)


def test_show_notes_legacy_package_keywords(backend, config_root, capsys):
    (config_root / "package.keywords").write_text(f"{ATOM} ~amd64\n")

    assert run(backend, ATOM) == 0
    assert "legacy package.keywords" in capsys.readouterr().out


def test_testing_expands_to_arch(backend, config_root, keyword_file):
    assert run(backend, "--testing", ATOM) == 0
    assert keyword_file.read_text() == f"{ATOM} ~amd64\n"


def test_testing_uses_the_real_arch(config_root, keyword_file):
    backend = MockPortageBackend({"cat/pkg": {"repo_versions": ["1.0"]}}, {"ARCH": "arm64"})

    assert run(backend, "--testing", "cat/pkg") == 0
    assert keyword_file.read_text() == "cat/pkg ~arm64\n"


def test_explicit_keyword(backend, config_root, keyword_file):
    assert run(backend, ATOM, "~arm64") == 0
    assert keyword_file.read_text() == f"{ATOM} ~arm64\n"


def test_wildcard_keywords_are_operands_not_options(backend, config_root, keyword_file):
    assert run(backend, ATOM, "-*", "**") == 0
    assert keyword_file.read_text() == f"{ATOM} -* **\n"


def test_testing_combines_with_explicit_keywords(backend, config_root, keyword_file):
    assert run(backend, "--testing", ATOM, "-*") == 0
    assert keyword_file.read_text() == f"{ATOM} -* ~amd64\n"


def test_exact_pins_the_version(backend, config_root, keyword_file):
    assert run(backend, "--exact", "--testing", ATOM) == 0
    assert keyword_file.read_text() == f"={ATOM}-0.11.0 ~amd64\n"


def test_unset(backend, config_root, keyword_file):
    run(backend, "--testing", ATOM)

    assert run(backend, "--unset", ATOM, "~amd64") == 0
    assert not keyword_file.read_text()


def test_show_reports_a_bare_managed_entry_as_the_testing_keyword(
    backend, config_root, keyword_file, capsys
):
    # A lone atom in package.accept_keywords accepts ~ARCH (validated against
    # real portage in docs/gentoo-validation.md §10); show must say so rather
    # than claiming "(none)".
    keyword_file.parent.mkdir()
    keyword_file.write_text(f"{ATOM}\n")

    assert run(backend, "--json", ATOM) == 0
    assert json.loads(capsys.readouterr().out)["managed"] == ["~amd64"]


def test_testing_on_a_bare_managed_entry_changes_nothing(backend, config_root, keyword_file):
    keyword_file.parent.mkdir()
    keyword_file.write_text(f"{ATOM}\n")

    assert run(backend, "--testing", ATOM) == 0
    assert keyword_file.read_text() == f"{ATOM}\n"


def test_new_keyword_on_a_bare_managed_entry_keeps_the_implicit_arch(
    backend, config_root, keyword_file
):
    keyword_file.parent.mkdir()
    keyword_file.write_text(f"{ATOM}\n")

    assert run(backend, ATOM, "-*") == 0
    assert keyword_file.read_text() == f"{ATOM} ~amd64 -*\n"


def test_unset_arch_removes_a_bare_managed_entry(backend, config_root, keyword_file):
    keyword_file.parent.mkdir()
    keyword_file.write_text(f"{ATOM}\n")

    assert run(backend, "--unset", ATOM, "~amd64") == 0
    assert not keyword_file.read_text()


def test_dry_run_writes_nothing(backend, config_root, keyword_file, capsys):
    assert run(backend, "--dry-run", "--testing", ATOM) == 0

    assert not keyword_file.exists()
    assert "[dry-run]" in capsys.readouterr().out


def test_unknown_package_exits_3(backend, config_root):
    assert run(backend, "app-editors/emacs", "~amd64") == 3


def test_ambiguous_name_exits_4(backend, config_root):
    assert run(backend, "vim", "~amd64") == 4


def test_invalid_keyword_exits_2(backend, config_root, capsys):
    assert run(backend, ATOM, "~amd64 && reboot") == 2
    assert "invalid keyword" in capsys.readouterr().err


def test_testing_with_unset_exits_2(backend, config_root, capsys):
    assert run(backend, "--testing", "--unset", ATOM, "~amd64") == 2
    assert "cannot be combined" in capsys.readouterr().err


def test_unset_without_keywords_exits_2(backend, config_root, capsys):
    assert run(backend, "--unset", ATOM) == 2
    assert "requires at least one keyword" in capsys.readouterr().err


def test_unknown_arch_exits_7(config_root, capsys):
    backend = MockPortageBackend({"cat/pkg": {"repo_versions": ["1.0"]}}, {"ARCH": ""})

    assert run(backend, "--testing", "cat/pkg") == 7
    assert "cannot determine ARCH" in capsys.readouterr().err
