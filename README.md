# public-nuget-packages

Publicly available NuGet packages useful for building Keyfactor integrations

To access these packages add `https://nuget.pkg.github.com/Keyfactor/index.json` as a NuGet package source in Visual Studio or other development tools.

Some package availability changes from time to time. Please view the `CHANGELOG.md` for further details on changes to available libraries.

## Adding a NuGet Package and/or Version

### Via GitHub Actions

1. Add the package and version(s) to [`packages.yml`](./packages.yml).
2. Trigger the [Sync NuGet Packages](https://github.com/Keyfactor/public-nuget-packages/actions/workflows/sync-nuget.yml) workflow.

Once complete, the package will be available in the Keyfactor Public GitHub Package Registry (GPR). The workflow runs automatically on a weekly schedule and skips any versions already published.

> [!IMPORTANT]
> The package and version must already exist in the Azure DevOps feed before adding it to `packages.yml`:
> https://dev.azure.com/Keyfactor/Engineering/_artifacts/feed/KeyfactorPackages@Local

### Running Locally

**Prerequisites:** Python 3.8+, `nuget` CLI (with Mono on Linux), `dotnet` CLI

1. Create a `.env` file in the repo root:

```bash
export AZ_DEVOPS_PAT=<Azure DevOps PAT with package read permissions>
export GITHUB_TOKEN=<GitHub PAT with write:packages permission>
export GITHUB_ORG=keyfactor
```

2. Install dependencies:

```bash
python -m venv venv && source venv/bin/activate
pip install -e .
```

#### CLI Reference

The sync script is a CLI with two commands:

**`sync`** — Download and upload packages defined in a packages file. Skips versions already published to the GitHub Package Registry.

```bash
# Sync all packages
source .env && python scripts/sync_nuget.py sync packages.yml

# Sync a single package
source .env && python scripts/sync_nuget.py sync packages.yml --package Keyfactor.PKI
```

**`register`** — Add a package and version(s) to a packages file. Validates that each version exists in the Azure DevOps feed before writing.

```bash
# Register a new version of an existing package
source .env && python scripts/sync_nuget.py register packages.yml Keyfactor.PKI 8.4.0

# Register multiple versions at once
source .env && python scripts/sync_nuget.py register packages.yml Keyfactor.PKI 8.4.0 8.5.0

# Register a brand new package
source .env && python scripts/sync_nuget.py register packages.yml Keyfactor.NewPackage 1.0.0

# Skip Azure DevOps feed validation
python scripts/sync_nuget.py register packages.yml Keyfactor.PKI 8.4.0 --skip-validate
```

After registering, run `sync` to push the new version(s) to the GitHub Package Registry.

### Manually using dotnet CLI

1. Create a GitHub PAT with `write:packages` access and grant it SSO.
2. Push the package:

```bash
dotnet nuget push ./Your.Package.1.0.0.nupkg \
  --source "https://nuget.pkg.github.com/keyfactor/index.json" \
  --api-key $GITHUB_TOKEN
```
