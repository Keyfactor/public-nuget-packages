"""sync_nuget.py — CLI for syncing NuGet packages between Azure DevOps and GitHub Packages.

Commands:
    sync      Download and upload all (or one) package(s) defined in a packages YAML file.
    register  Add a new package or version(s) to a packages YAML file.
    upgrade   Query Azure DevOps for new versions of all listed packages and register them.
    sort      Sort and deduplicate versions in a packages YAML file.
    download  Download a single package version directly from Azure DevOps.

Package sources:
    Most packages are sourced from the Azure DevOps feed (the default).  Packages that are
    published directly to GitHub Packages by another repository should set ``source: github``
    in packages.yml — they are downloaded from the Keyfactor GitHub Packages registry
    (using GH_NUGET_TOKEN) rather than from Azure DevOps.  The ``upgrade`` command skips
    packages with a non-azdo source since it queries the Azure DevOps feed.

Environment variables:
    AZ_DEVOPS_PAT   Azure DevOps Personal Access Token with package read permissions.
    GH_NUGET_TOKEN  GitHub Personal Access Token with write:packages permission.
                    Falls back to GITHUB_TOKEN if not set.
    GITHUB_TOKEN    GitHub token (used as fallback for GH_NUGET_TOKEN).
"""

import os
import subprocess
import sys
from pathlib import Path

import click
import requests
import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_AZDO_FEED_BASE = "https://pkgs.dev.azure.com/Keyfactor/_packaging/KeyfactorPackages/nuget/v3/flat2"
_GITHUB_NUGET_BASE = "https://nuget.pkg.github.com/keyfactor"
_GITHUB_NUGET_PUSH_URL = "https://nuget.pkg.github.com/keyfactor/index.json"
_TMP_DIR = "nupkgs"

# Package source identifiers used in packages.yml
_SOURCE_AZDO = "azdo"     # default: download from Azure DevOps feed
_SOURCE_GITHUB = "github"  # download from GitHub Packages (keyfactor org)


# ---------------------------------------------------------------------------
# NuGetSyncer
# ---------------------------------------------------------------------------

class NuGetSyncer:
    """Orchestrates downloading packages from Azure DevOps and publishing them to GitHub Packages.

    Attributes:
        github_token:     GitHub PAT used to authenticate pushes and version queries.
        az_devops_pat:    Azure DevOps PAT used to authenticate downloads.
        tmp_dir:          Local directory used to cache downloaded .nupkg files.
        allowed_packages: List of package dicts (``{name, versions}``) to sync,
                          optionally filtered to a single package.
    """

    def __init__(self, packages_file: str, package_filter: str | None = None) -> None:
        """Initialise the syncer and load the package list.

        Args:
            packages_file:  Path to the YAML file that declares packages and versions.
            package_filter: If provided, only the package whose name matches this value
                            (case-insensitive) will be synced.  Raises
                            :class:`click.BadParameter` if no match is found.
        """
        self.github_token: str | None = os.getenv("GH_NUGET_TOKEN") or os.getenv("GITHUB_TOKEN")
        self.az_devops_pat: str | None = os.getenv("AZ_DEVOPS_PAT")
        self.tmp_dir: Path = Path(_TMP_DIR)
        self.package_filter = package_filter
        self.allowed_packages: list[dict] = self._load_packages(packages_file)
        self._github_versions_cache: dict[str, set[str]] = {}
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Package list loading
    # ------------------------------------------------------------------

    def _load_packages(self, packages_file: str) -> list[dict]:
        """Load and optionally filter the package list from a YAML file.

        The YAML file is expected to have the structure::

            packages:
              - name: Some.Package
                versions:
                  - 1.0.0
                  - 2.0.0

        Args:
            packages_file: Path to the packages YAML file.

        Returns:
            A list of package dicts.  When *package_filter* is set, the list
            contains at most one entry.

        Raises:
            click.BadParameter: If *package_filter* is set but no matching
                package is found in the file.
        """
        try:
            with open(packages_file) as f:
                packages: list[dict] = yaml.safe_load(f).get("packages", []) or []
        except Exception as e:
            click.echo(f"Error loading {packages_file}: {e}", err=True)
            return []
        if self.package_filter:
            packages = [p for p in packages if p.get("name", "").lower() == self.package_filter.lower()]
            if not packages:
                raise click.BadParameter(f"Package '{self.package_filter}' not found in {packages_file}")
        return packages

    # ------------------------------------------------------------------
    # GitHub Packages queries
    # ------------------------------------------------------------------

    def get_github_published_versions(self, name: str) -> set[str]:
        """Return the set of versions already published to the GitHub Package Registry.

        Results are cached per package name for the lifetime of this instance so
        that repeated calls within a single sync run do not make redundant HTTP
        requests.

        Args:
            name: The NuGet package ID (e.g. ``Keyfactor.PKI``).

        Returns:
            A set of version strings currently published on GitHub Packages.
            Returns an empty set if the package has never been published or if
            the query fails.
        """
        if name in self._github_versions_cache:
            return self._github_versions_cache[name]
        url = f"{_GITHUB_NUGET_BASE}/download/{name.lower()}/index.json"
        try:
            resp = requests.get(url, auth=("token", self.github_token), timeout=15)
            versions = set(resp.json().get("versions", [])) if resp.ok else set()
        except Exception as e:
            click.echo(f"Warning: could not fetch published versions for {name}: {e}", err=True)
            versions = set()
        self._github_versions_cache[name] = versions
        return versions

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download_package(self, name: str, version: str) -> Path:
        """Download a single package version from the Azure DevOps NuGet feed.

        Uses the NuGet v3 flat container API
        (``/flat2/{id}/{version}/{id}.{version}.nupkg``) with Basic
        authentication so that credential handling is handled entirely by
        ``requests`` rather than the Mono nuget CLI, which has known issues
        resolving ``ClearTextPassword`` credentials on Linux.

        The file is cached in :attr:`tmp_dir`; if it already exists on disk the
        download is skipped.

        Args:
            name:    The NuGet package ID (e.g. ``Keyfactor.PKI``).
            version: The exact version string to download (e.g. ``8.2.2``).

        Returns:
            The local :class:`~pathlib.Path` of the downloaded ``.nupkg`` file.

        Raises:
            requests.HTTPError: If the Azure DevOps feed returns a non-2xx
                response (e.g. 401 Unauthorised or 404 Not Found).
        """
        filename = f"{name}.{version}.nupkg".replace("/", "_")
        filepath = self.tmp_dir / filename
        if filepath.exists():
            click.echo(f"Already downloaded: {filename}")
            return filepath
        click.echo(f"Downloading {name} {version}...")
        url = f"{_AZDO_FEED_BASE}/{name.lower()}/{version}/{name.lower()}.{version}.nupkg"
        resp = requests.get(url, auth=("any", self.az_devops_pat), timeout=120, stream=True)
        resp.raise_for_status()
        with filepath.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        click.echo(f"Downloaded: {filename}")
        return filepath

    def download_package_from_github(self, name: str, version: str) -> Path:
        """Download a single package version from the Keyfactor GitHub Packages registry.

        Used for packages whose canonical source is a GitHub repository rather than
        the Azure DevOps feed (i.e. entries with ``source: github`` in packages.yml).
        Authenticates with :attr:`github_token`.

        The file is cached in :attr:`tmp_dir`; if it already exists on disk the
        download is skipped.

        Args:
            name:    The NuGet package ID (e.g. ``Keyfactor.Extensions.Pam.Utilities``).
            version: The exact version string to download.

        Returns:
            The local :class:`~pathlib.Path` of the downloaded ``.nupkg`` file.

        Raises:
            requests.HTTPError: If the GitHub Packages registry returns a non-2xx response.
        """
        filename = f"{name}.{version}.nupkg".replace("/", "_")
        filepath = self.tmp_dir / filename
        if filepath.exists():
            click.echo(f"Already downloaded: {filename}")
            return filepath
        click.echo(f"Downloading {name} {version} from GitHub Packages...")
        url = f"{_GITHUB_NUGET_BASE}/download/{name.lower()}/{version}/{name.lower()}.{version}.nupkg"
        resp = requests.get(url, auth=("token", self.github_token), timeout=120, stream=True)
        resp.raise_for_status()
        with filepath.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        click.echo(f"Downloaded: {filename}")
        return filepath

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload_to_github(self, package_file: Path | str) -> bool:
        """Push a ``.nupkg`` file to the GitHub Package Registry using ``dotnet nuget push``.

        Args:
            package_file: Path to the ``.nupkg`` file.

        Returns:
            ``True`` if the push succeeded, ``False`` otherwise.
        """
        if not self.github_token:
            click.echo("GITHUB_TOKEN not set — skipping upload.", err=True)
            return False

        name = Path(package_file).name
        click.echo(f"Uploading {name} to GitHub Packages...")
        try:
            subprocess.run(
                [
                    "dotnet", "nuget", "push", str(package_file),
                    "--source", _GITHUB_NUGET_PUSH_URL,
                    "--api-key", self.github_token,
                    "--skip-duplicate",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            click.echo(f"Uploaded: {name}")
            return True
        except subprocess.CalledProcessError as e:
            click.echo(f"Failed to upload {name}: {e}", err=True)
            if e.stdout:
                click.echo(e.stdout, err=True)
            if e.stderr:
                click.echo(e.stderr, err=True)
            return False

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    def sync_packages(self) -> None:
        """Sync all packages in :attr:`allowed_packages` to GitHub Packages.

        For each package and version declared in the packages file, the method:

        1. Queries the GitHub Package Registry to check whether the version is
           already published (skipping it if so).
        2. Downloads the ``.nupkg`` from Azure DevOps via
           :meth:`download_package`.
        3. Pushes it to GitHub Packages via :meth:`upload_to_github`.

        Prints a summary of uploaded, skipped, and failed versions on
        completion.
        """
        if not self.allowed_packages:
            click.echo("No packages specified. Nothing to sync.")
            return

        click.echo(f"Syncing: {[p.get('name') for p in self.allowed_packages]}")
        skipped = successful = 0
        failures: list[str] = []

        for pkg in self.allowed_packages:
            name: str = pkg.get("name", "")
            versions: list[str] = pkg.get("versions") or []
            source: str = pkg.get("source", _SOURCE_AZDO)
            published = self.get_github_published_versions(name)
            for version in versions:
                if version in published:
                    click.echo(f"Already published: {name} {version} — skipping")
                    skipped += 1
                    continue
                try:
                    if source == _SOURCE_GITHUB:
                        package_file = self.download_package_from_github(name, version)
                    else:
                        package_file = self.download_package(name, version)
                    if self.upload_to_github(package_file):
                        successful += 1
                    else:
                        failures.append(f"{name} {version}")
                except Exception as e:
                    click.echo(f"Failed to sync {name} {version}: {e}", err=True)
                    failures.append(f"{name} {version}")

        click.echo(f"\nSync summary:\n  Uploaded: {successful}\n  Skipped:  {skipped}\n  Failed:   {len(failures)}")
        if failures:
            click.echo("\nFailed versions:")
            for entry in failures:
                click.echo(f"  - {entry}")
            sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _version_key(v: str) -> tuple[int, ...]:
    """Return a tuple of ints for semver-aware sorting.

    Non-numeric segments (e.g. prerelease labels) fall back to zero so they
    sort below their numeric counterparts.

    Args:
        v: A version string such as ``8.2.3`` or ``1.0.0``.

    Returns:
        A tuple of integers suitable for use as a sort key.
    """
    return tuple(int(x) if x.isdigit() else 0 for x in v.split("."))


def _get_azdo_versions(name: str, az_pat: str) -> set[str]:
    """Return all versions available for *name* in the Azure DevOps feed.

    Args:
        name:   The NuGet package ID.
        az_pat: Azure DevOps PAT used for authentication.

    Returns:
        A set of version strings available in the feed, or an empty set if the
        package is not found or the request fails.
    """
    resp = requests.get(
        f"{_AZDO_FEED_BASE}/{name.lower()}/index.json",
        auth=("any", az_pat),
        timeout=15,
    )
    return set(resp.json().get("versions", [])) if resp.ok else set()


def _validate_versions(name: str, versions: tuple[str, ...], az_pat: str) -> None:
    """Verify that each requested version exists in the Azure DevOps feed.

    Args:
        name:     The NuGet package ID.
        versions: Tuple of version strings to validate.
        az_pat:   Azure DevOps PAT used for authentication.

    Raises:
        click.ClickException: If the package is not found in the feed, or if
            any of the requested versions are not available.
    """
    available = _get_azdo_versions(name, az_pat)
    if not available:
        raise click.ClickException(f"Package '{name}' not found in Azure DevOps feed.")
    if missing := [v for v in versions if v not in available]:
        raise click.ClickException(
            f"Version(s) not found in Azure DevOps feed: {', '.join(missing)}\n"
            f"Available: {', '.join(sorted(available, key=_version_key))}"
        )


def _write_versions_to_file(
    packages_file: str,
    name: str,
    versions: tuple[str, ...],
) -> tuple[list[str], list[str]]:
    """Insert package versions into *packages_file* using line-based editing.

    Edits the file in-place without parsing and re-serialising the full YAML
    document, which preserves all existing comments and formatting.

    - If the package already exists: new versions are inserted immediately
      after the last existing version entry.
    - If the package does not exist: a new package block is appended at the
      end of the file.

    Args:
        packages_file: Path to the packages YAML file.
        name:          The NuGet package ID.
        versions:      Tuple of version strings to add.

    Returns:
        A ``(added, skipped)`` tuple where *added* is the list of versions
        that were written and *skipped* is the list that were already present.

    Raises:
        click.ClickException: If the package entry or its versions block cannot
            be located in the file (should not occur under normal circumstances).
    """
    path = Path(packages_file)
    content = path.read_text()
    lines = content.splitlines(keepends=True)
    data = yaml.safe_load(content)

    packages: list[dict] = data.get("packages") or []
    existing = next((p for p in packages if p.get("name", "").lower() == name.lower()), None)

    already_present: set[str] = {str(v) for v in existing.get("versions", [])} if existing else set()
    to_add = sorted([v for v in versions if v not in already_present], key=_version_key)
    skipped = [v for v in versions if v in already_present]

    if not to_add:
        return [], skipped

    if existing:
        pkg_line = next(
            (i for i, l in enumerate(lines) if l.strip().lstrip("- ").startswith(f"name: {name}")),
            None,
        )
        if pkg_line is None:
            raise click.ClickException(f"Could not locate '{name}' in {packages_file}.")

        last_ver_line: int | None = None
        ver_indent: int | None = None
        in_versions = False
        for i in range(pkg_line + 1, len(lines)):
            stripped = lines[i].strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped == "versions:":
                in_versions = True
                continue
            if in_versions:
                if stripped.startswith("- ") and not stripped.startswith("- name:"):
                    last_ver_line = i
                    ver_indent = len(lines[i]) - len(lines[i].lstrip())
                else:
                    break
            elif stripped.startswith("- name:"):
                break

        if last_ver_line is None:
            raise click.ClickException(f"Could not find versions block for '{name}'.")

        for v in reversed(to_add):
            lines.insert(last_ver_line + 1, " " * ver_indent + f"- {v}\n")
    else:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(f"  - name: {name}\n")
        lines.append("    versions:\n")
        for v in to_add:
            lines.append(f"      - {v}\n")

    path.write_text("".join(lines))
    return to_add, skipped


def _sort_versions_in_file(packages_file: str) -> dict[str, int]:
    """Sort the versions for every package in *packages_file* in ascending semver order.

    Edits the file in-place using line-based manipulation so that comments and
    overall formatting are preserved.  Inline comments on version lines (e.g.
    ``- 1.0.0.1 # unusual release``) travel with their version entry.

    Args:
        packages_file: Path to the packages YAML file.

    Returns:
        A mapping of ``{package_name: version_count}`` for each package whose
        versions were reordered.  Packages that were already sorted are omitted.
    """
    path = Path(packages_file)
    lines = path.read_text().splitlines(keepends=True)

    changed: dict[str, int] = {}
    current_pkg: str | None = None
    in_versions: bool = False
    ver_indices: list[int] = []

    def _ver_str(idx: int) -> str:
        raw = lines[idx].strip()
        return raw[2:].split("#")[0].strip() if raw.startswith("- ") else raw

    def _flush() -> None:
        nonlocal ver_indices, in_versions
        if ver_indices and current_pkg is not None:
            unique: dict[str, str] = {}
            for idx in ver_indices:
                v = _ver_str(idx)
                if v not in unique:
                    unique[v] = lines[idx]

            sorted_lines = [unique[v] for v in sorted(unique, key=_version_key)]
            original_lines = [lines[i] for i in ver_indices]

            for pos, idx in enumerate(ver_indices):
                lines[idx] = sorted_lines[pos] if pos < len(sorted_lines) else ""

            if [lines[i] for i in ver_indices] != original_lines:
                changed[current_pkg] = len(sorted_lines)
        ver_indices.clear()
        in_versions = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("# "):
            continue
        if stripped.startswith("- name:") or (not stripped.startswith("-") and stripped.startswith("name:")):
            _flush()
            current_pkg = stripped.split("name:", 1)[1].strip()
        elif stripped == "versions:" and current_pkg is not None:
            in_versions = True
        elif in_versions:
            if stripped.startswith("- ") and not stripped.startswith("- name:"):
                ver_indices.append(i)
            elif stripped and not stripped.startswith("#"):
                _flush()

    _flush()

    path.write_text("".join(lines))
    return changed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.group()
def cli() -> None:
    """Manage NuGet package sync between Azure DevOps and GitHub Packages."""


@cli.command()
@click.argument("packages_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--package", default=None, help="Sync only this package name (must exist in the packages file).")
def sync(packages_file: str, package: str | None) -> None:
    """Sync packages from Azure DevOps to GitHub Packages.

    Reads PACKAGES_FILE, queries GitHub Packages to skip already-published
    versions, then downloads and pushes any missing versions.
    """
    NuGetSyncer(packages_file, package_filter=package).sync_packages()


@cli.command()
@click.argument("packages_file", type=click.Path(dir_okay=False))
@click.argument("name")
@click.argument("versions", nargs=-1, required=True)
@click.option("--skip-validate", is_flag=True, default=False,
              help="Skip Azure DevOps feed validation.")
def register(
    packages_file: str,
    name: str,
    versions: tuple[str, ...],
    skip_validate: bool,
) -> None:
    """Add NAME with one or more VERSIONS to PACKAGES_FILE.

    Validates that each version exists in the Azure DevOps feed before writing.
    Requires AZ_DEVOPS_PAT env var unless --skip-validate is set.
    """
    if not skip_validate:
        az_pat = os.getenv("AZ_DEVOPS_PAT")
        if not az_pat:
            raise click.ClickException(
                "AZ_DEVOPS_PAT env var is required for validation. Use --skip-validate to bypass."
            )
        click.echo(f"Validating {name} against Azure DevOps feed...")
        _validate_versions(name, versions, az_pat)

    added, skipped = _write_versions_to_file(packages_file, name, versions)

    if added:
        click.echo(f"Registered {name}: {', '.join(added)}")
    if skipped:
        click.echo(f"Already in {packages_file}, skipped: {', '.join(skipped)}")
    if not added and not skipped:
        click.echo("Nothing to register.")


@cli.command()
@click.argument("packages_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--package", default=None,
              help="Check only this package name (must exist in the packages file).")
@click.option("--dry-run", is_flag=True, default=False,
              help="Print new versions that would be registered without writing to the file.")
@click.option("--include-prerelease", is_flag=True, default=False,
              help="Include prerelease versions (excluded by default).")
def upgrade(packages_file: str, package: str | None, dry_run: bool, include_prerelease: bool) -> None:
    """Check Azure DevOps for new versions of packages listed in PACKAGES_FILE and register them.

    Stable versions only by default; use --include-prerelease to also pick up
    prerelease versions.  Requires AZ_DEVOPS_PAT env var.

    After running upgrade, use the sync command to push the new versions to the
    GitHub Package Registry.
    """
    az_pat = os.getenv("AZ_DEVOPS_PAT")
    if not az_pat:
        raise click.ClickException("AZ_DEVOPS_PAT env var is required.")

    with open(packages_file) as f:
        data = yaml.safe_load(f)
    packages: list[dict] = data.get("packages") or []

    if package:
        packages = [p for p in packages if p.get("name", "").lower() == package.lower()]
        if not packages:
            raise click.BadParameter(f"Package '{package}' not found in {packages_file}.")

    total_added = 0

    for pkg in packages:
        name: str = pkg.get("name", "")
        source: str = pkg.get("source", _SOURCE_AZDO)
        current: set[str] = {str(v) for v in pkg.get("versions") or []}

        if source != _SOURCE_AZDO:
            click.echo(f"Skipping {name} (source: {source}, not Azure DevOps).")
            continue

        click.echo(f"Checking {name}...")
        available = _get_azdo_versions(name, az_pat)
        if not available:
            click.echo("  Not found in Azure DevOps feed — skipping.")
            continue

        candidates = available if include_prerelease else {v for v in available if "PRERELEASE" not in v.upper()}
        max_current = max(current, key=_version_key) if current else None
        new_versions = sorted(
            (v for v in candidates - current if max_current is None or _version_key(v) > _version_key(max_current)),
            key=_version_key,
        )
        if not new_versions:
            click.echo("  Up to date.")
            continue

        click.echo(f"  New versions: {', '.join(new_versions)}")
        if not dry_run:
            _write_versions_to_file(packages_file, name, tuple(new_versions))
            total_added += len(new_versions)

    if dry_run:
        click.echo("\n(Dry run — no changes written.)")
    else:
        click.echo(f"\nUpgrade complete. {total_added} new version(s) registered.")
        if total_added:
            click.echo("Run 'sync' to push them to the GitHub Package Registry.")


@cli.command(name="sort")
@click.argument("packages_file", type=click.Path(exists=True, dir_okay=False))
def sort_cmd(packages_file: str) -> None:
    """Sort versions for all packages in PACKAGES_FILE in ascending semver order."""
    changed = _sort_versions_in_file(packages_file)
    if changed:
        for name, count in changed.items():
            click.echo(f"Sorted {count} version(s) for {name}")
    else:
        click.echo("All versions already in order.")


@cli.command()
@click.argument("name")
@click.argument("version")
@click.option("--output-dir", default=_TMP_DIR, show_default=True,
              help="Directory to save the downloaded .nupkg file.")
def download(name: str, version: str, output_dir: str) -> None:
    """Download a single package version from Azure DevOps.

    Saves the .nupkg file to OUTPUT_DIR (default: nupkgs/).
    Requires AZ_DEVOPS_PAT env var.
    """
    az_pat = os.getenv("AZ_DEVOPS_PAT")
    if not az_pat:
        raise click.ClickException("AZ_DEVOPS_PAT env var is required.")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    filepath = out / f"{name}.{version}.nupkg"
    url = f"{_AZDO_FEED_BASE}/{name.lower()}/{version}/{name.lower()}.{version}.nupkg"

    click.echo(f"Downloading {name} {version}...")
    resp = requests.get(url, auth=("any", az_pat), timeout=120, stream=True)
    if resp.status_code == 404:
        raise click.ClickException(f"{name} {version} not found in Azure DevOps feed.")
    resp.raise_for_status()

    with filepath.open("wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    click.echo(f"Saved to {filepath}")


if __name__ == "__main__":
    cli()
