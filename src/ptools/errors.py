"""Error taxonomy.

Every failure carries the process exit code it maps to, so the CLIs never have
to re-derive the mapping. The authoritative table is in the README (machine-
checked against these classes by tests/unit/test_docs.py); rationale in
docs/decisions.md.
"""


class PtoolsError(Exception):
    """Base class for every expected ptools failure."""

    exit_code = 1
    kind = "error"


class UsageError(PtoolsError):
    exit_code = 2
    kind = "usage"


class PackageNotFoundError(PtoolsError):
    exit_code = 3
    kind = "not-found"


class AmbiguousPackageError(PtoolsError):
    """An unqualified name matched several packages.

    ``matches`` carries the candidate cps so an interactive caller can offer
    them as a menu; the message alone stays complete for scripts.
    """

    exit_code = 4
    kind = "ambiguous"

    def __init__(self, message: str, matches: tuple[str, ...] = ()):
        super().__init__(message)
        self.matches = matches


class AmbiguousTargetError(PtoolsError):
    """The atom has entries in more than one file; --file must pick one."""

    exit_code = 4
    kind = "ambiguous"


class PermissionDeniedError(PtoolsError):
    """The target is not writable; the caller must re-run as root."""

    exit_code = 5
    kind = "permission"


class InvalidConfigError(PtoolsError):
    exit_code = 6
    kind = "invalid-config"


class PortageIntegrationError(PtoolsError):
    exit_code = 7
    kind = "portage"


class WriteError(PtoolsError):
    exit_code = 8
    kind = "write"
