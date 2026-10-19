variable "region" {
  type    = string
  default = "us-east-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "public_subnet_cidr" {
  type    = string
  default = "10.0.1.0/24"
}

variable "app_ingress_cidr" {
  type        = string
  description = "CIDR allowed to reach the app port"
  default     = "0.0.0.0/0"
}

variable "ssh_cidr" {
  type        = string
  description = "CIDR allowed to SSH, e.g. 203.0.113.5/32"
  default     = "127.0.0.1/32" # effectively closed until you set it
}

variable "instance_type" {
  type        = string
  description = "EC2 instance type"
  default     = "t3.micro"
}

variable "ami_id" {
  type        = string
  description = "x86_64 Amazon Linux 2023 AMI ID for ap-south-1"
  default     = "ami-0f8a61b66d1accaee"
}

variable "app_image" {
  type        = string
  description = "Docker image to run"
  default     = "nginx:stable"
}

variable "app_container_port" {
  type        = number
  description = "Port the app listens on inside the container"
  default     = 80
}