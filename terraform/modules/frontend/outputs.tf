output "cloudfront_url" {
  value = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "frontend_url" {
  value = "https://${local.frontend_domain}"
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.frontend.id
}