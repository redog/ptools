import os

import pytest

from ptools.config_store import ConfigStore, apply_set, apply_unset, parse_line
from ptools.domain import ConfigMutation
from ptools.errors import InvalidConfigError, PermissionDeniedError, WriteError

ATOM = "app-editors/neovim"


def mutation(operation, *values, atom=ATOM):
    return ConfigMutation(operation=operation, atom=atom, values=values)


def test_parse_line_splits_atom_values_and_comment():
    line = parse_line("  app-editors/neovim lua -python # keep lua\n")
    assert line.indent == "  "
    assert line.atom == "app-editors/neovim"
    assert line.values == ("lua", "-python")
    assert line.comment == "# keep lua"


def test_parse_line_treats_full_comment_as_no_atom():
    assert parse_line("# just a comment\n").atom is None
    assert parse_line("\n").atom is None


@pytest.mark.parametrize(
    ("values", "tokens", "expected"),
    [
        ((), ("lua",), ("lua",)),
        (("lua",), ("lua",), ("lua",)),
        (("-lua",), ("lua",), ("lua",)),
        (("lua", "python"), ("-lua",), ("python", "-lua")),
        (("~amd64",), ("-*",), ("~amd64", "-*")),
    ],
)
def test_apply_set(values, tokens, expected):
    assert apply_set(values, tokens) == expected


def test_apply_unset_drops_both_polarities():
    assert apply_unset(("lua", "-python", "x"), ("lua", "python")) == ("x",)


def test_add_new_entry_creates_file(tmp_path):
    path = tmp_path / "package.use" / "ptools"
    result = ConfigStore().apply_mutation(path, mutation("set", "lua", "python"))

    assert result.changed is True
    assert result.added == ("lua", "python")
    assert path.read_text() == f"{ATOM} lua python\n"
    assert path.stat().st_mode & 0o777 == 0o644


def test_set_reports_only_real_changes(tmp_path):
    path = tmp_path / "ptools"
    path.write_text(f"{ATOM} lua\n")

    result = ConfigStore().apply_mutation(path, mutation("set", "lua", "python"))

    assert result.added == ("python",)
    assert result.removed == ()
    assert path.read_text() == f"{ATOM} lua python\n"


def test_set_is_idempotent(tmp_path):
    path = tmp_path / "ptools"
    path.write_text(f"{ATOM} lua\n")

    result = ConfigStore().apply_mutation(path, mutation("set", "lua"))

    assert result.changed is False
    assert result.added == ()
    assert path.read_text() == f"{ATOM} lua\n"


def test_set_replaces_the_contradicting_token(tmp_path):
    path = tmp_path / "ptools"
    path.write_text(f"{ATOM} -lua python\n")

    result = ConfigStore().apply_mutation(path, mutation("set", "lua"))

    assert result.added == ("lua",)
    assert result.removed == ("-lua",)
    assert path.read_text() == f"{ATOM} python lua\n"


def test_unset_removes_flag_and_negated_flag(tmp_path):
    path = tmp_path / "ptools"
    path.write_text(f"{ATOM} -lua python\n")

    ConfigStore().apply_mutation(path, mutation("unset", "lua"))

    assert path.read_text() == f"{ATOM} python\n"


def test_unset_last_value_removes_the_line(tmp_path):
    path = tmp_path / "ptools"
    path.write_text(f"# comment\n{ATOM} lua\nsys-apps/portage build\n")

    ConfigStore().apply_mutation(path, mutation("unset", "lua"))

    assert path.read_text() == "# comment\nsys-apps/portage build\n"


def test_unset_on_missing_file_is_a_no_op(tmp_path):
    path = tmp_path / "package.use" / "ptools"

    result = ConfigStore().apply_mutation(path, mutation("unset", "lua"))

    assert result.changed is False
    assert not path.exists()


def test_preserves_comments_blanks_and_unrelated_entries(tmp_path):
    content = (
        "# Top comment\n"
        "\n"
        "dev-lang/python  sqlite   -tk\n"
        "\tsys-apps/portage build\n"
        "\n"
        "# trailing note\n"
    )
    path = tmp_path / "ptools"
    path.write_text(content)

    ConfigStore().apply_mutation(path, mutation("set", "lua"))

    assert path.read_text() == content + f"{ATOM} lua\n"


def test_preserves_inline_comment_on_the_managed_entry(tmp_path):
    path = tmp_path / "ptools"
    path.write_text(f"{ATOM} lua  # why we need lua\n")

    ConfigStore().apply_mutation(path, mutation("set", "python"))

    assert path.read_text() == f"{ATOM} lua python # why we need lua\n"


def test_appends_newline_before_adding_to_an_unterminated_file(tmp_path):
    path = tmp_path / "ptools"
    path.write_text("sys-apps/portage build")

    ConfigStore().apply_mutation(path, mutation("set", "lua"))

    assert path.read_text() == f"sys-apps/portage build\n{ATOM} lua\n"


def test_duplicate_atoms_fail_by_default(tmp_path):
    path = tmp_path / "ptools"
    path.write_text(f"{ATOM} lua\n{ATOM} python\n")

    with pytest.raises(InvalidConfigError, match="duplicate entries"):
        ConfigStore().apply_mutation(path, mutation("set", "sqlite"))


def test_duplicate_atoms_merge_on_request(tmp_path):
    path = tmp_path / "ptools"
    path.write_text(f"{ATOM} lua\nsys-apps/portage build\n{ATOM} python\n")

    ConfigStore(merge_duplicates=True).apply_mutation(path, mutation("set", "sqlite"))

    assert path.read_text() == f"{ATOM} lua python sqlite\nsys-apps/portage build\n"


def test_valueless_managed_entry_is_invalid(tmp_path):
    path = tmp_path / "ptools"
    path.write_text(f"{ATOM}\n")

    with pytest.raises(InvalidConfigError, match="has no values"):
        ConfigStore().apply_mutation(path, mutation("set", "lua"))


def test_bare_entry_with_implicit_value_is_read_as_that_value(tmp_path):
    path = tmp_path / "ptools"
    path.write_text(f"{ATOM}\n")

    assert ConfigStore().read_values(path, ATOM, implicit=("~amd64",)) == ("~amd64",)


def test_setting_the_implicit_value_on_a_bare_entry_is_a_no_op(tmp_path):
    path = tmp_path / "ptools"
    path.write_text(f"{ATOM}\n")

    result = ConfigStore().apply_mutation(path, mutation("set", "~amd64"), implicit=("~amd64",))

    assert result.changed is False
    assert result.added == ()
    assert path.read_text() == f"{ATOM}\n"  # the bare entry stays byte-for-byte


def test_setting_a_new_value_on_a_bare_entry_makes_the_implicit_explicit(tmp_path):
    path = tmp_path / "ptools"
    path.write_text(f"{ATOM}\n")

    result = ConfigStore().apply_mutation(path, mutation("set", "-*"), implicit=("~amd64",))

    assert result.added == ("-*",)
    assert result.removed == ()
    assert path.read_text() == f"{ATOM} ~amd64 -*\n"


def test_unsetting_the_implicit_value_removes_the_bare_entry(tmp_path):
    path = tmp_path / "ptools"
    path.write_text(f"# note\n{ATOM}\nsys-apps/portage ~amd64\n")

    result = ConfigStore().apply_mutation(path, mutation("unset", "~amd64"), implicit=("~amd64",))

    assert result.removed == ("~amd64",)
    assert path.read_text() == "# note\nsys-apps/portage ~amd64\n"


def test_semantic_no_op_preserves_nonstandard_spacing(tmp_path):
    path = tmp_path / "ptools"
    path.write_text(f"{ATOM}   lua\n")

    result = ConfigStore().apply_mutation(path, mutation("set", "lua"))

    assert result.changed is False
    assert path.read_text() == f"{ATOM}   lua\n"


def test_non_utf8_target_is_invalid(tmp_path):
    path = tmp_path / "ptools"
    path.write_bytes(b"\xff\xfe not utf-8\n")

    with pytest.raises(InvalidConfigError, match="not valid UTF-8"):
        ConfigStore().apply_mutation(path, mutation("set", "lua"))


def test_dry_run_writes_nothing(tmp_path):
    path = tmp_path / "ptools"
    path.write_text(f"{ATOM} lua\n")
    before = path.read_bytes()

    result = ConfigStore(dry_run=True).apply_mutation(path, mutation("set", "python"))

    assert result.changed is True
    assert result.added == ("python",)
    assert path.read_bytes() == before


def test_dry_run_does_not_create_the_directory(tmp_path):
    path = tmp_path / "package.use" / "ptools"

    ConfigStore(dry_run=True).apply_mutation(path, mutation("set", "lua"))

    assert not path.parent.exists()


def test_read_values_returns_managed_tokens(tmp_path):
    path = tmp_path / "ptools"
    path.write_text(f"# c\n{ATOM} lua -python\n")

    store = ConfigStore()
    assert store.read_values(path, ATOM) == ("lua", "-python")
    assert store.read_values(path, "sys-apps/portage") == ()
    assert store.read_values(tmp_path / "missing", ATOM) == ()


def test_existing_mode_and_group_are_preserved(tmp_path):
    path = tmp_path / "ptools"
    path.write_text(f"{ATOM} lua\n")
    os.chmod(path, 0o640)

    ConfigStore().apply_mutation(path, mutation("set", "python"))

    assert path.stat().st_mode & 0o777 == 0o640


def test_world_writable_mode_is_never_carried_over(tmp_path):
    path = tmp_path / "ptools"
    path.write_text(f"{ATOM} lua\n")
    os.chmod(path, 0o666)

    ConfigStore().apply_mutation(path, mutation("set", "python"))

    assert path.stat().st_mode & 0o002 == 0


def test_refuses_to_write_through_a_symlink(tmp_path):
    real = tmp_path / "elsewhere"
    real.write_text(f"{ATOM} lua\n")
    link = tmp_path / "ptools"
    link.symlink_to(real)

    with pytest.raises(WriteError, match="symlink"):
        ConfigStore().apply_mutation(link, mutation("set", "python"))

    assert real.read_text() == f"{ATOM} lua\n"


def test_flat_layout_parent_is_reported_as_invalid(tmp_path):
    flat = tmp_path / "package.use"
    flat.write_text("# a flat package.use file\n")

    with pytest.raises(InvalidConfigError, match="directory layout"):
        ConfigStore().apply_mutation(flat / "ptools", mutation("set", "lua"))


def test_interrupted_write_leaves_the_target_intact(tmp_path, monkeypatch):
    path = tmp_path / "ptools"
    path.write_text(f"{ATOM} lua\n")
    store = ConfigStore()

    def boom(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(ConfigStore, "_preserve_metadata", boom)

    with pytest.raises(KeyboardInterrupt):
        store.apply_mutation(path, mutation("set", "python"))

    assert path.read_text() == f"{ATOM} lua\n"
    assert list(tmp_path.glob(".ptools-*")) == []


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
def test_unwritable_directory_is_a_permission_error(tmp_path):
    target_dir = tmp_path / "package.use"
    target_dir.mkdir()
    path = target_dir / "ptools"
    path.write_text(f"{ATOM} lua\n")
    os.chmod(target_dir, 0o500)
    try:
        with pytest.raises(PermissionDeniedError, match="re-run as root"):
            ConfigStore().apply_mutation(path, mutation("set", "python"))
    finally:
        os.chmod(target_dir, 0o700)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
def test_unreadable_target_is_a_permission_error(tmp_path):
    path = tmp_path / "ptools"
    path.write_text(f"{ATOM} lua\n")
    os.chmod(path, 0o000)
    try:
        with pytest.raises(PermissionDeniedError, match="cannot read"):
            ConfigStore().apply_mutation(path, mutation("set", "python"))
    finally:
        os.chmod(path, 0o600)
