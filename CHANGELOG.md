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
