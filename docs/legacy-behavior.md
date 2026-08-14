# Legacy Behavior and Modernization

## Legacy Behavior

The Python 2 originals (`ptk.py`, `puse.py`, `pkw.py`) are deleted from the tree
and live in git history only. What they did:

`puse --show`: Shows the USE flags for a given package (installed vs available in tree).
`puse --change`: Sets USE flags for a package. `--any` targets any version, `--exact` targets a specific version, `--not` unsets/negates flags.
`puse --remove`: Removes locally configured USE flags from the config.
`pkw --change`: Sets keyword for a package.
`pkw --remove`: Removes a keyword configuration.

DROPPED (previously DEFERRED): `pkw --fix-kw` - This cleaned up invalid keywords. Deferred during the modernization, then dropped permanently on 2026-08-14 by user decision: whole-directory cleanup is a job for modern tooling, not for these commands.

A fourth tool existed and is lost; no behavior is invented for it.

## Modernization Decisions

The authoritative record is `docs/decisions.md` plus the README's command
docs (`build_PROMPT.md`, which held this during the build, is deleted — see
git history). In summary:

- `puse` and `pkw` are the only commands, and they are **first-class CLIs**, not
  wrappers: each parses its own arguments and calls the service layer directly.
  There is no `ptools` command and no subprocess between them.
- The old mode switches (`--show` / `--change` / `--remove` / `--any` / `--not`)
  are gone. The shape is now `cmd [OPTIONS] PACKAGE [TOKEN ...]`:
  inspection is the bare-`PACKAGE` form, `--change --any` is just listing tokens,
  `--not` is the `-flag` token itself, and `--remove` is `--unset`.
  `--exact` survives with its old meaning.
- Writes target `<config-root>/package.use/ptools` and
  `<config-root>/package.accept_keywords/ptools` in the directory layout. The
  config root is discovered from portage, never assumed to be `/`.
- No automatic backups (`.bak`), matching the original tools' simpler style.
  Safety comes from preserving unrelated content and replacing the target
  atomically.
- **No privilege escalation.** The originals shelled out to `sudo`; ptools does
  not. Run it as root when writing; an unwritable target exits 5.
- Legacy `package.keywords` is never migrated or written. `pkw` only reports
  that it exists.
