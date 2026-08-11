"""Machine-checked documentation (Milestone F).

The README is the user-facing contract: its examples, its option list, and its
exit-code table are all checked against the code here, so documentation cannot
drift away from behavior without a test going red.
"""

import re
import shlex
import tomllib
from pathlib import Path

import pytest

from ptools import errors, pkw, puse

REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"
README_TEXT = README.read_text()

#: ```bash fenced blocks, which is where every runnable example lives. ```text
#: blocks are transcripts and are not executed.
_BASH_BLOCK_RE = re.compile(r"```bash\n(.*?)```", re.DOTALL)
_TABLE_ROW_RE = re.compile(r"^\|\s*(\d)\s*\|\s*([^|]+?)\s*\|$", re.MULTILINE)
_ENV_ASSIGNMENT_RE = re.compile(r"^[A-Z_][A-Z0-9_]*=")

COMMANDS = {"puse": puse, "pkw": pkw}


def _readme_examples() -> list[list[str]]:
    """Every `puse`/`pkw` invocation in the README, as argv lists."""
    examples = []
    for block in _BASH_BLOCK_RE.findall(README_TEXT):
        for line in block.splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            words = shlex.split(line)
            # Strip a leading VAR=value prefix (the PTOOLS_CONFIG_ROOT example).
            while words and _ENV_ASSIGNMENT_RE.match(words[0]):
                words.pop(0)
            if words and words[0] in COMMANDS:
                examples.append(words)
    return examples


README_EXAMPLES = _readme_examples()


def test_readme_has_runnable_examples():
    # Guards the extractor itself: a refactor that stops finding examples must
    # not silently turn this whole module into a no-op.
    assert len(README_EXAMPLES) >= 10


@pytest.mark.parametrize("argv", README_EXAMPLES, ids=lambda argv: " ".join(argv))
def test_readme_examples_run(argv, backend, config_root, capsys):
    """Each documented example resolves, parses, and succeeds on the mock backend."""
    module = COMMANDS[argv[0]]
    assert module.main(argv[1:], backend=backend) == 0
    assert capsys.readouterr().err == ""


def test_readme_documents_only_real_options():
    """No README example passes an option the parser does not accept."""
    documented = {word for argv in README_EXAMPLES for word in argv if word.startswith("--")}
    known = set(puse.GLOBAL_OPTIONS) | set(pkw.OPTIONS)
    assert documented <= known


def test_exit_code_table_matches_the_error_taxonomy():
    """The README table is exactly the set of codes the code can produce."""
    table = {int(code): meaning for code, meaning in _TABLE_ROW_RE.findall(README_TEXT)}
    implemented = {
        cls.exit_code
        for cls in vars(errors).values()
        if isinstance(cls, type)
        and issubclass(cls, errors.PtoolsError)
        and cls is not errors.PtoolsError
    }
    assert set(table) == implemented | {0}
    assert table[0] == "Success"
    assert table[errors.PermissionDeniedError.exit_code] == "Permission"
    assert table[errors.WriteError.exit_code] == "Write Error"


def test_only_puse_and_pkw_are_installed_commands():
    """`ptools` is the distribution name, never a console script."""
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    assert pyproject["project"]["scripts"] == {
        "puse": "ptools.puse:main",
        "pkw": "ptools.pkw:main",
    }
    assert pyproject["project"]["requires-python"] == ">=3.11"


@pytest.mark.parametrize(
    ("command", "documented_target"),
    [
        ("puse", "package.use/ptools"),
        ("pkw", "package.accept_keywords/ptools"),
    ],
)
def test_documented_targets_are_the_real_targets(
    command, documented_target, backend, config_root, capsys
):
    """The README's target table matches the path the tool actually reports."""
    assert f"`<config-root>/{documented_target}`" in README_TEXT
    assert COMMANDS[command].main(["--json", "app-editors/neovim"], backend=backend) == 0
    payload = capsys.readouterr().out
    assert str(config_root / documented_target) in payload


def test_readme_carries_the_required_write_warning():
    warning = (
        "ptools modifies Portage configuration under /etc/portage. "
        "Use --dry-run before applying changes."
    )
    assert warning in README_TEXT
