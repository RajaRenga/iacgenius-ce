account_id = "123456789012"
subnet_id  = "subnet-REPLACE"
name       = "iacgenius-ce"
source_zip = "../../dist/iacgenius-ce-spot.zip"
running    = true

# Existing Secrets Manager secret holding only your model API key (never put the key itself here).
# model_secret_arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:YOUR_SECRET"
# model_name       = "deepseek-v4.1-flash"
# model_base_url   = "https://YOUR_PROVIDER/v1"   # OpenAI-compatible endpoint serving that model

# spot_instance_types = ["t3.large", "t3a.large"]
# container_memory_mb = 6144
# public_ip           = true