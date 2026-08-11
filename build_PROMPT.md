# System Architecture & Topology

```yaml
Project: ptools
Project Type: Gentoo Portage administration CLI
Execution Model: Local command-line process
Development Host: Container at /workspace/ptools
Target Host: Current Gentoo Linux workstation or server
Cloud Service: none
Network Service: none
Inbound API Endpoints: none
Outbound API Endpoints: none at runtime
Gateway: none
Proxy: none at runtime
Source Root: /workspace/ptools
Python Package Root: /workspace/ptools/src/ptools
Test Root: /workspace/ptools/tests
Effective Root: discover from portage.settings["ROOT"] or portageq envvar ROOT
Portage Config Root: discover from PORTAGE_CONFIGROOT; do not assume /
Default USE Target Candidate: ${PORTAGE_CONFIGROOT}/etc/portage/package.use/ptools
Default Keyword Target Candidate: ${PORTAGE_CONFIGROOT}/etc/portage/package.accept_keywords/ptools
Installed Package Database: Portage vartree or verified supported replacement
Repository Package Database: Portage portdb or verified supported replacement
Runtime Logs: stdout for results; stderr for errors
Persistent Application Logs: none specified
Build Metadata: /workspace/ptools/pyproject.toml
Runtime Network Access: none
```

```text
CLI arguments
  → argparse validation
  → service operation
  → Portage adapter
      → supported Portage Python API
      → repository database + installed-package database + effective settings
  → domain result / planned mutation
  → config store
      → read managed file
      → parse and preserve unrelated content
      → render candidate
      → dry-run output OR atomic file replacement
  → plain text or JSON on stdout

Validation/configuration failures → application exception → CLI exit-code mapping → stderr
```

# Hard Constraints & Capabilities

```yaml
Development CPU Cores: 3 logical CPUs
Development RAM Total: 19252858880 bytes
Development RAM Available at discovery: 18542030848 bytes
Development Swap: 0 bytes
Development Storage Filesystem: /dev/vda
Development Storage Available at discovery: 30426923008 bytes
Development Source Path: /workspace/ptools
Development Python: 3.14.4
Development Portage Python Package: unavailable
Development Gentoo Commands: emerge, portageq, equery, euse, eix, qatom, qlist, and qgrep unavailable
Development /etc/portage: unavailable
GPU: not required by the design; no GPU capability or allocation established
GPU VRAM: not applicable
Model Size Limit: not applicable; no local inference
Runtime Dependencies: portage plus Python standard library
Optional Runtime Dependencies: none initially
CLI Parser: argparse
Build Backend: hatchling
Test Runner: pytest
Minimum Test Coverage: 85 percent
Concurrent Connection Limit: not applicable; no network listener
Network Bandwidth: not applicable at runtime
Request Timeout: not applicable; synchronous local CLI
Operation Timeout: unspecified; obtain approval before introducing one
Storage Quota: no application-specific quota specified
Target Python Minimum: unresolved; derive from current Gentoo stable Python
Target Portage Version: unresolved; record from the integration system
Target Architecture: unresolved; read from Portage and never assume amd64
Target RAM and CPU: no minimum specified
```

```yaml
Build Blockers:
  Portage API Validation: blocked in the development container because the portage module is absent
  Gentoo Integration Validation: requires a user-designated current Gentoo system
  External Existing-Solution Validation: attempted against official Gentoo Portage API, Gentoo Wiki, and gentoo/portage sources; network proxy returned HTTP 403
  Write Enablement: blocked until configuration layout, target ownership, and privilege policy are confirmed
```

# Agentic Boundaries (The "Do Not Touch" List)

```text
✗ Do not modify /etc/portage during development without explicit approval.
✗ Do not enable writes until PORTAGE_CONFIGROOT and the package.use and package.accept_keywords layouts are confirmed.
✗ Do not run write commands against live Portage configuration before sandbox write tests pass.
✗ Do not modify files outside the resolved Portage configuration root.
✗ Do not rewrite all files under package.use or package.accept_keywords.
✗ Do not erase comments, blank lines, unknown valid lines, or unrelated entries.
✗ Do not normalize or merge duplicate atom entries without explicit --merge-duplicates authorization.
✗ Do not silently migrate package.keywords to package.accept_keywords.
✗ Do not follow arbitrary symlinks during privileged writes.
✗ Do not change ownership or permissions except to preserve an existing target.
✗ Do not create world-writable files.
✗ Do not log, print, store, or commit credentials or secrets.
✗ Do not invoke a shell with interpolated user input.
✗ Do not use shell=True.
✗ Do not execute emerge, dispatch-conf, or etc-update.
✗ Do not install or remove packages.
✗ Do not restart services or containers; none are required by this CLI.
✗ Do not alter network routes, gateways, proxies, or firewall rules.
✗ Do not publish a release or upload to PyPI.
✗ Do not create an ebuild before package and runtime behavior are complete.
✗ Do not implement custom Gentoo atom parsing, version comparison, repository visibility, USE-mask, USE-force, or package matching.
✗ Do not use private Portage APIs when a verified supported API or safer stable command exists.
✗ Do not preserve Python 2 structure, obsolete Portage imports, global mutable Portage state, or successful exit code 1.
✗ Do not implement the legacy --fix-kw cleanup in the initial release.
✗ Do not invent behavior for the lost fourth tool or expand scope from unfinished legacy code.
✗ Do not add Click, Typer, Rich, Pydantic, or another framework without a demonstrated unmet requirement.
✗ Do not vendor Portage code.
✗ Do not claim Gentoo compatibility from unit tests alone.
✗ Do not mark a milestone complete while its measurable checks fail or remain unrecorded.
```

# Step-by-Step Implementation Roadmap

1. [Validate Environment and Existing Solutions]
   - What: Run discovery on the user-designated current Gentoo system; record Python, Portage, ROOT, EPREFIX, PORTAGE_CONFIGROOT, ARCH, configuration layouts, installed tools, and supported Portage interfaces. Evaluate `portageq`, `emerge`, `equery`, `euse`, `eix`, `qatom`, `qlist`, and `qgrep` against the reuse order. Confirm every external integration decision against installed Portage behavior or official documentation.
   - Depends On: User identifies the Gentoo integration system and supplies or authorizes access to its Portage configuration metadata.
   - Completion Check: `docs/environment.md` exists and contains nonempty `PYTHON_VERSION`, `PORTAGE_VERSION`, `PORTAGE_MODULE`, `ROOT`, `EPREFIX`, `PORTAGE_CONFIGROOT`, `ARCH`, `PACKAGE_USE_LAYOUT`, `PACKAGE_KEYWORD_LAYOUT`, and `EXISTING_TOOL_DECISIONS`; the Portage `Atom` import and a supported database match operation succeed on that system.
   - Estimated Complexity: Moderate

2. [Resolve Write and Compatibility Policies]
   - What: Obtain explicit decisions for managed target files, file-versus-directory layouts, privileged writes, backups, and legacy `puse`/`pkw` wrappers.
   - Depends On: Milestone 1
   - Completion Check: `docs/environment.md` records concrete values for `USE_TARGET`, `KEYWORD_TARGET`, `PRIVILEGE_POLICY`, `BACKUP_DEFAULT`, `LEGACY_PUSE`, and `LEGACY_PKW`; no value is `unknown`.
   - Estimated Complexity: Simple

3. [Inventory Legacy Behavior]
   - What: Map `puse.py`, `pkw.py`, and `ptk.py` behavior to supported, broken, obsolete, and deferred behavior; create golden examples without retaining obsolete implementation details.
   - Depends On: Milestone 1
   - Completion Check: `docs/legacy-behavior.md` covers `puse --show`, `puse --change`, `puse --remove`, `pkw --change`, and `pkw --remove`, and marks `pkw --fix-kw` as deferred.
   - Estimated Complexity: Moderate

4. [Create Python 3 Project Skeleton]
   - What: Add Hatchling packaging, the layered `src/ptools` package, argparse entry point, test structure, Ruff configuration, and mypy configuration using the discovered minimum Python version.
   - Depends On: Milestones 1 and 3
   - Completion Check: The source distribution and wheel build; `ptools --help` exits 0; Ruff, mypy, and the initial pytest suite pass.
   - Estimated Complexity: Moderate

5. [Implement the Portage Adapter]
   - What: Isolate supported Portage APIs for atom parsing, deterministic package resolution, repository and installed versions, metadata, effective USE state, and architecture. Preserve atom operators and distinguish exact from package-wide requests.
   - Depends On: Milestone 4
   - Completion Check: Unit adapter tests pass with fakes; marked integration tests pass on the designated Gentoo system for a category-qualified atom, an exact atom, an invalid atom, and an ambiguous unqualified name.
   - Estimated Complexity: Complex

6. [Implement Read-Only Commands]
   - What: Add `package resolve`, `package versions`, `use show`, and `keyword show` with plain and JSON output plus documented exit-code mapping.
   - Depends On: Milestone 5
   - Completion Check: All four commands succeed for `sys-apps/portage` on the designated Gentoo system; JSON output parses with a standards-compliant JSON parser; not-found and ambiguous cases return their specified exit codes.
   - Estimated Complexity: Moderate

7. [Implement the Managed Configuration Store]
   - What: Parse confirmed managed USE and keyword targets, preserve comments and unrelated content, reject invalid selected entries, detect duplicates, render deterministically, and replace files atomically while preserving applicable mode and ownership.
   - Depends On: Milestones 2 and 4
   - Completion Check: Unit and sandbox integration tests prove comment, blank-line, unknown-line, permission, and unrelated-entry preservation; duplicate atoms fail diagnostically; an interrupted candidate write never produces a partial target.
   - Estimated Complexity: Complex

8. [Implement Mutation Commands]
   - What: Add USE and keyword set/unset operations, `--testing` architecture expansion, `-*`, dry-run, idempotency, and confirmed managed targets.
   - Depends On: Milestones 5, 6, and 7
   - Completion Check: Service, CLI, and sandbox write tests pass; dry-run leaves target bytes unchanged; repeated identical operations report `changed: false`; exact and package-wide atoms remain distinct.
   - Estimated Complexity: Complex

9. [Implement Approved Legacy Wrappers]
   - What: Implement only the explicitly approved `puse` and `pkw` compatibility mappings and emit deprecation guidance; omit `--fix-kw`.
   - Depends On: Milestones 2 and 8
   - Completion Check: Each approved wrapper has passing CLI tests and `--help` exits 0; every rejected legacy behavior is documented rather than silently approximated.
   - Estimated Complexity: Moderate

10. [Validate on Current Gentoo]
   - What: Validate read-only commands, non-root dry-run, file- and directory-based sandbox layouts, an approved privileged write, and Portage consumption of generated entries.
   - Depends On: Milestone 8 and Milestone 9 when wrappers are approved
   - Completion Check: `docs/gentoo-validation.md` contains the tested profile, Portage and Python versions, layouts, exact results for read-only/dry-run/write tests, and evidence that Portage consumes the generated sandbox or approved live entries.
   - Estimated Complexity: Complex

11. [Produce the Release Candidate]
   - What: Complete machine-checked documentation and migration guidance, run all quality gates, and build local release artifacts without publishing.
   - Depends On: Milestone 10
   - Completion Check: Ruff check and format check pass; mypy passes; pytest coverage is at least 85 percent; all Gentoo integration tests pass; wheel and source archive build; Twine validates both artifacts.
   - Estimated Complexity: Moderate

# Tool & Schema Requirements

```yaml
Project Metadata:
  Name: ptools
  Language: Python 3
  Minimum Python: ${DISCOVERED_CURRENT_GENTOO_MINIMUM}
  Build File: pyproject.toml
  Build Backend: hatchling
  Primary Executable: ptools
  Optional Compatibility Executables: [puse, pkw]
Environment Variables:
  ROOT: ${PORTAGE_DISCOVERED_ROOT}
  EPREFIX: ${PORTAGE_DISCOVERED_EPREFIX}
  PORTAGE_CONFIGROOT: ${PORTAGE_DISCOVERED_CONFIGROOT}
  ARCH: ${PORTAGE_DISCOVERED_ARCH}
Managed Configuration:
  USE_TARGET: ${CONFIRMED_USE_TARGET}
  KEYWORD_TARGET: ${CONFIRMED_KEYWORD_TARGET}
  BACKUP_SUFFIX: .bak
  BACKUP_DEFAULT: false
Output:
  COLOR_DEFAULT: auto
  JSON_FLAG: --json
  QUIET_FLAG: --quiet
  COLOR_DISABLE_FLAG: --no-color
```

```bash
ptools [--dry-run] [--interactive] [--json] [--quiet] [--no-color] use show PACKAGE
ptools [--dry-run] [--json] [--quiet] [--no-color] use set PACKAGE FLAG [FLAG ...]
ptools [--dry-run] [--json] [--quiet] [--no-color] use unset PACKAGE FLAG [FLAG ...]
ptools [--dry-run] [--interactive] [--json] [--quiet] [--no-color] keyword show PACKAGE
ptools [--dry-run] [--json] [--quiet] [--no-color] keyword set PACKAGE KEYWORD [KEYWORD ...]
ptools [--dry-run] [--json] [--quiet] [--no-color] keyword set PACKAGE --testing
ptools [--dry-run] [--json] [--quiet] [--no-color] keyword unset PACKAGE KEYWORD [KEYWORD ...]
ptools [--interactive] [--json] [--quiet] [--no-color] package resolve PACKAGE
ptools [--interactive] [--json] [--quiet] [--no-color] package versions PACKAGE
```

```yaml
Package Inputs:
  Category Qualified: app-editors/neovim
  Exact: =app-editors/neovim-0.10.4
  Version Matched: ~app-editors/neovim-0.10.4
  Unqualified: neovim
USE Tokens:
  Enable: flag
  Disable: -flag
  Unset: remove both flag and -flag from the matching managed entry
Keyword Tokens:
  Explicit Testing: ~${ARCH}
  Mask All: -*
  Testing Expansion: --testing resolves to ~${ARCH}
Configuration Format: Portage whitespace-delimited atom followed by tokens, with comments and blank lines preserved
Duplicate Atom Default: fail
Duplicate Atom Opt-In: --merge-duplicates
```

```json
{
  "operation": "use.set",
  "atom": "app-editors/neovim",
  "target": "/resolved/config/root/etc/portage/package.use/ptools",
  "added": ["lua"],
  "removed": [],
  "changed": true,
  "dry_run": false
}
```

```json
{
  "operation": "package.resolve",
  "atom": "app-editors/neovim",
  "cp": "app-editors/neovim",
  "cpv": null,
  "installed_versions": [],
  "repository_versions": ["app-editors/neovim-0.10.4"]
}
```

```yaml
Exit Codes:
  Success: 0
  Usage: 2
  Not Found: 3
  Ambiguous: 4
  Permission: 5
  Invalid Configuration: 6
  Portage Error: 7
  Write Error: 8
Stream Contract:
  Results: stdout
  Errors: stderr
  JSON ANSI Escapes: prohibited
  Success Messages on stderr: prohibited
```

```yaml
Atomic Write:
  1: Read current target
  2: Parse managed entries
  3: Produce candidate content
  4: Write a temporary file in the target directory
  5: Flush the temporary file
  6: Apply original mode and ownership where applicable
  7: Replace the target atomically
Dry Run Output:
  - Resolved package atom
  - Target configuration file
  - Entries added
  - Entries removed
  - Final candidate line
  - No-write confirmation
```

```bash
ruff check .
ruff format --check .
mypy src/ptools
pytest
pytest --cov=ptools --cov-report=term-missing --cov-fail-under=85
pytest -m 'not integration'
pytest -m integration
python -m build
python -m twine check dist/*
```

# Grounding: Environment-Specific Details

```yaml
Repository Working Tree: /workspace/ptools
Git Branch: work
Git Remote: none configured
GitHub Organization: unknown; no git remote or repository identifier is present
GitHub Repository Path: unknown; no git remote or repository identifier is present
Legacy Source Files:
  - /workspace/ptools/ptk.py
  - /workspace/ptools/puse.py
  - /workspace/ptools/pkw.py
Modernization Specification: /workspace/ptools/SPEC.md
Generated Build Prompt: /workspace/ptools/build_PROMPT.md
Legacy ptk Version: 0.0.3
Legacy puse Version: 0.0.1
Legacy pkw Version: 0.0.3
Legacy Support Address: bugzilla@opelousas.org
Legacy Hard-Coded Python Paths:
  - /usr/lib/ptools
  - /usr/lib/portage/pym
Legacy Hard-Coded Effective Root: /
Legacy Hard-Coded Config Root: /etc/portage
Legacy Keyword Path: /etc/portage/package.keywords
Legacy USE Path: /etc/portage/package.use
Modern Default USE Target Candidate: /etc/portage/package.use/ptools
Modern Default Keyword Target Candidate: /etc/portage/package.accept_keywords/ptools
Development Container Python: 3.14.4
Development Container Portage Module: absent
Development Container /etc/portage: absent
Development Container CPU: 3 logical CPUs
Development Container RAM: 19252858880 bytes
Development Container Available Storage: 30426923008 bytes on /dev/vda at discovery
Azure Automation Account ID: not applicable; no Azure integration exists in the specification or source
Intune Group IDs: not applicable; no Intune integration exists in the specification or source
Entra App IDs: not applicable; no Entra integration exists in the specification or source
Service Principal Names: not applicable; no service principal integration exists
Domain Names: not applicable; no domain infrastructure exists in the specification or source
Ollama Models: not applicable; no local LLM inference exists
Custom Runtime Library Versions: unresolved until Portage is discovered on the designated Gentoo system
Official Portage Source: https://github.com/gentoo/portage
Official Portage API Documentation: https://dev.gentoo.org/~zmedico/portage/doc/api/
Gentoo package.accept_keywords Documentation: https://wiki.gentoo.org/wiki//etc/portage/package.accept_keywords
Gentoo package.use Documentation: https://wiki.gentoo.org/wiki//etc/portage/package.use
External Reference Reachability at Discovery: HTTP 403 from the development network proxy
```

```yaml
Required User Decisions Before Writes:
  Gentoo Integration System: unknown
  PORTAGE_CONFIGROOT: unknown
  package.use Layout: unknown
  package.accept_keywords Layout: unknown
  Dedicated ptools File Ownership: unknown
  Legacy puse Availability: unknown
  Legacy pkw Availability: unknown
  Privileged Write Policy: unknown
  Backup Policy: unknown; specification default is false
```
