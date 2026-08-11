# Environment Discovery

> **STATUS: NOT YET DISCOVERED (Milestone D is open).**
>
> The values below are placeholders from the mock backend. They are **not**
> facts about any real system and must not be relied on. Replace this file with
> the output of `scripts/discover_environment.py` run on gumbo (the CI job
> uploads it as the `environment-gentoo-dev` artifact and prints it in the
> "Discover real environment" step) or in a local stage3 chroot.

```yaml
PYTHON_VERSION: unknown (>=3.11 required by pyproject)
PORTAGE_VERSION: unknown (mock backend only)
PORTAGE_MODULE: unknown
ROOT: unknown
EPREFIX: unknown
PORTAGE_CONFIGROOT: unknown (discovered at runtime; never assumed to be /)
ARCH: unknown (never assume amd64)
PACKAGE_USE_LAYOUT: unknown (ptools requires the directory layout)
PACKAGE_KEYWORD_LAYOUT: unknown (ptools requires the directory layout)
EXISTING_TOOL_DECISIONS: unknown
```
