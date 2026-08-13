# Portage Tools Modernization Specification

> **Building ptools?** Start with [`build_PROMPT.md`](build_PROMPT.md) — it holds
> the current state, resolved decisions, and remaining milestones. This SPEC is
> the behavioral reference behind it.
>
> **Command surface: superseded throughout.** This document was written while
> an umbrella `ptools <noun> <verb>` command was still on the table, and its
> examples still use that shape. It was resolved against: the only commands are
> `puse` and `pkw`, flat and terse (`puse [OPTIONS] PACKAGE [TOKEN ...]`), and
> `ptools` is the distribution name, not a command. Read every `ptools use set
> X lua` here as `puse X lua`, and `ptools keyword set X '~amd64'` as `pkw X
> '~amd64'`. The *behavior* each example describes still stands — only the
> spelling changed. See `build_PROMPT.md` §4 for the live contract and the
> README for user-facing docs.


```yaml
PROJECT_NAME: ptools
PROJECT_TYPE: Gentoo Portage administration CLI
SOURCE_LANGUAGE: Python 2
TARGET_LANGUAGE: Python 3
TARGET_PLATFORM: Current Gentoo Linux
SOURCE_FILES:
  - ptk.py
  - puse.py
  - pkw.py
PRIMARY_CONFIG_ROOT: /etc/portage
PRIMARY_GOAL: Modernize the original package USE and keyword management workflows
SECONDARY_GOAL: Preserve useful historical behavior without preserving obsolete implementation details
```

## 1. Objective

Rebuild the surviving `ptools` functionality for current Gentoo and current Python.

Provide commands for:

```yaml
USE_FLAG_OPERATIONS:
  - Inspect effective USE state for a package
  - Add enabled USE flags
  - Add disabled USE flags
  - Remove locally configured USE flags
  - Target all package versions
  - Target an exact package version

KEYWORD_OPERATIONS:
  - Add the current architecture testing keyword
  - Add explicit keyword values
  - Add -* where explicitly requested
  - Remove locally configured keyword entries
  - Target all package versions
  - Target an exact package version

PACKAGE_OPERATIONS:
  - Resolve package atoms
  - Detect ambiguous package names
  - List matching packages
  - Inspect installed versions
  - Inspect repository versions
```

Do not preserve unused, broken, or superseded functionality solely because it exists in the original code.

## 2. Source Behavior

Treat the surviving files as the behavioral baseline.

```yaml
ptk.py:
  ROLE: Shared Portage integration and package model
  OBSERVED_RESPONSIBILITIES:
    - Access Portage repository and installed-package databases
    - Resolve CP and CPV values
    - Read IUSE, USE, KEYWORDS, DEPEND, RDEPEND, SLOT, and ebuild paths
    - Read package.use and package.keywords state
    - Write package.use and package.keywords state
    - Compare enabled, disabled, and masked USE flags
    - Prompt for ambiguous package selection

puse.py:
  ROLE: USE flag CLI
  OBSERVED_COMMANDS:
    - show
    - change
    - remove
  OBSERVED_SCOPES:
    - any version
    - exact version
  OBSERVED_MODIFIERS:
    - enable flag
    - disable flag

pkw.py:
  ROLE: Keyword CLI
  OBSERVED_COMMANDS:
    - change
    - remove
    - incomplete cleanup
  OBSERVED_SCOPES:
    - any version
    - exact version
  OBSERVED_MODIFIERS:
    - current architecture testing keyword
    - -*
```

## 3. Authoritative External Interfaces

Use current Gentoo and Portage interfaces.

```yaml
PORTAGE_PYTHON_PACKAGE: portage
PORTAGE_CONFIG_ROOT: /etc/portage
INSTALLED_DATABASE: Portage vartree or supported replacement
REPOSITORY_DATABASE: Portage portdb or supported replacement
PACKAGE_ATOM_IMPLEMENTATION: portage.dep.Atom
PACKAGE_VERSION_IMPLEMENTATION: portage.versions
CLI_PARSER: argparse
TEST_RUNNER: pytest
BUILD_BACKEND: hatchling
PACKAGING_METADATA: pyproject.toml
MINIMUM_PYTHON: Determine from current Gentoo stable Python
```

Reference documentation:

```yaml
PORTAGE_SOURCE: https://github.com/gentoo/portage
PORTAGE_API_DOCS: https://dev.gentoo.org/~zmedico/portage/doc/api/
GENTOO_DEV_MANUAL: https://devmanual.gentoo.org/
GENTOO_HANDBOOK: https://wiki.gentoo.org/wiki/Handbook:AMD64
PACKAGE_ACCEPT_KEYWORDS_DOCS: https://wiki.gentoo.org/wiki//etc/portage/package.accept_keywords
PACKAGE_USE_DOCS: https://wiki.gentoo.org/wiki//etc/portage/package.use
PYTHON_PACKAGING_GUIDE: https://packaging.python.org/en/latest/
PYPROJECT_SPEC: https://packaging.python.org/en/latest/specifications/pyproject-toml/
ARGPARSE_DOCS: https://docs.python.org/3/library/argparse.html
PYTEST_DOCS: https://docs.pytest.org/
```

Before implementation, verify that each linked Portage API remains available in the installed Portage version.

Do not copy an API call from the legacy code without verifying its current public or supported equivalent.

## 4. Discovery Requirements

Perform discovery before selecting the implementation architecture.

```bash
python --version
python -c 'import portage; print(portage.VERSION)'
python -c 'import portage; print(portage.__file__)'
python -c 'from portage.dep import Atom; print(Atom("sys-apps/portage"))'
emerge --info
portageq envvar ROOT
portageq envvar EPREFIX
portageq envvar PORTAGE_CONFIGROOT
portageq envvar ARCH
```

Inspect available Portage APIs.

```bash
python - <<'PY'
import portage
print("settings:", type(portage.settings))
print("db roots:", list(portage.db))
print("root:", portage.settings["ROOT"])
print("configroot:", portage.settings.get("PORTAGE_CONFIGROOT"))
PY
```

Inspect current configuration layouts.

```bash
find /etc/portage/package.use -maxdepth 2 -type f -print 2>/dev/null
find /etc/portage/package.accept_keywords -maxdepth 2 -type f -print 2>/dev/null
find /etc/portage/package.keywords -maxdepth 2 -type f -print 2>/dev/null
```

Ask before implementation when any of these are unresolved.

> **RESOLVED** in `build_PROMPT.md` §3: directory layout for both files, one
> managed aggregate file named `ptools`, **no privilege escalation** (run as
> root yourself; an unwritable target exits 5), and the original command names
> kept as the only two commands. `UNKNOWN_CONFIG_LAYOUT` is the one item still
> pending real-system confirmation (Milestone D).

```yaml
UNKNOWN_CONFIG_LAYOUT:
  - package.use is a file
  - package.use is a directory
  - package.accept_keywords is a file
  - package.accept_keywords is a directory
  - legacy package.keywords is present
  - configuration is managed by another tool

UNKNOWN_WRITE_POLICY:
  - Modify an existing file
  - Create a dedicated ptools file
  - Preserve source file placement
  - Use one file per package
  - Use one managed aggregate file

UNKNOWN_PRIVILEGE_POLICY:
  - Run as root
  - Use sudo only for final writes
  - Generate changes without applying them

UNKNOWN_COMPATIBILITY_POLICY:
  - Preserve original command names
  - Preserve original flags
  - Introduce a new unified CLI
```

Do not assume `/` is the effective root.

Do not assume `/etc/portage` is the effective configuration root.

Do not assume `package.keywords` remains the correct target.

Do not assume package configuration paths are regular files.

## 5. Build-vs-Reuse Decision Rules

Prefer supported Portage APIs and existing Gentoo tools.

```yaml
REUSE_ORDER:
  1: Supported Portage Python API
  2: Stable Portage command with machine-readable output
  3: Existing Gentoo utility with suitable behavior
  4: Small internal implementation
```

Evaluate these tools before reimplementing their behavior:

```yaml
TOOLS:
  - portageq
  - emerge
  - equery
  - euse
  - eix
  - qatom
  - qlist
  - qgrep
```

Do not shell out when the Portage Python API provides a supported, testable equivalent.

Do not use a private Portage API when a stable command provides a safer interface.

Do not parse colorized or human-oriented command output.

Do not recreate Portage atom parsing.

Do not recreate Gentoo version comparison.

Do not recreate repository visibility logic.

Do not recreate profile USE-mask or USE-force evaluation.

Do not recreate package matching when `portage.dep.Atom`, `dbapi.match()`, or a current supported equivalent provides it.

Document each external integration decision.

```yaml
INTEGRATION_DECISION_RECORD:
  OPERATION: package atom parsing
  SELECTED_INTERFACE: portage.dep.Atom
  REJECTED_ALTERNATIVES:
    - custom parser
  REASON: Portage owns Gentoo atom semantics
  TESTS:
    - valid atom accepted
    - invalid atom rejected
    - exact atom preserved
```

## 6. Configuration Write Policy

Default to a dedicated managed file.

```yaml
DEFAULT_USE_TARGET: /etc/portage/package.use/ptools
DEFAULT_KEYWORD_TARGET: /etc/portage/package.accept_keywords/ptools
```

Confirm these paths with the user before enabling writes.

Support file-based installations only after discovery.

Do not rewrite all files under `package.use`.

Do not rewrite all files under `package.accept_keywords`.

Do not erase comments from user-maintained files.

Do not normalize unrelated entries.

Do not reorder unrelated entries.

Do not merge unrelated files.

Do not silently migrate `package.keywords` to `package.accept_keywords`.

Do not write partial files.

Use an atomic write sequence.

```yaml
ATOMIC_WRITE:
  1: Read current target
  2: Parse managed entries
  3: Produce candidate content
  4: Write temporary file in target directory
  5: Flush temporary file
  6: Apply original mode and ownership where applicable
  7: Replace target atomically
```

Create a backup only when requested or configured.

```yaml
BACKUP_SUFFIX: .bak
BACKUP_DEFAULT: false
```

Support dry-run mode.

```bash
ptools --dry-run use set app-editors/neovim lua python
ptools --dry-run keyword set app-editors/neovim '~amd64'
```

Dry-run output must include:

```yaml
DRY_RUN_OUTPUT:
  - Resolved package atom
  - Target configuration file
  - Entries added
  - Entries removed
  - Final candidate line
  - No-write confirmation
```

## 7. Proposed Command Interface

> **SUPERSEDED.** This section is the original proposal. The command surface was
> resolved in `build_PROMPT.md` §3-§4: two first-class commands, `puse` and
> `pkw`, flat and terse (`puse [OPTIONS] PACKAGE [TOKEN ...]`), with inspection
> folded into the bare-`PACKAGE` form. There is no `ptools` executable, no
> subcommand groups, and no `--interactive` mode. Ambiguity exits **4**, not 2.
> The `ptools ...` invocations below are kept only as a record of the proposal.
>
> **Amended 2026-08-13 (Milestone I):** the legacy selection menu returned by
> user request — an ambiguous name offers its candidates as a numbered menu
> when stdin and stderr are both TTYs (no flag; TTY detection is the switch).
> Scripted, piped, `--json`, and `--quiet` invocations still exit 4
> deterministically, so "Scripted operation must remain deterministic" holds.

Provide one primary executable.

```bash
ptools use show PACKAGE
ptools use set PACKAGE FLAG...
ptools use unset PACKAGE FLAG...
ptools keyword show PACKAGE
ptools keyword set PACKAGE KEYWORD...
ptools keyword unset PACKAGE KEYWORD...
ptools package resolve PACKAGE
ptools package versions PACKAGE
```

Support exact atoms directly.

```bash
ptools use set '=app-editors/neovim-0.10.4' lua
ptools keyword set '=app-editors/neovim-0.10.4' '~amd64'
```

Support non-versioned atoms directly.

```bash
ptools use set app-editors/neovim lua
ptools keyword set app-editors/neovim '~amd64'
```

Support package names without categories only when resolution is unambiguous.

```bash
ptools package resolve neovim
```

On ambiguity:

```yaml
EXIT_CODE: 2
OUTPUT:
  - Matching package atoms
  - Instruction to rerun with a category-qualified atom
```

Do not prompt interactively by default.

Optional interactive selection:

```bash
ptools --interactive package resolve PACKAGE
```

Scripted operation must remain deterministic.

## 8. Compatibility Interface

> **SUPERSEDED.** Resolved: `puse` and `pkw` are retained as the *only*
> commands, and they are not wrappers — they call the service layer directly.
> The legacy mode switches are not implemented; see `docs/legacy-behavior.md`
> for how each one maps onto the new shape.

Evaluate whether legacy commands should be retained as wrappers.

```yaml
LEGACY_COMMANDS:
  - puse
  - pkw
```

Possible mappings:

```bash
puse --show app-editors/neovim
ptools use show app-editors/neovim

puse --change --any app-editors/neovim lua
ptools use set app-editors/neovim lua

puse --change --any --not app-editors/neovim lua
ptools use set app-editors/neovim -lua

pkw --change --any app-editors/neovim
ptools keyword set app-editors/neovim '~${ARCH}'
```

Do not implement compatibility flags until their precise old semantics are documented by tests.

Do not preserve successful exit code `1`.

## 9. Python Architecture

Use a small layered design.

```yaml
LAYERS:
  cli:
    RESPONSIBILITY:
      - Parse arguments
      - Validate command combinations
      - Render output
      - Convert exceptions to exit codes

  services:
    RESPONSIBILITY:
      - Resolve package requests
      - Calculate requested mutations
      - Coordinate dry-run and write operations

  portage_adapter:
    RESPONSIBILITY:
      - Access supported Portage APIs
      - Resolve atoms
      - Query repository packages
      - Query installed packages
      - Query metadata
      - Query effective USE state

  config_store:
    RESPONSIBILITY:
      - Read managed configuration
      - Parse managed lines
      - Modify entries
      - Render deterministic output
      - Write atomically

  domain:
    RESPONSIBILITY:
      - Typed immutable values
      - Package references
      - USE mutations
      - Keyword mutations
      - Planned file changes
```

Suggested package structure:

```text
ptools/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── ptools/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── errors.py
│       ├── domain.py
│       ├── services.py
│       ├── portage_adapter.py
│       ├── config_store.py
│       └── output.py
└── tests/
    ├── unit/
    │   ├── test_atoms.py
    │   ├── test_config_store.py
    │   ├── test_services.py
    │   └── test_cli.py
    └── integration/
        ├── test_portage_queries.py
        └── test_sandbox_writes.py
```

## 10. Data Model

Prefer immutable typed structures.

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class PackageRequest:
    raw: str
    exact: bool


@dataclass(frozen=True)
class ResolvedPackage:
    atom: str
    cp: str
    cpv: str | None
    installed_versions: tuple[str, ...]
    repository_versions: tuple[str, ...]


@dataclass(frozen=True)
class ConfigMutation:
    operation: Literal["set", "unset"]
    atom: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class FileChange:
    path: Path
    before: str
    after: str
```

Do not expose Portage global objects throughout the application.

Do not store mutable Portage dictionaries as application state.

Do not make domain objects write files.

Do not mix terminal coloring with domain values.

## 11. Package Resolution

Accept Gentoo package atoms.

```yaml
SUPPORTED_INPUT:
  - app-editors/neovim
  - =app-editors/neovim-0.10.4
  - '~app-editors/neovim-0.10.4'
  - neovim
```

Resolution rules:

```yaml
CATEGORY_QUALIFIED_ATOM:
  ACTION: Parse and validate directly

UNQUALIFIED_PACKAGE_NAME:
  ACTION: Search repositories and installed database
  ZERO_MATCHES: Fail
  ONE_MATCH: Resolve
  MULTIPLE_MATCHES: Fail unless --interactive

EXACT_ATOM:
  ACTION: Preserve operator and CPV

NONEXACT_ATOM:
  ACTION: Preserve package-level scope
```

Do not silently select the newest version when the user requested an ambiguous name.

Do not silently convert an exact atom to a package-wide atom.

Do not silently convert a package-wide atom to an exact atom.

## 12. USE Flag Semantics

Represent USE configuration tokens exactly as Portage expects.

```yaml
ENABLE_FLAG: flag
DISABLE_FLAG: -flag
REMOVE_LOCAL_OVERRIDE: Remove matching flag and -flag tokens from the managed entry
```

Examples:

```bash
ptools use set app-editors/neovim lua python
ptools use set app-editors/neovim -gtk
ptools use unset app-editors/neovim lua gtk
```

`use show` output must distinguish:

```yaml
USE_STATES:
  - Enabled by effective configuration
  - Disabled by effective configuration
  - Forced
  - Masked
  - Declared by IUSE
  - Locally configured by ptools
  - Installed package build-time USE state
```

Do not infer effective USE state solely from `package.use`.

Do not describe every flag absent from `USE` as locally disabled.

Do not discard IUSE defaults such as `+flag` or `-flag`.

Use current Portage APIs for effective state whenever available.

## 13. Keyword Semantics

Use `package.accept_keywords` as the modern default target, subject to discovery.

```yaml
DEFAULT_TESTING_KEYWORD: ~${ARCH}
UNKEYWORD_ALL_TOKEN: -*
```

Commands:

```bash
ptools keyword set app-editors/neovim '~amd64'
ptools keyword set app-editors/neovim '-*' '~amd64'
ptools keyword unset app-editors/neovim '~amd64'
```

Provide architecture expansion only when explicitly requested.

```bash
ptools keyword set app-editors/neovim --testing
```

Equivalent resolved operation:

```yaml
ARCH: amd64
KEYWORD: ~amd64
```

Do not assume `amd64`.

Do not interpret `-*` as permission to remove other tokens.

Do not automatically remove keyword entries because newer stable versions exist.

Do not implement the legacy `--fix-kw` feature in the first release.

A future cleanup command must use Portage visibility and keyword semantics rather than string comparison.

## 14. Parsing Existing Configuration

Support comments and blank lines.

```text
# Required for Lua support
app-editors/neovim lua

# Temporary keyword
=app-editors/neovim-0.10.4 ~amd64
```

Initial managed-file parser requirements:

```yaml
PRESERVE:
  - Comments
  - Blank lines
  - Unknown valid lines
  - Whitespace outside modified managed entries when practical

MODIFY:
  - Exact matching atom entries
  - Tokens explicitly requested

REJECT:
  - Invalid atoms in lines selected for mutation
  - Invalid requested USE tokens
  - Invalid requested keyword tokens
```

When duplicate matching atoms exist:

```yaml
DEFAULT_ACTION: Fail with diagnostic
OPTIONAL_ACTION: Normalize only with explicit --merge-duplicates
```

Do not silently collapse duplicate entries.

Do not parse general Portage configuration as a simplistic whitespace-only dictionary if doing so loses semantics.

## 15. Output

Default output must be plain and script-readable.

```yaml
COLOR_DEFAULT: auto
COLOR_AUTO_RULE: Enable only on a terminal
COLOR_DISABLE_FLAG: --no-color
JSON_FLAG: --json
QUIET_FLAG: --quiet
```

Example JSON result:

```json
{
  "operation": "use.set",
  "atom": "app-editors/neovim",
  "target": "/etc/portage/package.use/ptools",
  "added": ["lua"],
  "removed": [],
  "changed": true,
  "dry_run": false
}
```

Do not include ANSI escape codes in JSON.

Do not print success messages to stderr.

Do not print errors to stdout.

## 16. Exit Codes

```yaml
EXIT_SUCCESS: 0
EXIT_USAGE: 2
EXIT_NOT_FOUND: 3
EXIT_AMBIGUOUS: 4
EXIT_PERMISSION: 5
EXIT_INVALID_CONFIG: 6
EXIT_PORTAGE_ERROR: 7
EXIT_WRITE_ERROR: 8
```

Tests must verify every documented exit code.

## 17. Error Handling

Define application-specific exceptions.

```python
class PtoolsError(Exception):
    pass


class PackageNotFoundError(PtoolsError):
    pass


class AmbiguousPackageError(PtoolsError):
    pass


class InvalidConfigError(PtoolsError):
    pass


class PortageIntegrationError(PtoolsError):
    pass
```

Do not use bare `except:`.

Do not catch `Exception` without adding context or re-raising.

Do not convert programming errors into “package not found.”

Do not call `sys.exit()` below the CLI boundary.

## 18. Security and Privilege Boundaries

```yaml
NETWORK_ACCESS: none
DEFAULT_WRITE_ACCESS: disabled during dry-run
EXPECTED_PRIVILEGED_PATH: /etc/portage
SHELL_EXECUTION: prohibited unless an approved external command is required
```

Do not invoke a shell with interpolated user input.

Do not use `shell=True`.

Do not follow arbitrary symlinks during privileged writes without validating the target.

Do not change ownership or permissions beyond preserving the existing target.

Do not create world-writable files.

Do not modify files outside the resolved Portage configuration root.

Do not execute `emerge`.

Do not execute `dispatch-conf`.

Do not execute `etc-update`.

Do not perform package installation or removal.

## 19. Dependency Policy

Prefer the standard library.

```yaml
RUNTIME_DEPENDENCIES:
  REQUIRED:
    - portage
  OPTIONAL:
    - none initially

DEVELOPMENT_DEPENDENCIES:
  - pytest
  - pytest-cov
  - mypy
  - ruff
```

Do not add Click, Typer, Rich, Pydantic, or another framework without demonstrating a requirement not reasonably met by the standard library.

Do not vendor Portage code.

## 20. Code Quality

```yaml
FORMATTER_LINTER: ruff
TYPE_CHECKER: mypy
TEST_RUNNER: pytest
MINIMUM_TEST_COVERAGE: 85
TYPE_CHECK_TARGET: src/ptools
```

Required commands:

```bash
ruff check .
ruff format --check .
mypy src/ptools
pytest
pytest --cov=ptools --cov-report=term-missing --cov-fail-under=85
```

Do not mark a task complete while any required command fails.

## 21. Test Strategy

Use unit tests without requiring a live Gentoo system.

Provide adapter interfaces and fakes.

```python
from typing import Protocol


class PortageBackend(Protocol):
    def resolve(self, request: str) -> ResolvedPackage: ...
    def effective_use(self, atom: str) -> tuple[str, ...]: ...
    def installed_use(self, atom: str) -> tuple[str, ...]: ...
    def iuse(self, atom: str) -> tuple[str, ...]: ...
```

Integration tests may require Gentoo.

Mark them explicitly.

```bash
pytest -m 'not integration'
pytest -m integration
```

Required test cases:

```yaml
ATOM_TESTS:
  - Parse category-qualified atom
  - Parse exact atom
  - Reject invalid atom
  - Detect ambiguous unqualified name
  - Preserve atom operator

USE_TESTS:
  - Add enabled flag
  - Add disabled flag
  - Remove enabled flag
  - Remove disabled flag
  - Remove both forms when unset is requested
  - Preserve unrelated flags
  - Reject invalid flag token
  - Produce no change for idempotent operation

KEYWORD_TESTS:
  - Add testing keyword
  - Add -*
  - Remove one keyword
  - Preserve unrelated keywords
  - Resolve current architecture
  - Produce no change for idempotent operation

FILE_TESTS:
  - Preserve comments
  - Preserve blank lines
  - Preserve unrelated entries
  - Detect duplicate atoms
  - Write atomically
  - Preserve file mode
  - Dry-run performs no write

CLI_TESTS:
  - Help exits 0
  - Version exits 0
  - Usage failure exits 2
  - Package not found uses documented exit code
  - JSON output is valid JSON
  - JSON output contains no ANSI escapes
```

## 22. Packaging

> **PARTLY SUPERSEDED.** The `[project.scripts]` block below is the *original*
> proposal and no longer matches the tree: there is no `ptools` command and no
> `ptools.compat` package. The resolved entry points are `puse =
> "ptools.puse:main"` and `pkw = "ptools.pkw:main"`, and they are checked
> against `pyproject.toml` by `tests/unit/test_docs.py`. Minimum Python was
> resolved to 3.11 (Milestone D confirmed 3.14.6 on the validation host).

Use `pyproject.toml`.

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ptools"
version = "0.1.0"
description = "Gentoo Portage configuration tools"
requires-python = ">=3.11"
dependencies = []

[project.scripts]
ptools = "ptools.cli:main"
puse = "ptools.compat.puse:main"
pkw = "ptools.compat.pkw:main"
```

Determine the actual minimum Python version during discovery.

Do not retain `>=3.11` without checking current Gentoo support requirements.

Do not publish to PyPI as part of the modernization task.

## 23. Documentation

README requirements:

```yaml
README_SECTIONS:
  - Purpose
  - Historical background
  - Supported Gentoo versions
  - Supported Python versions
  - Installation
  - Read-only examples
  - Dry-run examples
  - Write examples
  - Configuration target policy
  - Exit codes
  - JSON output
  - Known limitations
  - Migration from puse
  - Migration from pkw
```

Include this warning before write examples:

```text
ptools modifies Portage configuration under /etc/portage. Use --dry-run before applying changes.
```

Do not describe unsupported Portage versions as supported.

Do not claim compatibility based only on unit tests.

## 24. Deferred Features

```yaml
DEFERRED:
  - Automatic removal of obsolete keyword entries
  - Whole-tree keyword cleanup
  - Whole-tree USE cleanup
  - Dependency graph visualization
  - Ebuild creation
  - Ebuild editing
  - Overlay management
  - Repository synchronization
  - Package installation
  - Package removal
  - Automatic etc-update integration
```

Do not implement deferred features during the initial modernization.

## 25. Roadmap

### Phase 1: Environment Discovery

Tasks:

```yaml
TASKS:
  - Record Python version
  - Record Portage version
  - Record Portage module location
  - Record ROOT
  - Record PORTAGE_CONFIGROOT
  - Record ARCH
  - Record package.use layout
  - Record package.accept_keywords layout
  - Identify supported Portage APIs
  - Identify required external commands
```

Completion Check:

```bash
test -f docs/environment.md
grep -q '^PYTHON_VERSION:' docs/environment.md
grep -q '^PORTAGE_VERSION:' docs/environment.md
grep -q '^PORTAGE_CONFIGROOT:' docs/environment.md
grep -q '^ARCH:' docs/environment.md
grep -q '^PACKAGE_USE_LAYOUT:' docs/environment.md
grep -q '^PACKAGE_KEYWORD_LAYOUT:' docs/environment.md
```

### Phase 2: Behavioral Inventory

Tasks:

```yaml
TASKS:
  - Map each legacy option to intended behavior
  - Mark broken legacy behavior
  - Mark obsolete legacy behavior
  - Define compatibility decisions
  - Create golden examples for supported behavior
```

Completion Check:

```bash
test -f docs/legacy-behavior.md
grep -q 'puse --show' docs/legacy-behavior.md
grep -q 'puse --change' docs/legacy-behavior.md
grep -q 'puse --remove' docs/legacy-behavior.md
grep -q 'pkw --change' docs/legacy-behavior.md
grep -q 'pkw --remove' docs/legacy-behavior.md
grep -q 'DEFERRED.*fix-kw' docs/legacy-behavior.md
```

### Phase 3: Project Skeleton

Tasks:

```yaml
TASKS:
  - Create pyproject.toml
  - Create package layout
  - Create CLI entry point
  - Configure pytest
  - Configure Ruff
  - Configure mypy
```

Completion Check:

```bash
python -m build
ptools --help
ruff check .
ruff format --check .
mypy src/ptools
pytest
```

### Phase 4: Portage Adapter

Tasks:

```yaml
TASKS:
  - Parse atoms using Portage
  - Resolve category-qualified atoms
  - Resolve unqualified package names
  - Query installed versions
  - Query repository versions
  - Query package metadata
  - Query effective USE state
  - Query architecture
```

Completion Check:

```bash
pytest tests/unit/test_atoms.py
pytest tests/unit/test_portage_adapter.py
pytest -m integration tests/integration/test_portage_queries.py
```

### Phase 5: Read-Only CLI

Tasks:

```yaml
TASKS:
  - Implement package resolve
  - Implement package versions
  - Implement use show
  - Implement keyword show
  - Implement JSON output
  - Implement documented exit codes
```

Completion Check:

```bash
ptools package resolve sys-apps/portage
ptools package versions sys-apps/portage
ptools use show sys-apps/portage
ptools keyword show sys-apps/portage
ptools --json package resolve sys-apps/portage | python -m json.tool
```

### Phase 6: Configuration Store

Tasks:

```yaml
TASKS:
  - Parse dedicated managed USE file
  - Parse dedicated managed keyword file
  - Preserve comments
  - Preserve blank lines
  - Detect duplicate atoms
  - Render deterministic output
  - Implement atomic writes
```

Completion Check:

```bash
pytest tests/unit/test_config_store.py
pytest tests/integration/test_sandbox_writes.py
```

### Phase 7: Mutation CLI

Tasks:

```yaml
TASKS:
  - Implement use set
  - Implement use unset
  - Implement keyword set
  - Implement keyword unset
  - Implement dry-run
  - Implement idempotent writes
```

Completion Check:

```bash
pytest tests/unit/test_services.py
pytest tests/unit/test_cli.py
pytest tests/integration/test_sandbox_writes.py
```

### Phase 8: Legacy Compatibility

> **SUPERSEDED — no compatibility layer was built.** `puse` and `pkw` are the
> primary commands rather than wrappers over one, so there is nothing to wrap
> and no deprecation guidance to emit. The legacy mode switches map onto the new
> shape in `docs/legacy-behavior.md` and in the README's two migration tables.

Tasks:

```yaml
TASKS:
  - Implement puse wrapper for supported behavior
  - Implement pkw wrapper for supported behavior
  - Emit deprecation guidance
  - Match documented legacy semantics
```

Completion Check:

```bash
puse --help
pkw --help
# The compat suites below were never written; the equivalent coverage lives in
# tests/unit/test_puse.py, tests/unit/test_pkw.py and tests/unit/test_docs.py.
```

### Phase 9: Gentoo Validation

Tasks:

```yaml
TASKS:
  - Test against a current Gentoo installation
  - Test file-based configuration
  - Test directory-based configuration
  - Test non-root dry-run
  - Test privileged write
  - Verify Portage consumes generated entries
```

Completion Check:

```bash
ptools --dry-run use set sys-apps/portage test
ptools --dry-run keyword set sys-apps/portage --testing
portageq envvar ARCH
emerge -pv sys-apps/portage
```

Record results:

```yaml
VALIDATION_RECORD:
  GENTOO_PROFILE:
  PORTAGE_VERSION:
  PYTHON_VERSION:
  PACKAGE_USE_LAYOUT:
  PACKAGE_KEYWORD_LAYOUT:
  READ_ONLY_TESTS:
  DRY_RUN_TESTS:
  WRITE_TESTS:
  PORTAGE_CONSUMPTION_TEST:
```

### Phase 10: Release Candidate

Tasks:

```yaml
TASKS:
  - Complete documentation
  - Complete migration guide
  - Run all static checks
  - Run all unit tests
  - Run Gentoo integration tests
  - Build source archive and wheel
```

Completion Check:

```bash
ruff check .
ruff format --check .
mypy src/ptools
pytest --cov=ptools --cov-report=term-missing --cov-fail-under=85
python -m build
python -m twine check dist/*
```

## 26. Definition of Done

```yaml
DONE:
  - Read-only package queries work on current Gentoo
  - USE changes target a confirmed Portage configuration path
  - Keyword changes target a confirmed Portage configuration path
  - Dry-run performs no writes
  - Writes are atomic
  - Comments and unrelated entries are preserved
  - Exact and package-wide atoms remain distinct
  - Ambiguous package names fail deterministically
  - Effective USE state comes from Portage
  - Atom parsing comes from Portage
  - Version comparison comes from Portage
  - All documented exit codes are tested
  - Unit test coverage is at least 85 percent
  - Ruff passes
  - Mypy passes
  - Pytest passes
  - Gentoo integration results are documented
  - Legacy wrappers either work as documented or are explicitly omitted
```

## 27. Agent Boundaries

Do not modify `/etc/portage` during development without explicit approval.

Do not run write commands against the live configuration before sandbox tests pass.

Do not invent missing behavior from the lost fourth tool.

Do not assume the lost fourth tool was an ebuild generator.

Do not expand project scope based on comments or unfinished functions in the old code.

Do not preserve Python 2 structure.

Do not preserve global mutable state.

Do not preserve obsolete Portage imports.

Do not preserve private Portage APIs when supported alternatives exist.

Do not implement custom atom parsing.

Do not implement custom Gentoo version comparison.

Do not replace Portage behavior with approximations.

Do not erase comments.

Do not rewrite unrelated configuration.

Do not publish a release.

Do not create an ebuild until the Python package and runtime behavior are complete.

Do not claim completion until every roadmap Completion Check passes or the failure is explicitly documented.

## 28. Required Agent Questions

Ask these before enabling writes:

```yaml
QUESTIONS:
  - What Gentoo system should be used for integration testing?
  - What is the output of portageq envvar PORTAGE_CONFIGROOT?
  - Is package.use a file or directory?
  - Is package.accept_keywords a file or directory?
  - Should ptools own dedicated files named ptools?
  - Should legacy puse and pkw commands remain available?
  - Should privileged writes run directly as root or through sudo?
  - Should backups be created before every write?
```

Ask when an implementation choice is not supported by the discovered Portage version.

Ask when existing configuration contains duplicate entries that cannot be modified without normalization.

Ask when the requested change would alter a file not owned by `ptools`.
