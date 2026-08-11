
import pytest

from ptools.config_store import ConfigStore
from ptools.domain import ConfigMutation
from ptools.errors import InvalidConfigError


def test_config_store_add_new_entry(tmp_path):
    file_path = tmp_path / "package.use/ptools"
    store = ConfigStore()

    mutation = ConfigMutation(operation="set", atom="app-editors/neovim", values=("lua", "python"))
    change = store.apply_mutation(file_path, mutation)

    assert change is not None
    assert "app-editors/neovim lua python\n" in change.after
    assert file_path.read_text() == "app-editors/neovim lua python\n"


def test_config_store_modify_existing(tmp_path):
    file_path = tmp_path / "ptools"
    file_path.write_text("app-editors/neovim lua\n")
    store = ConfigStore()

    mutation = ConfigMutation(operation="set", atom="app-editors/neovim", values=("-lua", "python"))
    change = store.apply_mutation(file_path, mutation)

    assert change is not None
    assert file_path.read_text() == "app-editors/neovim -lua python\n"


def test_config_store_remove_values(tmp_path):
    file_path = tmp_path / "ptools"
    file_path.write_text("app-editors/neovim lua python\n")
    store = ConfigStore()

    mutation = ConfigMutation(operation="unset", atom="app-editors/neovim", values=("lua",))
    store.apply_mutation(file_path, mutation)

    assert file_path.read_text() == "app-editors/neovim python\n"


def test_config_store_remove_last_value(tmp_path):
    file_path = tmp_path / "ptools"
    file_path.write_text("app-editors/neovim lua\n# comment\n")
    store = ConfigStore()

    mutation = ConfigMutation(operation="unset", atom="app-editors/neovim", values=("lua",))
    store.apply_mutation(file_path, mutation)

    assert file_path.read_text() == "# comment\n"


def test_config_store_preserves_comments_and_blanks(tmp_path):
    content = "# Top comment\n\napp-editors/neovim lua\n\n# Bottom comment\n"
    file_path = tmp_path / "ptools"
    file_path.write_text(content)
    store = ConfigStore()

    mutation = ConfigMutation(operation="set", atom="sys-apps/portage", values=("test",))
    store.apply_mutation(file_path, mutation)

    expected = (
        "# Top comment\n\napp-editors/neovim lua\n\n# Bottom comment\nsys-apps/portage test\n"
    )
    assert file_path.read_text() == expected


def test_config_store_dry_run(tmp_path):
    file_path = tmp_path / "ptools"
    file_path.write_text("app-editors/neovim lua\n")
    store = ConfigStore(dry_run=True)

    mutation = ConfigMutation(operation="set", atom="app-editors/neovim", values=("python",))
    change = store.apply_mutation(file_path, mutation)

    assert change is not None
    assert "python" in change.after
    assert file_path.read_text() == "app-editors/neovim lua\n"


def test_config_store_duplicate_error(tmp_path):
    file_path = tmp_path / "ptools"
    file_path.write_text("app-editors/neovim lua\napp-editors/neovim python\n")
    store = ConfigStore()

    mutation = ConfigMutation(operation="set", atom="app-editors/neovim", values=("test",))
    with pytest.raises(InvalidConfigError):
        store.apply_mutation(file_path, mutation)
