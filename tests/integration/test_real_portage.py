"""Integration tests against a real portage installation.

These run on the gumbo runner (and any Gentoo host); everywhere else they skip.
Run them with ``pytest -m integration``.
"""

import pytest

from ptools import pkw, puse
from ptools.config_store import ConfigStore
from ptools.domain import ResolvedPackage
from ptools.errors import AmbiguousPackageError, PackageNotFoundError
from ptools.portage_adapter import get_portage_backend
from ptools.services import MutationService, ReadOnlyService

pytestmark = pytest.mark.integration

portage = pytest.importorskip("portage", reason="needs a real portage installation")

#: Always present on a Gentoo host, in both the tree and the vdb.
ANCHOR = "sys-apps/portage"


@pytest.fixture(scope="module")
def backend():
    return get_portage_backend()


@pytest.fixture(scope="module")
def all_cp(backend):
    cps = sorted(set(backend.portdb.cp_all()))
    if not cps:
        pytest.skip("no ebuild repository available on this host")
    return cps


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    root = tmp_path / "portage"
    root.mkdir()
    monkeypatch.setenv("PTOOLS_CONFIG_ROOT", str(root))
    return root


def test_atom_import_and_supported_db_match(backend, all_cp):
    package = backend.resolve(ANCHOR)

    assert package.cp == ANCHOR
    assert package.repository_versions or package.installed_versions
    assert ANCHOR in all_cp


def test_category_qualified_atom(backend):
    package = backend.resolve(ANCHOR)

    # Regression: portage's Atom.cpv is the *cp* for an unversioned atom, so a
    # resolved cpv must always carry a version and be usable for metadata reads.
    assert package.cpv.startswith(f"{ANCHOR}-")
    assert package.cpv != package.cp
    assert backend.keywords(ANCHOR)
    assert backend.iuse(ANCHOR)


def test_exact_atom(backend):
    package = backend.resolve(ANCHOR)

    exact = backend.resolve(f"={package.cpv}")

    assert exact.cpv == package.cpv
    assert exact.cp == ANCHOR


def test_invalid_atom_is_not_found(backend):
    with pytest.raises(PackageNotFoundError):
        backend.resolve("app-nonexistent/definitely-not-a-package")

    with pytest.raises(PackageNotFoundError):
        backend.resolve("this is not an atom")


@pytest.fixture(scope="module")
def name_counts(all_cp):
    counts: dict[str, int] = {}
    for cp in all_cp:
        name = cp.split("/")[-1]
        counts[name] = counts.get(name, 0) + 1
    return counts


def test_ambiguous_unqualified_name(backend, name_counts):
    ambiguous = next((name for name, count in name_counts.items() if count > 1), None)
    if ambiguous is None:
        pytest.skip("no package name exists in two categories in this repository")

    with pytest.raises(AmbiguousPackageError):
        backend.resolve(ambiguous)


def test_unqualified_name_resolves_when_unique(backend, all_cp, name_counts):
    # "portage" itself is ambiguous (acct-group, acct-user, sys-apps), so pick a
    # name the repository really does carry in exactly one category.
    unique = next((cp for cp in all_cp if name_counts[cp.split("/")[-1]] == 1), None)
    if unique is None:
        pytest.skip("every package name is ambiguous in this repository")

    assert backend.resolve(unique.split("/")[-1]).cp == unique


def test_metadata_reads_fall_back_to_the_vdb(backend):
    """Regression: a package installed but no longer in the tree.

    Such a package (dropped from ::gentoo, or from an overlay that is gone)
    resolves its cpv out of the vdb, so every metadata read must query the vdb
    too -- asking portdb for a cpv it does not carry raises, which surfaced as a
    portage error (exit 7) on a plain ``puse PACKAGE`` show.

    Built deterministically from an always-installed anchor rather than by
    hunting for a real dropped package, so this never skips.
    """
    installed = backend.resolve(ANCHOR)
    assert installed.installed_versions

    # The shape resolve() produces when only the vdb matched.
    vdb_only = ResolvedPackage(
        atom=ANCHOR,
        cp=ANCHOR,
        cpv=installed.installed_versions[-1],
        installed_versions=installed.installed_versions,
        repository_versions=(),
    )

    assert backend._db_for(vdb_only) is backend.vardb
    assert backend._db_for(installed) is backend.portdb

    # The fallback db must actually satisfy both kinds of read.
    assert backend._aux(backend.vardb, vdb_only.cpv, "IUSE")
    settings = portage.config(clone=backend.settings)
    settings.setcpv(vdb_only.cpv, mydb=backend.vardb)
    assert settings.get("PORTAGE_USE", settings.get("USE", ""))


def test_use_state_reads(backend, sandbox):
    payload = ReadOnlyService(backend, ConfigStore(), sandbox).use_show(ANCHOR)

    assert payload["cp"] == ANCHOR
    assert payload["effective"]
    assert payload["managed"] == []


def test_keyword_state_reads(backend, sandbox):
    payload = ReadOnlyService(backend, ConfigStore(), sandbox).keyword_show(ANCHOR)

    assert payload["arch"]
    assert payload["keywords"]


def test_sandbox_write_preserves_the_rest_of_the_file(backend, sandbox):
    target = sandbox / "package.use" / "ptools"
    target.parent.mkdir(parents=True)
    preamble = "# hand written\n\ndev-lang/python sqlite\n"
    target.write_text(preamble)

    service = MutationService(backend, ConfigStore(), sandbox)
    result = service.apply_use("set", ANCHOR, ("build",))

    assert result["changed"] is True
    assert target.read_text() == preamble + f"{ANCHOR} build\n"


def test_cli_round_trip_in_a_sandbox(sandbox):
    target = sandbox / "package.use" / "ptools"

    assert puse.main([ANCHOR, "build"]) == 0
    assert target.read_text() == f"{ANCHOR} build\n"
    assert puse.main([ANCHOR, "build"]) == 0  # idempotent
    assert puse.main(["--unset", ANCHOR, "build"]) == 0
    assert target.read_text() == ""


def test_pkw_testing_uses_the_host_arch(backend, sandbox):
    arch = backend.get_setting("ARCH")
    target = sandbox / "package.accept_keywords" / "ptools"

    assert pkw.main(["--testing", ANCHOR]) == 0
    assert target.read_text() == f"{ANCHOR} ~{arch}\n"


def test_dry_run_never_writes(sandbox):
    assert puse.main(["--dry-run", ANCHOR, "build"]) == 0
    assert not (sandbox / "package.use" / "ptools").exists()
