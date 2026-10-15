# AWS Preview Environments per Pull Request

Every pull request gets its own temporary preview environment on AWS, built with
GitHub Actions, Terraform, Docker, ECR, ECS Fargate and an ALB.
It is destroyed automatically when the PR is closed.

Status: in progress (building step by step).
