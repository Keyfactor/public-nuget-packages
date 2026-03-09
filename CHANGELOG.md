# [1.7.0](https://github.com/Keyfactor/public-nuget-packages/compare/v1.6.1...v1.7.0) (2026-03-09)


### Features

* **ci:** Add workflow to create PRs automatically if new packages are released. ([fd7d73e](https://github.com/Keyfactor/public-nuget-packages/commit/fd7d73eee3bbe8c69bbb420538bc7b4ace955ce9))

## [1.6.1](https://github.com/Keyfactor/public-nuget-packages/compare/v1.6.0...v1.6.1) (2026-03-09)


### Bug Fixes

* **cli:** If failures exit code non-zero ([a4bc399](https://github.com/Keyfactor/public-nuget-packages/commit/a4bc399d362812d254e10f2ed6a802cbdc2d38f3))

# [1.6.0](https://github.com/Keyfactor/public-nuget-packages/compare/v1.5.0...v1.6.0) (2026-03-09)


### Features

* **cli:** Add `upgrade` to fetch new releases of existing packages, and `sort` to sort versions oldest to latest. ([f62a9b4](https://github.com/Keyfactor/public-nuget-packages/commit/f62a9b4db4c6cf48e1453c8d1c68319c11b2a8f2))

# [1.5.0](https://github.com/Keyfactor/public-nuget-packages/compare/v1.4.0...v1.5.0) (2026-03-09)


### Features

* **cli:** Add `download` CLI function ([64c956a](https://github.com/Keyfactor/public-nuget-packages/commit/64c956ad68abe627f30d927dc84758f58d2267be))

# [1.4.0](https://github.com/Keyfactor/public-nuget-packages/compare/v1.3.1...v1.4.0) (2026-03-09)


### Features

* **cli:** Convert sync script to lightweight CLI. ([c106bcc](https://github.com/Keyfactor/public-nuget-packages/commit/c106bccccf82d515ea59b355df57b2a8396c4095))

## [1.3.1](https://github.com/Keyfactor/public-nuget-packages/compare/v1.3.0...v1.3.1) (2026-03-09)


### Bug Fixes

* **script:** Capture stderr and stdout ([0f4a172](https://github.com/Keyfactor/public-nuget-packages/commit/0f4a1721fabcb9bc37d4d72a747f420125a6188b))

# [1.3.0](https://github.com/Keyfactor/public-nuget-packages/compare/v1.2.0...v1.3.0) (2026-03-09)


### Features

* **script:** Add logic to generate a Nuget.config and skip already uploaded packages. ([9aed007](https://github.com/Keyfactor/public-nuget-packages/commit/9aed0074df9430ddcd9de1d78137f1dce580bdb6))

# [1.2.0](https://github.com/Keyfactor/public-nuget-packages/compare/v1.1.3...v1.2.0) (2026-03-09)


### Features

* Update packages ([4d9a32a](https://github.com/Keyfactor/public-nuget-packages/commit/4d9a32a09680c5a20e0e0b5842d6655ef2f8f153))

## [1.1.3](https://github.com/Keyfactor/public-nuget-packages/compare/v1.1.2...v1.1.3) (2026-01-15)


### Bug Fixes

* **pkg:** Add `Keyfactor.Orchestrators.Common v3.3.0` and `Keyfactor.PKI v8.2.2` ([d7e14b9](https://github.com/Keyfactor/public-nuget-packages/commit/d7e14b9a060413c2ba1b67cdd836099bf0e76370))

## [1.1.2](https://github.com/Keyfactor/public-nuget-packages/compare/v1.1.1...v1.1.2) (2025-08-11)


### Bug Fixes

* **ci:** Fix nugetconfig that gets generated in the action ([f8dd3d7](https://github.com/Keyfactor/public-nuget-packages/commit/f8dd3d78fc6ef5703a93436cf1f18874e3d02faf))
* **ci:** Fix nugetconfig that gets generated in the action ([260b3f7](https://github.com/Keyfactor/public-nuget-packages/commit/260b3f77595698d68284a29222db1c3f8fce5a8e))
* **ci:** Install mono to call nuget ([2f5cdd4](https://github.com/Keyfactor/public-nuget-packages/commit/2f5cdd42a96df83339bc9db19def5ba86c670d8a))

## [1.1.1](https://github.com/Keyfactor/public-nuget-packages/compare/v1.1.0...v1.1.1) (2025-08-11)


### Bug Fixes

* **scripts:** Update paths for tmp and packages.yml to run in root dir rather than scripts dir. ([2843a83](https://github.com/Keyfactor/public-nuget-packages/commit/2843a832fe19254a2b020e5da2b21b69aa0668cb))

# [1.1.0](https://github.com/Keyfactor/public-nuget-packages/compare/v1.0.0...v1.1.0) (2025-08-11)


### Features

* **ci:** Add CICD code to run sync in GitHub actions ([2080e31](https://github.com/Keyfactor/public-nuget-packages/commit/2080e314e38f9f35f50aff059ec70962c6b367ea))
* **repo:** Add tf code for adding PATs to secrets ([3759afd](https://github.com/Keyfactor/public-nuget-packages/commit/3759afdd3a685f14c74c03bed84cd0ae112f2402))
* **scripts:** Add scripts to pull and push nuget packages from Engineering Devops Nuget to Keyfactor GitHub Nuget. ([f724b5a](https://github.com/Keyfactor/public-nuget-packages/commit/f724b5afd75328a82c078f44cd53e1b970ef5d9f))

# 1.0.0 (2025-08-06)


### Features

* **ci:** Add semver release CI ([aa775ec](https://github.com/Keyfactor/public-nuget-packages/commit/aa775ec6bc2bbbe52daf7043d1491691933b3ebc))

July 10 2025
* Keyfactor.Common `2.9.0` added

June 02 2025
* Packages were removed due to signing vulnerabilites. A certificate was revoked due to an administrative error, invalidating the signatures on the following releases. This is flagged in code scanning utilites, but was not the result of any actual compromise of the signing key or codesigning process.
    * Keyfactor.Orchestrators.Common `3.0.0`
    * Keyfactor.Platform.IOrchestratorJobCompleteHandler `1.0.0`
    * Keyfactor.Platform.IOrchestratorRegistrationHandler `2.0.0`

* New packages were added for public accessibility. Some versions added (with a fourth dot version) were to address the aforementioned signing vulnerabilities.
    * Keyfactor.Orchestrators.IOrchestratorJobExtensions `1.0.0`
    * Keyfactor.PKI `5.7.0`
    * Keyfactor.PKI `6.3.0`
    * Keyfactor.PKI `7.8.0`
    * Keyfactor.PKI `8.1.0`
    * Keyfactor.Platform.IOrchestratorJobCompleteHandler `1.0.0.1`
    * Keyfactor.Platform.IOrchestratorRegistrationHandler `2.0.0.1`
    * Keyfactor.Platform.IOrchestratorRegistrationHandler `3.0.0`
