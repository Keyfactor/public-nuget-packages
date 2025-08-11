// Variables
# variable "github_token" {
#   description = "GitHub personal access token with repo permissions"
#   type        = string
#   sensitive   = true
# }

variable "az_devops_pat" {
  description = "Azure DevOps personal access token with package read permissions"
  type        = string
  sensitive   = true
}

variable "repo_github_pat" {
  description = "GitHub personal access token with package write permissions"
  type        = string
  sensitive   = true
}