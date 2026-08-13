"""Milestone I: the ambiguity menu, and showing every atom form of a package.

The legacy tools offered ambiguous names as a menu; that behavior returns as a
TTY-only prompt (scripts, --json, and --quiet still exit 4 deterministically).
Shows list every config entry whose atom refers to the package, however it is
spelled, so the user can see what to change or unset.
"""

import io
import json

import pytest

from ptools import cli_common, pkw, puse
from ptools.portage_adapter import MockPortageBackend

ATOM = "app-editors/neovim"


class FakeTty(io.StringIO):
    def isatty(self) -> bool:
        return True


@pytest.fixture
def interactive(monkeypatch):
    """Pretend a human is attached; feed menu answers via the returned setter."""

    def answer(text: str) -> None:
        monkeypatch.setattr(cli_common.sys, "stdin", FakeTty(text))

    monkeypatch.setattr(cli_common, "can_prompt", lambda args: not args.json and not args.quiet)
    return answer


# -- the menu itself ------------------------------------------------------


def test_select_match_returns_the_chosen_candidate(monkeypatch, capsys):
    monkeypatch.setattr(cli_common.sys, "stdin", FakeTty("2\n"))

    assert cli_common.select_match(("app-editors/vim", "app-misc/vim")) == "app-misc/vim"
    err = capsys.readouterr().err
    assert "1) app-editors/vim" in err
    assert "2) app-misc/vim" in err


@pytest.mark.parametrize("answer", ["", "\n", "q\n", "0\n", "3\n", "nope\n"])
def test_select_match_aborts_on_anything_else(monkeypatch, answer):
    monkeypatch.setattr(cli_common.sys, "stdin", FakeTty(answer))

    assert cli_common.select_match(("app-editors/vim", "app-misc/vim")) is None


def test_can_prompt_requires_ttys_on_both_ends(monkeypatch):
    args = puse.build_parser().parse_args([ATOM])
    monkeypatch.setattr(cli_common.sys, "stdin", FakeTty(""))
    monkeypatch.setattr(cli_common.sys, "stderr", io.StringIO())  # not a tty

    assert cli_common.can_prompt(args) is False


# -- end to end through the CLIs ------------------------------------------


def test_ambiguous_show_offers_a_menu_and_continues(backend, config_root, interactive, capsys):
    interactive("1\n")

    assert puse.main(["vim"], backend=backend) == 0

    captured = capsys.readouterr()
    assert "1) app-editors/vim" in captured.err
    assert "app-editors/vim" in captured.out  # the show ran for the choice


def test_ambiguous_mutation_uses_the_choice(backend, config_root, use_file, interactive, capsys):
    interactive("2\n")

    assert puse.main(["vim", "python"], backend=backend) == 0
    assert use_file.read_text() == "app-misc/vim python\n"


def test_menu_abort_falls_back_to_exit_4(backend, config_root, interactive, capsys):
    interactive("q\n")

    assert pkw.main(["vim", "~amd64"], backend=backend) == 4
    assert "ambiguous package name" in capsys.readouterr().err


def test_json_mode_never_prompts(backend, config_root, interactive, capsys):
    assert puse.main(["--json", "vim"], backend=backend) == 4

    err = json.loads(capsys.readouterr().err)
    assert err["error"] == "ambiguous"


def test_quiet_mode_never_prompts(backend, config_root, interactive, capsys):
    assert puse.main(["--quiet", "vim"], backend=backend) == 4
    assert "candidates" not in capsys.readouterr().err


def test_non_tty_never_prompts(backend, config_root, capsys):
    # No patching at all: pytest's captured streams are not ttys.
    assert puse.main(["vim"], backend=backend) == 4
    assert "ambiguous package name" in capsys.readouterr().err


# -- showing every atom form of the package --------------------------------


@pytest.fixture
def use_dir(config_root):
    path = config_root / "package.use"
    path.mkdir()
    return path


@pytest.fixture
def keyword_dir(config_root):
    path = config_root / "package.accept_keywords"
    path.mkdir()
    return path


def test_show_lists_exact_and_slotted_entries_for_the_package(backend, use_dir, capsys):
    (use_dir / "default").write_text(
        f"{ATOM} lua\n=app-editors/neovim-0.10.4 -python\n{ATOM}:0 tree-sitter\n"
    )

    assert puse.main(["--json", ATOM], backend=backend) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["entries"] == [
        {"file": "default", "atom": ATOM, "values": ["lua"]},
        {"file": "default", "atom": "=app-editors/neovim-0.10.4", "values": ["-python"]},
        {"file": "default", "atom": f"{ATOM}:0", "values": ["tree-sitter"]},
    ]
    # managed/target still track only the atom a plain mutation would edit
    assert payload["managed"] == ["lua"]
    assert payload["target"] == str(use_dir / "default")


def test_show_render_labels_the_differing_atom(backend, use_dir, capsys):
    (use_dir / "default").write_text(f"{ATOM} lua\n=app-editors/neovim-0.10.4 -python\n")

    assert puse.main([ATOM], backend=backend) == 0
    out = capsys.readouterr().out

    assert "managed [default]:" in out
    assert "managed [default] =app-editors/neovim-0.10.4:" in out


def test_show_ignores_entries_for_other_packages(backend, use_dir, capsys):
    (use_dir / "default").write_text(f"{ATOM} lua\napp-editors/vim -python\napp-editors/* gtk\n")

    assert puse.main(["--json", ATOM], backend=backend) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["entries"] == [{"file": "default", "atom": ATOM, "values": ["lua"]}]


def test_exact_show_also_lists_the_package_wide_entry(backend, use_dir, capsys):
    (use_dir / "default").write_text(f"{ATOM} lua\n")

    assert puse.main(["--json", "--exact", "=app-editors/neovim-0.10.4"], backend=backend) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["atom"] == "=app-editors/neovim-0.10.4"
    assert payload["entries"] == [{"file": "default", "atom": ATOM, "values": ["lua"]}]


def test_keyword_show_lists_bare_exact_entries(backend, keyword_dir, capsys):
    (keyword_dir / "default").write_text("=app-editors/neovim-0.10.4\n")

    assert pkw.main(["--json", ATOM], backend=backend) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["entries"] == [
        {"file": "default", "atom": "=app-editors/neovim-0.10.4", "values": ["~amd64"]}
    ]
    assert payload["managed"] == []


def test_mock_atom_cp_parses_config_atom_forms():
    backend = MockPortageBackend({})
    assert backend.atom_cp(ATOM) == ATOM
    assert backend.atom_cp("=app-editors/neovim-0.10.4") == ATOM
    assert backend.atom_cp(f"{ATOM}:0") == ATOM
    assert backend.atom_cp("~app-editors/neovim-0.10.4") == ATOM
    assert backend.atom_cp("neovim") is None
