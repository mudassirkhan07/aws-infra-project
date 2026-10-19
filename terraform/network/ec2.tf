
resource "aws_iam_role" "ec2_ssm" {
  name = "infra-ec2-ssm-role-use1"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "sts:AssumeRole"

        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "infra-ec2-ssm-role"
  }
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ec2_ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ec2_ssm" {
  name = "infra-ec2-ssm-profile-use1"
  role = aws_iam_role.ec2_ssm.name
}

resource "aws_instance" "app" {
  ami                         = var.ami_id
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.app.id]
  associate_public_ip_address = true
  iam_instance_profile        = aws_iam_instance_profile.ec2_ssm.name

  #checkov:skip=CKV_AWS_88:Public IP is retained for direct access to this learning demo; use SSM for administration.

  ebs_optimized = true
  monitoring    = true

  metadata_options {
    http_tokens = "required"
  }

  root_block_device {
    encrypted   = true
    volume_size = 8
  }

  user_data_replace_on_change = true

  user_data = <<-EOF
    #!/bin/bash
    set -eux

    apt-get update -y
    apt-get install -y docker.io

    systemctl enable --now docker

    docker run -d \
      --name app \
      --restart unless-stopped \
      -p 5000:${var.app_container_port} \
      ${var.app_image}
  EOF

  tags = {
    Name = "infra-app"
  }
}

output "app_public_ip" {
  description = "Public IP address of the application EC2 instance"
  value       = aws_instance.app.public_ip
}

output "app_url" {
  description = "URL for accessing the application"
  value       = "http://${aws_instance.app.public_ip}:5000"
}