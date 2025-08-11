// GitHub provider configuration
terraform {
  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 5.0"
    }
  }
}

// Configure the GitHub Provider
provider "github" {
  owner = "Keyfactor"
}