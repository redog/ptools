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
