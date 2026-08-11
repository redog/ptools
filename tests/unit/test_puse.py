import json
import os

import pytest

from ptools import puse
from ptools.portage_adapter import MockPortageBackend

ATOM = "app-editors/neovim"


def run(backend, *argv):
    return puse.main(list(argv), backend=backend)


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        puse.main(["--help"])
    assert exc.value.code == 0
    assert "puse [OPTIONS] PACKAGE" in capsys.readouterr().out


def test_show_is_the_default_form(backend, config_root, capsys):
    assert run(backend, ATOM) == 0

    out = capsys.readouterr()
    assert "app-editors/neovim-0.11.0" in out.out
    assert "lua tree-sitter" in out.out
    assert out.err == ""


def test_show_json(backend, config_root, capsys):
    assert run(backend, "--json", ATOM) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["operation"] == "use.show"
    assert payload["managed"] == []
    assert "\033" not in json.dumps(payload)


def test_set_writes_the_managed_entry(backend, config_root, use_file, capsys):
    assert run(backend, ATOM, "lua", "-python") == 0

    assert use_file.read_text() == f"{ATOM} lua -python\n"
    assert "+lua" in capsys.readouterr().out


def test_set_accepts_a_bare_name(backend, config_root, use_file):
    assert run(backend, "neovim", "lua") == 0
    assert use_file.read_text() == f"{ATOM} lua\n"


def test_exact_pins_the_version(backend, config_root, use_file):
    assert run(backend, "--exact", ATOM, "lua") == 0
    assert use_file.read_text() == f"={ATOM}-0.11.0 lua\n"


def test_repeating_a_set_is_idempotent(backend, config_root, use_file, capsys):
    run(backend, ATOM, "lua")
    before = use_file.read_bytes()
    capsys.readouterr()

    assert run(backend, "--json", ATOM, "lua") == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["changed"] is False
    assert use_file.read_bytes() == before


def test_unset_removes_both_polarities(backend, config_root, use_file):
    run(backend, ATOM, "-lua", "python")

    assert run(backend, "--unset", ATOM, "lua") == 0
    assert use_file.read_text() == f"{ATOM} python\n"


def test_dry_run_writes_nothing(backend, config_root, use_file, capsys):
    assert run(backend, "--dry-run", ATOM, "lua") == 0

    assert not use_file.exists()
    assert "[dry-run]" in capsys.readouterr().out


def test_dry_run_json_reports_the_plan(backend, config_root, use_file, capsys):
    assert run(backend, "--dry-run", "--json", ATOM, "lua") == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "operation": "use.set",
        "atom": ATOM,
        "target": str(use_file),
        "added": ["lua"],
        "removed": [],
        "changed": True,
        "dry_run": True,
    }


def test_quiet_suppresses_human_output(backend, config_root, capsys):
    assert run(backend, "--quiet", ATOM, "lua") == 0
    assert capsys.readouterr() == ("", "")


def test_quiet_keeps_requested_json(backend, config_root, capsys):
    assert run(backend, "--quiet", "--json", ATOM, "lua") == 0
    assert json.loads(capsys.readouterr().out)["changed"] is True


def test_unknown_package_exits_3(backend, config_root, capsys):
    assert run(backend, "app-editors/emacs", "lua") == 3
    assert "package not found" in capsys.readouterr().err


def test_ambiguous_name_exits_4(backend, config_root, capsys):
    assert run(backend, "vim", "python") == 4

    out = capsys.readouterr()
    assert out.out == ""
    assert "ambiguous" in out.err


def test_duplicate_entries_exit_6(backend, config_root, use_file, capsys):
    use_file.parent.mkdir(parents=True)
    use_file.write_text(f"{ATOM} lua\n{ATOM} python\n")

    assert run(backend, ATOM, "sqlite") == 6
    assert "duplicate entries" in capsys.readouterr().err


def test_merge_duplicates_opt_in(backend, config_root, use_file):
    use_file.parent.mkdir(parents=True)
    use_file.write_text(f"{ATOM} lua\n{ATOM} python\n")

    assert run(backend, "--merge-duplicates", ATOM, "sqlite") == 0
    assert use_file.read_text() == f"{ATOM} lua python sqlite\n"


def test_symlinked_target_exits_8(backend, config_root, use_file, tmp_path, capsys):
    use_file.parent.mkdir(parents=True)
    use_file.symlink_to(tmp_path / "elsewhere")

    assert run(backend, ATOM, "lua") == 8
    assert "symlink" in capsys.readouterr().err


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
def test_unwritable_target_exits_5(backend, config_root, use_file, capsys):
    use_file.parent.mkdir(parents=True)
    os.chmod(use_file.parent, 0o500)
    try:
        assert run(backend, ATOM, "lua") == 5
        assert "re-run as root" in capsys.readouterr().err
    finally:
        os.chmod(use_file.parent, 0o700)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
def test_dry_run_needs_no_write_access(backend, config_root, use_file, capsys):
    use_file.parent.mkdir(parents=True)
    os.chmod(use_file.parent, 0o500)
    try:
        assert run(backend, "--dry-run", ATOM, "lua") == 0
    finally:
        os.chmod(use_file.parent, 0o700)


def test_missing_package_argument_exits_2(backend, config_root, capsys):
    assert run(backend) == 2

    out = capsys.readouterr()
    assert out.out == ""
    assert "usage: puse" in out.err


def test_unknown_option_exits_2(backend, config_root, capsys):
    assert run(backend, "--nope", ATOM) == 2
    assert "unrecognized option: --nope" in capsys.readouterr().err


def test_invalid_flag_exits_2(backend, config_root, capsys):
    assert run(backend, ATOM, "lua;rm -rf /") == 2
    assert "invalid USE flag" in capsys.readouterr().err


def test_unset_without_flags_exits_2(backend, config_root, capsys):
    assert run(backend, "--unset", ATOM) == 2
    assert "requires at least one USE flag" in capsys.readouterr().err


def test_json_errors_go_to_stderr(backend, config_root, capsys):
    assert run(backend, "--json", "app-editors/emacs") == 3

    out = capsys.readouterr()
    assert out.out == ""
    assert json.loads(out.err) == {
        "error": "not-found",
        "message": "package not found: app-editors/emacs",
        "exit_code": 3,
    }


def test_portage_failures_exit_7(config_root, capsys):
    class BrokenBackend(MockPortageBackend):
        def resolve(self, request):
            from ptools.errors import PortageIntegrationError

            raise PortageIntegrationError("portage lookup failed")

    assert run(BrokenBackend({}), ATOM, "lua") == 7
    assert "portage lookup failed" in capsys.readouterr().err
