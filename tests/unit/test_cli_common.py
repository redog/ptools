import re
from pathlib import Path

import pytest

from ptools.cli_common import (
    GLOBAL_OPTIONS,
    KEYWORD_RE,
    USE_FLAG_RE,
    Output,
    color_enabled,
    partition_argv,
    render_field,
    render_mutation,
    resolve_config_root,
    validate_tokens,
)
from ptools.errors import PackageNotFoundError, UsageError
from ptools.portage_adapter import MockPortageBackend


def test_partition_keeps_negated_tokens_as_operands():
    found, operands = partition_argv(["--dry-run", "cat/pkg", "-lua", "-*"], GLOBAL_OPTIONS)

    assert found == ["--dry-run"]
    assert operands == ["cat/pkg", "-lua", "-*"]


def test_partition_normalises_help():
    assert partition_argv(["-h"], GLOBAL_OPTIONS)[0] == ["--help"]


def test_partition_honours_the_end_of_options_marker():
    found, operands = partition_argv(["--", "--exact"], GLOBAL_OPTIONS)

    assert found == []
    assert operands == ["--exact"]


def test_partition_rejects_unknown_options():
    with pytest.raises(UsageError, match="unrecognized option: --wat"):
        partition_argv(["--wat"], GLOBAL_OPTIONS)


@pytest.mark.parametrize("token", ["lua", "-lua", "tree-sitter", "l10n_en", "video_cards_amdgpu"])
def test_valid_use_flags(token):
    assert USE_FLAG_RE.match(token)


@pytest.mark.parametrize("token", ["", "-", "lua flag", "lua;ls", "*", "$(id)"])
def test_invalid_use_flags(token):
    assert not USE_FLAG_RE.match(token)


@pytest.mark.parametrize("token", ["~amd64", "amd64", "-amd64", "-*", "**", "*", "~amd64-linux"])
def test_valid_keywords(token):
    assert KEYWORD_RE.match(token)


@pytest.mark.parametrize("token", ["~amd64 x86", "amd64|x86", "~"])
def test_invalid_keywords(token):
    assert not KEYWORD_RE.match(token)


def test_validate_tokens_reports_the_offender():
    with pytest.raises(UsageError, match="invalid USE flag: 'no way'"):
        validate_tokens(["lua", "no way"], USE_FLAG_RE, "USE flag")


def test_config_root_prefers_the_override(monkeypatch, tmp_path):
    monkeypatch.setenv("PTOOLS_CONFIG_ROOT", str(tmp_path))

    assert resolve_config_root(MockPortageBackend({})) == tmp_path


def test_config_root_follows_portage_configroot(monkeypatch):
    monkeypatch.delenv("PTOOLS_CONFIG_ROOT", raising=False)
    backend = MockPortageBackend({}, {"PORTAGE_CONFIGROOT": "/mnt/gentoo"})

    assert resolve_config_root(backend) == Path("/mnt/gentoo/etc/portage")


def test_config_root_never_assumes_a_missing_setting(monkeypatch):
    monkeypatch.delenv("PTOOLS_CONFIG_ROOT", raising=False)
    backend = MockPortageBackend({}, {"PORTAGE_CONFIGROOT": ""})

    assert resolve_config_root(backend) == Path("/etc/portage")


def test_colour_is_off_when_requested(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert color_enabled(no_color=True) is False


def test_colour_is_off_under_no_color_env(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert color_enabled(no_color=False) is False


def test_paint_is_a_no_op_without_colour():
    assert Output(prog="puse").paint("x", "red") == "x"


def test_paint_wraps_in_ansi_when_enabled():
    assert Output(prog="puse", color=True).paint("x", "red") == "\033[31mx\033[0m"


def test_render_mutation_shows_added_and_removed():
    out = Output(prog="puse")
    payload = {
        "atom": "cat/pkg",
        "added": ["lua"],
        "removed": ["-lua"],
        "changed": True,
        "dry_run": False,
        "target": "/etc/portage/package.use/ptools",
    }

    assert render_mutation(out, payload) == (
        "cat/pkg: +lua --lua -> /etc/portage/package.use/ptools"
    )


def test_render_mutation_reports_no_change():
    payload = {"atom": "cat/pkg", "changed": False, "dry_run": True, "added": [], "removed": []}

    assert render_mutation(Output(prog="puse"), payload) == "[dry-run] cat/pkg: no change"


def test_render_field_falls_back_to_a_placeholder():
    assert render_field(Output(prog="puse"), "iuse", [], empty="(none)").endswith("(none)")


def test_failure_writes_plain_text_to_stderr(capsys):
    code = Output(prog="puse").failure(PackageNotFoundError("nope"), usage="usage: puse ...\n")

    assert code == 3
    err = capsys.readouterr().err
    assert err.splitlines() == ["usage: puse ...", "puse: error: nope"]
    assert not re.search(r"\033", err)
