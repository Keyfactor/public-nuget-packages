// Repository reference
data "github_repository" "nuget_repo" {
  full_name = "Keyfactor/public-nuget-packages"
}

// Create the Azure DevOps PAT secret for NuGet package downloads
resource "github_actions_secret" "az_devops_pat" {
  repository      = data.github_repository.nuget_repo.name
  secret_name     = "AZ_DEVOPS_PAT"
  plaintext_value = var.az_devops_pat
}

// Create the GitHub PAT secret for GitHub Package uploads
// Note: This is separate from the built-in GITHUB_TOKEN
resource "github_actions_secret" "github_pat" {
  repository      = data.github_repository.nuget_repo.name
  secret_name     = "GH_NUGET_TOKEN"
  plaintext_value = var.repo_github_pat
}

