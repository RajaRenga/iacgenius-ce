# Instance role: SSM + the state bucket + the model secret only.
# CE generation needs no AWS read permissions, so there is no audit role here.
# The Hermes container itself gets no credentials (metadata disabled, hop limit 1).
resource "aws_iam_role" "host" {
  name_prefix = "${var.name}-"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.host.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "host" {
  name_prefix = "${var.name}-"
  role        = aws_iam_role.host.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = concat([
      {
        Effect = "Allow",
        Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket", "s3:GetBucketLocation"],
        Resource = [aws_s3_bucket.data.arn, "${aws_s3_bucket.data.arn}/*"]
      }
    ], var.model_secret_arn == "" ? [] : [
      {
        Effect   = "Allow",
        Action   = ["secretsmanager:GetSecretValue"],
        Resource = [var.model_secret_arn]
      }
    ])
  })
}

resource "aws_iam_instance_profile" "host" {
  name_prefix = "${var.name}-"
  role        = aws_iam_role.host.name
}