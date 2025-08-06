# public-nuget-packages

Publicly available NuGet packages useful for building Keyfactor integrations

To access these packages add https://nuget.pkg.github.com/Keyfactor/index.json as a NuGet package source to Visual
Studio or other development tools.

Some package availability changes from time to time. Please view the `CHANGELOG.md` for further details on changes to
available libraries.

## Adding a package source

In order to add a nuget package to the keyfactor GPR, you must download from the DevOps Artifacts site and then push it
to the GitHub Package Registry (GPR) using a Personal Access Token (PAT).

1. Create a new PAT with access with `write:packages` access
2. Grant SSO to the PAT
3. Run the following command to push the package to the GitHub Package Registry (GPR):

```bash
dotnet nuget push ./Your.Package.1.0.0.nupkg \
  --source "https://nuget.pkg.github.com/keyfactor/index.json" \
  --api-key $GITHUB_TOKEN
```
