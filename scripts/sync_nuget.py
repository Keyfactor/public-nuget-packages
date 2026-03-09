import os
import shutil
import subprocess
import tempfile
import click
import requests
import yaml

class NuGetSyncer:
    def __init__(self, packages_file, package_filter=None):
        self.NUGET_FEED_URL = "https://pkgs.dev.azure.com/Keyfactor/_packaging/KeyfactorPackages/nuget/v3/index.json"
        self.GITHUB_NUGET_URL = "https://nuget.pkg.github.com/keyfactor/index.json"
        self.GITHUB_TOKEN = os.getenv("GH_NUGET_TOKEN", os.getenv("GITHUB_TOKEN"))
        self.AZ_DEVOPS_PAT = os.getenv("AZ_DEVOPS_PAT")
        self.TMP_DIR = "nupkgs"
        self.GITHUB_NUGET_BASE = "https://nuget.pkg.github.com/keyfactor"
        self.package_filter = package_filter
        self.allowed_packages = self.load_allowed_packages(packages_file)
        self._github_versions_cache = {}
        os.makedirs(self.TMP_DIR, exist_ok=True)

    def load_allowed_packages(self, packages_file):
        try:
            with open(packages_file, 'r') as f:
                packages = yaml.safe_load(f).get('packages', []) or []
        except Exception as e:
            click.echo(f"Error loading {packages_file}: {e}", err=True)
            return []
        if self.package_filter:
            packages = [p for p in packages if p.get('name', '').lower() == self.package_filter.lower()]
            if not packages:
                raise click.BadParameter(f"Package '{self.package_filter}' not found in {packages_file}")
        return packages

    def get_github_published_versions(self, name):
        """Fetch the list of versions already published to GitHub Packages for a given package."""
        if name in self._github_versions_cache:
            return self._github_versions_cache[name]
        url = f"{self.GITHUB_NUGET_BASE}/download/{name.lower()}/index.json"
        try:
            resp = requests.get(url, auth=("token", self.GITHUB_TOKEN), timeout=15)
            if resp.status_code == 200:
                versions = set(resp.json().get("versions", []))
            else:
                versions = set()
        except Exception as e:
            print(f"Warning: could not fetch published versions for {name}: {e}")
            versions = set()
        self._github_versions_cache[name] = versions
        return versions

    def download_package(self, name, version):
        filename = f"{name}.{version}.nupkg".replace("/", "_")
        filepath = os.path.join(self.TMP_DIR, filename)
        if os.path.exists(filepath):
            print(f"Already downloaded: {filename}")
            return filepath
        print(f"Downloading {name} {version} from NuGet v3 feed...")
        tmp_config_path = None
        if self.AZ_DEVOPS_PAT:
            nuget_config = f"""<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <add key="KeyfactorPackages" value="{self.NUGET_FEED_URL}" />
  </packageSources>
  <packageSourceCredentials>
    <KeyfactorPackages>
      <add key="Username" value="any" />
      <add key="ClearTextPassword" value="{self.AZ_DEVOPS_PAT}" />
    </KeyfactorPackages>
  </packageSourceCredentials>
</configuration>"""
            with tempfile.NamedTemporaryFile(mode='w', suffix='.config', delete=False) as tmp:
                tmp.write(nuget_config)
                tmp_config_path = tmp.name
            config_path = tmp_config_path
        else:
            config_path = os.path.expanduser("~/.nuget/NuGet/NuGet.Config")
        try:
            cmd = [
                "nuget", "install", name,
                "-Source", self.NUGET_FEED_URL,
                "-Version", version,
                "-OutputDirectory", self.TMP_DIR,
                "-DirectDownload",
                "-ConfigFile", config_path,
            ]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            if result.stdout:
                print(result.stdout)
            # Find the downloaded .nupkg file
            pkg_dir = os.path.join(self.TMP_DIR, f"{name}.{version}")
            for file in os.listdir(pkg_dir):
                if file.endswith(".nupkg"):
                    src = os.path.join(pkg_dir, file)
                    os.rename(src, filepath)
                    print(f"Downloaded: {filename}")
                    break
            # Remove all non-nupkg files in the self.TMP_DIR
            files = os.listdir(self.TMP_DIR)
            for file in files:
                try:
                    # Check if file is a directory
                    full_path = os.path.join(self.TMP_DIR, file)
                    if os.path.isdir(full_path):
                        shutil.rmtree(full_path)  # Recursively deletes directory and contents
                    elif not file.endswith(".nupkg"):
                        os.remove(full_path)
                except Exception as e:
                    print(f"Failed to remove {file} in {self.TMP_DIR}. It may not be a directory or file.")
                    print(e)
        finally:
            if tmp_config_path:
                os.unlink(tmp_config_path)

        return filepath

    def upload_to_github(self, package_file):
        """Upload a package to GitHub NuGet repository"""
        if not self.GITHUB_TOKEN:
            print("GITHUB_TOKEN environment variable not set. Skipping GitHub upload.")
            return False

        print(f"Uploading {os.path.basename(package_file)} to GitHub Packages...")
        try:
            cmd = [
                "dotnet", "nuget", "push", package_file,
                "--source", self.GITHUB_NUGET_URL,
                "--api-key", self.GITHUB_TOKEN,
                "--skip-duplicate"
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

    def upload_all_packages_to_github(self):
        """Upload all downloaded packages to GitHub NuGet repository"""
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

    def sync_packages(self):
        if not self.allowed_packages:
            click.echo("No packages specified. Nothing to sync.")
            return
        click.echo(f"Will sync the following packages: {[p.get('name', p) for p in self.allowed_packages]}")
        skipped = 0
        successful = 0
        failed = 0
        for pkg in self.allowed_packages:
            pkg_name = pkg.get('name', pkg)
            versions = pkg.get('versions', [])
            published = self.get_github_published_versions(pkg_name)
            for version in versions:
                if version in published:
                    print(f"Already published: {pkg_name} {version} — skipping")
                    skipped += 1
                    continue
                try:
                    package_file = self.download_package(pkg_name, version)
                    # Upload to GitHub after successful download
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

AZDO_FEED_BASE = "https://pkgs.dev.azure.com/Keyfactor/_packaging/KeyfactorPackages/nuget/v3/flat2"


def _validate_versions(name, versions, az_pat):
    """Check that each version exists in the Azure DevOps feed."""
    resp = requests.get(
        f"{AZDO_FEED_BASE}/{name.lower()}/index.json",
        auth=("any", az_pat),
        timeout=15,
    )
    if resp.status_code != 200:
        raise click.ClickException(f"Package '{name}' not found in Azure DevOps feed.")
    available = set(resp.json().get("versions", []))
    missing = [v for v in versions if v not in available]
    if missing:
        raise click.ClickException(
            f"Version(s) not found in Azure DevOps feed: {', '.join(missing)}\n"
            f"Available: {', '.join(sorted(available))}"
        )


def _write_versions_to_file(packages_file, name, versions):
    """
    Insert versions into packages_file using line-based editing to preserve
    all comments and formatting. Returns (added, skipped) version lists.
    """
    with open(packages_file, 'r') as f:
        lines = f.readlines()

    # Parse current state to know which versions already exist
    with open(packages_file, 'r') as f:
        data = yaml.safe_load(f)
    packages = data.get('packages') or []
    existing = next((p for p in packages if p.get('name', '').lower() == name.lower()), None)

    already_present = {str(v) for v in existing.get('versions', [])} if existing else set()
    to_add = [v for v in versions if v not in already_present]
    skipped = [v for v in versions if v in already_present]

    if not to_add:
        return [], skipped

    if existing:
        # Find the last version line for this package and insert after it.
        # Locate the `- name: <name>` line first.
        pkg_line = next(
            (i for i, l in enumerate(lines) if l.strip().lstrip('- ').startswith(f'name: {name}')),
            None,
        )
        if pkg_line is None:
            raise click.ClickException(f"Could not locate '{name}' in {packages_file}.")

        # Walk forward to find the last `- <version>` line inside this package block.
        last_ver_line = None
        ver_indent = None
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
                    break  # hit next key or next package
            elif stripped.startswith('- name:'):
                break  # hit next package without finding versions

        if last_ver_line is None:
            raise click.ClickException(f"Could not find versions block for '{name}'.")

        for v in reversed(to_add):
            lines.insert(last_ver_line + 1, ' ' * ver_indent + f'- {v}\n')
    else:
        # Append new package block at the end of the file.
        if lines and not lines[-1].endswith('\n'):
            lines.append('\n')
        lines.append(f'  - name: {name}\n')
        lines.append(f'    versions:\n')
        for v in to_add:
            lines.append(f'      - {v}\n')

    with open(packages_file, 'w') as f:
        f.writelines(lines)

    return to_add, skipped


@click.group()
def cli():
    """Manage NuGet package sync between Azure DevOps and GitHub Packages."""
    pass


@cli.command()
@click.argument("packages_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--package", default=None, help="Sync only this package name (must exist in the packages file).")
def sync(packages_file, package):
    """Sync packages from Azure DevOps to GitHub Packages."""
    syncer = NuGetSyncer(packages_file, package_filter=package)
    syncer.sync_packages()


@cli.command()
@click.argument("packages_file", type=click.Path(dir_okay=False))
@click.argument("name")
@click.argument("versions", nargs=-1, required=True)
@click.option("--skip-validate", is_flag=True, default=False,
              help="Skip Azure DevOps feed validation.")
def register(packages_file, name, versions, skip_validate):
    """Add NAME with one or more VERSIONS to PACKAGES_FILE.

    Validates each version exists in the Azure DevOps feed before writing.
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


if __name__ == "__main__":
    cli()
