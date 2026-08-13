#!/bin/bash
set -e

echo "🚀 Preparing AutonomyGuard for AWS SAM Deployment..."

# 1. Prepare clean source directory for SAM
echo "📦 Packaging dependencies..."
rm -rf sam_build_src
mkdir -p sam_build_src
cp -r autonomy_guard sam_build_src/

# Write a clean requirements.txt for SAM to use
cat <<EOF > sam_build_src/requirements.txt
fastapi>=0.100.0,<1.0.0
uvicorn[standard]>=0.30.0,<1.0.0
pydantic>=2.0.0,<3.0.0
pydantic-settings>=2.0.0,<3.0.0
structlog>=24.0.0,<25.0.0
mangum>=0.17.0,<1.0.0
aioboto3>=13.0.0,<14.0.0
EOF

# 2. Build via SAM
echo "🔨 Building SAM application..."
sam build

# 3. Deploy via SAM
echo "☁️ Deploying to AWS..."
sam deploy --stack-name autonomy-guard --resolve-s3 --capabilities CAPABILITY_IAM

echo "✅ Deployment complete!"
