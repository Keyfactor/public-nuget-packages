"""sync_nuget.py — CLI for syncing NuGet packages between Azure DevOps and GitHub Packages.

Commands:
    sync      Download and upload all (or one) package(s) defined in a packages YAML file.
    register  Add a new package or version(s) to a packages YAML file.
    download  Download a single package version directly from Azure DevOps.

Environment variables:
    AZ_DEVOPS_PAT   Azure DevOps Personal Access Token with package read permissions.
    GH_NUGET_TOKEN  GitHub Personal Access Token with write:packages permission.
                    Falls back to GITHUB_TOKEN if not set.
    GITHUB_TOKEN    GitHub token (used as fallback for GH_NUGET_TOKEN).
"""

from __future__ import annotations

import os
import subprocess
from typing import Optional

import click
import requests
import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_AZDO_FEED_INDEX = "https://pkgs.dev.azure.com/Keyfactor/_packaging/KeyfactorPackages/nuget/v3/index.json"
_AZDO_FEED_BASE = "https://pkgs.dev.azure.com/Keyfactor/_packaging/KeyfactorPackages/nuget/v3/flat2"
_GITHUB_NUGET_BASE = "https://nuget.pkg.github.com/keyfactor"
_GITHUB_NUGET_PUSH_URL = "https://nuget.pkg.github.com/keyfactor/index.json"
_TMP_DIR = "nupkgs"


# ---------------------------------------------------------------------------
# NuGetSyncer
# ---------------------------------------------------------------------------

class NuGetSyncer:
    """Orchestrates downloading packages from Azure DevOps and publishing them to GitHub Packages.

    Attributes:
        NUGET_FEED_URL:   NuGet v3 service index URL for the Azure DevOps feed.
        GITHUB_NUGET_URL: NuGet push endpoint for the GitHub Package Registry.
        GITHUB_TOKEN:     GitHub PAT used to authenticate pushes and version queries.
        AZ_DEVOPS_PAT:    Azure DevOps PAT used to authenticate downloads.
        TMP_DIR:          Local directory used to cache downloaded .nupkg files.
        allowed_packages: List of package dicts (``{name, versions}``) to sync,
                          optionally filtered to a single package.
    """

    def __init__(self, packages_file: str, package_filter: Optional[str] = None) -> None:
        """Initialise the syncer and load the package list.

        Args:
            packages_file:  Path to the YAML file that declares packages and versions.
            package_filter: If provided, only the package whose name matches this value
                            (case-insensitive) will be synced.  Raises
                            :class:`click.BadParameter` if no match is found.
        """
        self.NUGET_FEED_URL: str = _AZDO_FEED_INDEX
        self.GITHUB_NUGET_URL: str = _GITHUB_NUGET_PUSH_URL
        self.GITHUB_TOKEN: Optional[str] = os.getenv("GH_NUGET_TOKEN", os.getenv("GITHUB_TOKEN"))
        self.AZ_DEVOPS_PAT: Optional[str] = os.getenv("AZ_DEVOPS_PAT")
        self.TMP_DIR: str = _TMP_DIR
        self.package_filter: Optional[str] = package_filter
        self.allowed_packages: list[dict] = self.load_allowed_packages(packages_file)
        self._github_versions_cache: dict[str, set[str]] = {}
        os.makedirs(self.TMP_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # Package list loading
    # ------------------------------------------------------------------

    def load_allowed_packages(self, packages_file: str) -> list[dict]:
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
            with open(packages_file, 'r') as f:
                packages: list[dict] = yaml.safe_load(f).get('packages', []) or []
        except Exception as e:
            click.echo(f"Error loading {packages_file}: {e}", err=True)
            return []
        if self.package_filter:
            packages = [p for p in packages if p.get('name', '').lower() == self.package_filter.lower()]
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
            resp = requests.get(url, auth=("token", self.GITHUB_TOKEN), timeout=15)
            versions: set[str] = set(resp.json().get("versions", [])) if resp.status_code == 200 else set()
        except Exception as e:
            print(f"Warning: could not fetch published versions for {name}: {e}")
            versions = set()
        self._github_versions_cache[name] = versions
        return versions

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download_package(self, name: str, version: str) -> str:
        """Download a single package version from the Azure DevOps NuGet feed.

        Uses the NuGet v3 flat container API
        (``/flat2/{id}/{version}/{id}.{version}.nupkg``) with Basic
        authentication so that credential handling is handled entirely by
        ``requests`` rather than the Mono nuget CLI, which has known issues
        resolving ``ClearTextPassword`` credentials on Linux.

        The file is cached in :attr:`TMP_DIR`; if it already exists on disk the
        download is skipped.

        Args:
            name:    The NuGet package ID (e.g. ``Keyfactor.PKI``).
            version: The exact version string to download (e.g. ``8.2.2``).

        Returns:
            The local file path of the downloaded ``.nupkg`` file.

        Raises:
            requests.HTTPError: If the Azure DevOps feed returns a non-2xx
                response (e.g. 401 Unauthorised or 404 Not Found).
        """
        filename = f"{name}.{version}.nupkg".replace("/", "_")
        filepath = os.path.join(self.TMP_DIR, filename)
        if os.path.exists(filepath):
            print(f"Already downloaded: {filename}")
            return filepath
        print(f"Downloading {name} {version} from NuGet v3 feed...")
        url = f"{_AZDO_FEED_BASE}/{name.lower()}/{version}/{name.lower()}.{version}.nupkg"
        resp = requests.get(url, auth=("any", self.AZ_DEVOPS_PAT), timeout=120, stream=True)
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Downloaded: {filename}")
        return filepath

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload_to_github(self, package_file: str) -> bool:
        """Push a ``.nupkg`` file to the GitHub Package Registry using ``dotnet nuget push``.

        Args:
            package_file: Absolute or relative path to the ``.nupkg`` file.

        Returns:
            ``True`` if the push succeeded, ``False`` otherwise.
        """
        if not self.GITHUB_TOKEN:
            print("GITHUB_TOKEN environment variable not set. Skipping GitHub upload.")
            return False

        print(f"Uploading {os.path.basename(package_file)} to GitHub Packages...")
        try:
            cmd = [
                "dotnet", "nuget", "push", package_file,
                "--source", self.GITHUB_NUGET_URL,
                "--api-key", self.GITHUB_TOKEN,
                "--skip-duplicate",
            ]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"Successfully uploaded {os.path.basename(package_file)} to GitHub Packages")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to upload {os.path.basename(package_file)} to GitHub Packages: {e}")
            if e.stdout:
                print(f"stdout: {e.stdout}")
            if e.stderr:
                print(f"stderr: {e.stderr}")
            return False

    def upload_all_packages_to_github(self) -> None:
        """Upload every ``.nupkg`` file found in :attr:`TMP_DIR` to GitHub Packages.

        Iterates over all ``.nupkg`` files in the local cache directory and
        calls :meth:`upload_to_github` for each one.  Prints a summary of
        successes and failures on completion.
        """
        if not os.path.exists(self.TMP_DIR):
            print("No packages directory found. Nothing to upload.")
            return

        package_files = [f for f in os.listdir(self.TMP_DIR) if f.endswith('.nupkg')]
        if not package_files:
            print("No .nupkg files found in packages directory.")
            return

        print(f"Found {len(package_files)} packages to upload to GitHub Packages...")
        successful_uploads = 0
        failed_uploads = 0

        for package_file in package_files:
            full_path = os.path.join(self.TMP_DIR, package_file)
            if self.upload_to_github(full_path):
                successful_uploads += 1
            else:
                failed_uploads += 1

        print("\nUpload summary:")
        print(f"  Successful: {successful_uploads}")
        print(f"  Failed: {failed_uploads}")

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
        click.echo(f"Will sync the following packages: {[p.get('name', p) for p in self.allowed_packages]}")
        skipped = 0
        successful = 0
        failed = 0
        for pkg in self.allowed_packages:
            pkg_name: str = pkg.get('name', pkg)
            versions: list[str] = pkg.get('versions', [])
            published = self.get_github_published_versions(pkg_name)
            for version in versions:
                if version in published:
                    print(f"Already published: {pkg_name} {version} — skipping")
                    skipped += 1
                    continue
                try:
                    package_file = self.download_package(pkg_name, version)
                    if package_file and os.path.exists(package_file):
                        if self.upload_to_github(package_file):
                            successful += 1
                        else:
                            failed += 1
                except subprocess.CalledProcessError as e:
                    print(f"Failed to sync {pkg_name} {version}: exit code {e.returncode}")
                    if e.stdout:
                        print(e.stdout)
                    if e.stderr:
                        print(e.stderr)
                    failed += 1
                except Exception as e:
                    print(f"Failed to sync {pkg_name} {version}: {e}")
                    failed += 1

        print("\nSync summary:")
        print(f"  Uploaded:  {successful}")
        print(f"  Skipped:   {skipped}")
        print(f"  Failed:    {failed}")


# ---------------------------------------------------------------------------
# Helpers used by the register command
# ---------------------------------------------------------------------------

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
    resp = requests.get(
        f"{_AZDO_FEED_BASE}/{name.lower()}/index.json",
        auth=("any", az_pat),
        timeout=15,
    )
    if resp.status_code != 200:
        raise click.ClickException(f"Package '{name}' not found in Azure DevOps feed.")
    available: set[str] = set(resp.json().get("versions", []))
    missing = [v for v in versions if v not in available]
    if missing:
        raise click.ClickException(
            f"Version(s) not found in Azure DevOps feed: {', '.join(missing)}\n"
            f"Available: {', '.join(sorted(available))}"
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
    with open(packages_file, 'r') as f:
        lines = f.readlines()

    with open(packages_file, 'r') as f:
        data = yaml.safe_load(f)
    packages: list[dict] = data.get('packages') or []
    existing = next((p for p in packages if p.get('name', '').lower() == name.lower()), None)

    already_present: set[str] = {str(v) for v in existing.get('versions', [])} if existing else set()
    to_add = [v for v in versions if v not in already_present]
    skipped = [v for v in versions if v in already_present]

    if not to_add:
        return [], skipped

    if existing:
        pkg_line = next(
            (i for i, l in enumerate(lines) if l.strip().lstrip('- ').startswith(f'name: {name}')),
            None,
        )
        if pkg_line is None:
            raise click.ClickException(f"Could not locate '{name}' in {packages_file}.")

        last_ver_line: Optional[int] = None
        ver_indent: Optional[int] = None
        in_versions = False
        for i in range(pkg_line + 1, len(lines)):
            stripped = lines[i].strip()
            if not stripped or stripped.startswith('#'):
                continue
            if stripped == 'versions:':
                in_versions = True
                continue
            if in_versions:
                if stripped.startswith('- ') and not stripped.startswith('- name:'):
                    last_ver_line = i
                    ver_indent = len(lines[i]) - len(lines[i].lstrip())
                else:
                    break
            elif stripped.startswith('- name:'):
                break

        if last_ver_line is None:
            raise click.ClickException(f"Could not find versions block for '{name}'.")

        for v in reversed(to_add):
            lines.insert(last_ver_line + 1, ' ' * ver_indent + f'- {v}\n')
    else:
        if lines and not lines[-1].endswith('\n'):
            lines.append('\n')
        lines.append(f'  - name: {name}\n')
        lines.append(f'    versions:\n')
        for v in to_add:
            lines.append(f'      - {v}\n')

    with open(packages_file, 'w') as f:
        f.writelines(lines)

    return to_add, skipped


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.group()
def cli() -> None:
    """Manage NuGet package sync between Azure DevOps and GitHub Packages."""
    pass


@cli.command()
@click.argument("packages_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--package", default=None, help="Sync only this package name (must exist in the packages file).")
def sync(packages_file: str, package: Optional[str]) -> None:
    """Sync packages from Azure DevOps to GitHub Packages.

    Reads PACKAGES_FILE, queries GitHub Packages to skip already-published
    versions, then downloads and pushes any missing versions.
    """
    syncer = NuGetSyncer(packages_file, package_filter=package)
    syncer.sync_packages()


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

    os.makedirs(output_dir, exist_ok=True)
    filename = f"{name}.{version}.nupkg"
    filepath = os.path.join(output_dir, filename)
    url = f"{_AZDO_FEED_BASE}/{name.lower()}/{version}/{name.lower()}.{version}.nupkg"

    click.echo(f"Downloading {name} {version}...")
    resp = requests.get(url, auth=("any", az_pat), timeout=120, stream=True)
    if resp.status_code == 404:
        raise click.ClickException(f"{name} {version} not found in Azure DevOps feed.")
    resp.raise_for_status()

    with open(filepath, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    click.echo(f"Saved to {filepath}")


if __name__ == "__main__":
    cli()
