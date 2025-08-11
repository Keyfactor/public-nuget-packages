# public-nuget-packages

Publicly available NuGet packages useful for building Keyfactor integrations

To access these packages add https://nuget.pkg.github.com/Keyfactor/index.json as a NuGet package source to Visual
Studio or other development tools.

Some package availability changes from time to time. Please view the `CHANGELOG.md` for further details on changes to
available libraries.

## Adding a Nuget Package and/or Version

### Via GitHub Actions

To add a Nuget package modify the [packages.yml](./packages.yml) file in the root of this repository.

> [!IMPORTANT]
> The package and version must exist in this Nuget repository before it can be added to the `packages.yml` file.
> https://dev.azure.com/Keyfactor/Engineering/_artifacts/feed/KeyfactorPackages@Local

The to trigger the sync run the
workflow [Sync NuGet Packages](https://github.com/Keyfactor/public-nuget-packages/actions/workflows/sync-nuget.yml). Once
it's complete, the package will be available in the Keyfactor Public GitHub Package Registry (GPR).

### Manually using dotnet CLI

In order to add a nuget package to the Keyfactor Public GitHub Package Registry (GPR), you must download from the 
[DevOps Artifacts site](https://dev.azure.com/Keyfactor/Engineering/_artifacts/feed/KeyfactorPackages@Local) 
and then push it to the GPR using a Personal Access Token (PAT).

Steps:
1. Create a new PAT with access with `write:packages` access
2. Grant SSO to the PAT
3. Run the following command to push the package to the GitHub Package Registry (GPR):

```bash
dotnet nuget push ./Your.Package.1.0.0.nupkg \
  --source "https://nuget.pkg.github.com/keyfactor/index.json" \
  --api-key $GITHUB_TOKEN
```
