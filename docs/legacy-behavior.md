# Legacy Behavior and Modernization

## Legacy Behavior

`puse --show`: Shows the USE flags for a given package (installed vs available in tree).
`puse --change`: Sets USE flags for a package. `--any` targets any version, `--exact` targets a specific version, `--not` unsets/negates flags.
`puse --remove`: Removes locally configured USE flags from the config.
`pkw --change`: Sets keyword for a package.
`pkw --remove`: Removes a keyword configuration.

DEFERRED: `pkw --fix-kw` - This cleans up invalid keywords, but is deferred in this modernization step.

## Modernization Decisions

- Commands `puse` and `pkw` will be retained as first-class CLI utilities, mapping to `ptools use` and `ptools keyword` respectively.
- Configuration writes will target `/etc/portage/package.use/ptools` and `/etc/portage/package.accept_keywords/ptools` (in a directory layout).
- Privileged writes will require `sudo` if the script is not run as root.
- No automatic backups (`.bak`) will be enforced, adhering to the original tool's simpler style.
