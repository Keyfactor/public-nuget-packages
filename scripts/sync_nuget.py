import os
import shutil
import subprocess
import tempfile
import requests
import yaml

class NuGetSyncer:
    def __init__(self):
        self.NUGET_FEED_URL = "https://pkgs.dev.azure.com/Keyfactor/_packaging/KeyfactorPackages/nuget/v3/index.json"
        self.GITHUB_NUGET_URL = "https://nuget.pkg.github.com/keyfactor/index.json"
        self.GITHUB_TOKEN = os.getenv("GH_NUGET_TOKEN", os.getenv("GITHUB_TOKEN"))
        self.AZ_DEVOPS_PAT = os.getenv("AZ_DEVOPS_PAT")
        self.TMP_DIR = "nupkgs"
        self.PACKAGES_YML = "packages.yml"
        self.GITHUB_NUGET_BASE = "https://nuget.pkg.github.com/keyfactor"
        self.allowed_packages = self.load_allowed_packages()
        self._github_versions_cache = {}
        os.makedirs(self.TMP_DIR, exist_ok=True)

    def load_allowed_packages(self):
        try:
            with open(self.PACKAGES_YML, 'r') as file:
                yaml_data = yaml.safe_load(file)
                return yaml_data.get('packages', [])
        except Exception as e:
            print(f"Error loading packages.yml: {e}")
            return set()

    def get_all_packages_and_versions(self):
        # This function should be implemented to get all allowed packages and their versions
        # For now, let's assume you have a list of versions for each package in packages.yml
        # You can extend this to read from example_versions.json or another source
        # Example: { 'PackageA': ['1.0.0', '2.0.0'], ... }
        # For demonstration, we'll just return the allowed packages with no versions
        if isinstance(self.allowed_packages, str):
            return f"{self.allowed_packages}".split(",")
        elif isinstance(self.allowed_packages, list) or isinstance(self.allowed_packages, set):
            return self.allowed_packages
        return {pkg: [] for pkg in self.allowed_packages}

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
            subprocess.run(cmd, check=True)
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
            print("No packages specified in packages.yml. Nothing to sync.")
            return
        print(f"Will sync the following packages: {self.allowed_packages}")
        packages_and_versions = self.get_all_packages_and_versions()
        skipped = 0
        successful = 0
        failed = 0
        for pkg in packages_and_versions:
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
                except Exception as e:
                    print(f"Failed to sync {pkg_name} {version}: {e}")
                    failed += 1

        print("\nSync summary:")
        print(f"  Uploaded:  {successful}")
        print(f"  Skipped:   {skipped}")
        print(f"  Failed:    {failed}")

if __name__ == "__main__":
    syncer = NuGetSyncer()

    # Option 1: Download and upload packages from packages.yml
    syncer.sync_packages()

    # Option 2: Upload all existing packages in nupkgs directory
    # syncer.upload_all_packages_to_github()
