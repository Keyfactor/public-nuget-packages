// Outputs
output "repository_name" {
  value = data.github_repository.nuget_repo.name
}

output "secrets_configured" {
  value = [
    github_actions_secret.az_devops_pat.secret_name,
    github_actions_secret.github_pat.secret_name
  ]
}
