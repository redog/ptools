"""Milestone H: managing a directory of files, not just the ptools one.

Show reads every file in the directory (portage does); mutations follow the
atom to the file that already holds it; ptools.conf names the default target
for new atoms; --init discovers and writes that config.
"""

import json

import pytest

from ptools import pkw, puse
from ptools.config_store import ConfigStore, stack_values

ATOM = "app-editors/neovim"


@pytest.fixture
def keyword_dir(config_root):
    path = config_root / "package.accept_keywords"
    path.mkdir()
    return path


@pytest.fixture
def use_dir(config_root):
    path = config_root / "package.use"
    path.mkdir()
    return path


def pkw_json(backend, *argv, capsys):
    assert pkw.main(["--json", *argv], backend=backend) == 0
    return json.loads(capsys.readouterr().out)


def puse_json(backend, *argv, capsys):
    assert puse.main(["--json", *argv], backend=backend) == 0
    return json.loads(capsys.readouterr().out)


# -- store: scan_entries / stack_values ----------------------------------


def test_scan_entries_visits_files_in_sorted_order(tmp_path):
    (tmp_path / "b-second").write_text(f"{ATOM} python\n")
    (tmp_path / "a-first").write_text(f"{ATOM} lua\n")
    (tmp_path / "unrelated").write_text("sys-apps/portage build\n")

    entries = ConfigStore().scan_entries(tmp_path, ATOM)

    assert entries == [("a-first", ("lua",)), ("b-second", ("python",))]


def test_scan_entries_skips_dotfiles_and_subdirectories(tmp_path):
    (tmp_path / ".hidden").write_text(f"{ATOM} lua\n")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested").write_text(f"{ATOM} python\n")
    (tmp_path / "visible").write_text(f"{ATOM} tree-sitter\n")

    assert ConfigStore().scan_entries(tmp_path, ATOM) == [("visible", ("tree-sitter",))]


def test_scan_entries_applies_the_implicit_value_per_file(tmp_path):
    (tmp_path / "default").write_text(f"{ATOM}\n")

    entries = ConfigStore().scan_entries(tmp_path, ATOM, implicit=("~amd64",))

    assert entries == [("default", ("~amd64",))]


def test_scan_entries_missing_directory_is_empty(tmp_path):
    assert ConfigStore().scan_entries(tmp_path / "nope", ATOM) == []


def test_stack_values_lets_the_later_file_win_a_contradiction():
    entries = [("01-a", ("lua", "python")), ("02-b", ("-lua",))]

    assert stack_values(entries) == ("python", "-lua")


# -- H1: show reports every file -----------------------------------------


def test_show_reports_entries_across_files(backend, keyword_dir, capsys):
    (keyword_dir / "default").write_text(f"{ATOM} ~amd64\n")
    (keyword_dir / "99-local").write_text(f"{ATOM} -*\nsys-apps/portage ~amd64\n")

    payload = pkw_json(backend, ATOM, capsys=capsys)

    assert payload["entries"] == [
        {"file": "99-local", "atom": ATOM, "values": ["-*"]},
        {"file": "default", "atom": ATOM, "values": ["~amd64"]},
    ]
    assert payload["managed"] == ["-*", "~amd64"]
    assert payload["target"] is None  # ambiguous: a mutation would need --file


def test_show_target_follows_the_single_file_with_the_entry(backend, use_dir, capsys):
    (use_dir / "default").write_text(f"{ATOM} lua\n")

    payload = puse_json(backend, ATOM, capsys=capsys)

    assert payload["entries"] == [{"file": "default", "atom": ATOM, "values": ["lua"]}]
    assert payload["target"] == str(use_dir / "default")


def test_show_reports_a_bare_atom_in_a_user_file(backend, keyword_dir, capsys):
    (keyword_dir / "default").write_text(f"{ATOM}\n")

    payload = pkw_json(backend, ATOM, capsys=capsys)

    assert payload["entries"] == [{"file": "default", "atom": ATOM, "values": ["~amd64"]}]


def test_show_render_attributes_each_file(backend, keyword_dir, capsys):
    (keyword_dir / "default").write_text(f"{ATOM} ~amd64\n")
    (keyword_dir / "99-local").write_text(f"{ATOM} -*\n")

    assert pkw.main([ATOM], backend=backend) == 0
    out = capsys.readouterr().out
    assert "managed [default]:" in out
    assert "managed [99-local]:" in out
    assert "(ambiguous - pass --file to choose)" in out


# -- H2: mutations follow the atom ---------------------------------------


def test_set_edits_the_file_that_already_holds_the_atom(backend, keyword_dir, keyword_file):
    (keyword_dir / "default").write_text(f"{ATOM} ~amd64\n")

    assert pkw.main([ATOM, "-*"], backend=backend) == 0

    assert (keyword_dir / "default").read_text() == f"{ATOM} ~amd64 -*\n"
    assert not keyword_file.exists()


def test_ambiguous_entries_fail_without_file(backend, keyword_dir, capsys):
    (keyword_dir / "default").write_text(f"{ATOM} ~amd64\n")
    (keyword_dir / "99-local").write_text(f"{ATOM} -*\n")

    assert pkw.main([ATOM, "**"], backend=backend) == 4

    err = capsys.readouterr().err
    assert "99-local" in err and "default" in err and "--file" in err
    assert (keyword_dir / "default").read_text() == f"{ATOM} ~amd64\n"
    assert (keyword_dir / "99-local").read_text() == f"{ATOM} -*\n"


def test_file_option_picks_a_target_and_reports_the_others(backend, keyword_dir, capsys):
    (keyword_dir / "default").write_text(f"{ATOM} ~amd64\n")
    (keyword_dir / "99-local").write_text(f"{ATOM} -*\n")

    payload = pkw_json(backend, "--file", "99-local", ATOM, "**", capsys=capsys)

    assert payload["target"] == str(keyword_dir / "99-local")
    assert payload["also_in"] == ["default"]
    assert (keyword_dir / "99-local").read_text() == f"{ATOM} -* **\n"
    assert (keyword_dir / "default").read_text() == f"{ATOM} ~amd64\n"


def test_file_option_accepts_the_equals_form(backend, use_dir):
    assert puse.main(["--file=10-editors", ATOM, "lua"], backend=backend) == 0
    assert (use_dir / "10-editors").read_text() == f"{ATOM} lua\n"


def test_new_atom_goes_to_the_managed_default(backend, config_root, use_file):
    assert puse.main([ATOM, "lua"], backend=backend) == 0
    assert use_file.read_text() == f"{ATOM} lua\n"


def test_unset_follows_the_atom_too(backend, use_dir):
    (use_dir / "default").write_text(f"{ATOM} lua python\n")

    assert puse.main(["--unset", ATOM, "lua"], backend=backend) == 0
    assert (use_dir / "default").read_text() == f"{ATOM} python\n"


def test_file_without_a_mutation_exits_2(backend, config_root, capsys):
    assert pkw.main(["--file", "default", ATOM], backend=backend) == 2
    assert "--file only applies to mutations" in capsys.readouterr().err


def test_file_with_a_path_separator_exits_2(backend, config_root, capsys):
    assert puse.main(["--file", "../evil", ATOM, "lua"], backend=backend) == 2
    assert "invalid target filename" in capsys.readouterr().err


def test_file_with_a_leading_dot_exits_2(backend, config_root, capsys):
    assert puse.main(["--file", ".hidden", ATOM, "lua"], backend=backend) == 2
    assert "invalid target filename" in capsys.readouterr().err


def test_file_without_a_value_exits_2(backend, config_root, capsys):
    assert puse.main([ATOM, "lua", "--file"], backend=backend) == 2
    assert "requires a value" in capsys.readouterr().err


# -- H3: ptools.conf + --init --------------------------------------------


def test_config_default_file_receives_new_atoms(backend, config_root, use_dir):
    (config_root / "ptools.conf").write_text("[use]\ndefault-file = default\n")

    assert puse.main([ATOM, "lua"], backend=backend) == 0
    assert (use_dir / "default").read_text() == f"{ATOM} lua\n"


def test_config_sections_are_independent(backend, config_root, keyword_file):
    (config_root / "ptools.conf").write_text("[use]\ndefault-file = default\n")

    assert pkw.main(["--testing", ATOM], backend=backend) == 0
    assert keyword_file.read_text() == f"{ATOM} ~amd64\n"


def test_config_with_an_invalid_filename_exits_6(backend, config_root, capsys):
    (config_root / "ptools.conf").write_text("[use]\ndefault-file = ../evil\n")

    assert puse.main([ATOM, "lua"], backend=backend) == 6
    assert "invalid target filename" in capsys.readouterr().err


def test_config_that_does_not_parse_exits_6(backend, config_root, capsys):
    (config_root / "ptools.conf").write_text("not an ini file [\n")

    assert puse.main([ATOM, "lua"], backend=backend) == 6
    assert "cannot parse" in capsys.readouterr().err


def test_init_writes_the_discovered_config(backend, config_root, keyword_dir, use_dir, capsys):
    (keyword_dir / "default").write_text(f"{ATOM} ~amd64\n")
    (use_dir / "50-editors").write_text(f"{ATOM} lua\n")

    payload = pkw_json(backend, "--init", capsys=capsys)

    assert payload["use_default"] == "50-editors"
    assert payload["keywords_default"] == "default"
    conf = (config_root / "ptools.conf").read_text()
    assert "[use]\ndefault-file = 50-editors" in conf
    assert "[keywords]\ndefault-file = default" in conf


def test_init_prefers_a_file_named_default(backend, config_root, use_dir, capsys):
    (use_dir / "default").write_text(f"{ATOM} lua\n")
    (use_dir / "50-editors").write_text("sys-apps/portage build\n")

    payload = puse_json(backend, "--init", capsys=capsys)

    assert payload["use_default"] == "default"


def test_init_falls_back_to_ptools_when_it_cannot_guess(backend, config_root, use_dir, capsys):
    (use_dir / "50-editors").write_text(f"{ATOM} lua\n")
    (use_dir / "60-servers").write_text("sys-apps/portage build\n")

    payload = puse_json(backend, "--init", capsys=capsys)

    assert payload["use_default"] == "ptools"
    assert payload["keywords_default"] == "ptools"


def test_init_dry_run_writes_nothing(backend, config_root, capsys):
    assert puse.main(["--dry-run", "--init"], backend=backend) == 0
    assert "[dry-run]" in capsys.readouterr().out
    assert not (config_root / "ptools.conf").exists()


def test_init_refuses_to_overwrite_an_existing_config(backend, config_root, capsys):
    (config_root / "ptools.conf").write_text("[use]\ndefault-file = default\n")

    assert puse.main(["--init"], backend=backend) == 6
    assert "already exists" in capsys.readouterr().err


def test_init_with_a_package_exits_2(backend, config_root, capsys):
    assert pkw.main(["--init", ATOM], backend=backend) == 2
    assert "--init takes no" in capsys.readouterr().err
