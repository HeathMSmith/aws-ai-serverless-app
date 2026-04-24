output "api_endpoint" {
  value = module.apigateway.api_endpoint
}
output "cloudfront_url" {
  value = module.frontend.cloudfront_url
}
output "frontend_url" {
  value = module.frontend.frontend_url
}
output "cloudfront_distribution_id" {
  value = module.frontend.cloudfront_distribution_id
}