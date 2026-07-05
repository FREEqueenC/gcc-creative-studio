# Aetheris X Creative Studio - Google Cloud Run Deployment Script
# This PowerShell script automates building the backend container via Cloud Build and deploying it to Cloud Run.

$PROJECT_ID = gcloud config get-value project
if (-not $PROJECT_ID) {
    Write-Error "No active Google Cloud project detected. Please run 'gcloud config set project <PROJECT_ID>' first."
    exit
}

Write-Host "Deploying Aetheris X backend to Google Cloud Run in project: $PROJECT_ID" -ForegroundColor Cyan

# Define configuration parameters (Modify these or load them from your local backend/.env)
$SERVICE_NAME = "aetherisx-backend"
$REGION = "us-central1"
$DB_CONNECTION_NAME = "${PROJECT_ID}:${REGION}:ai-studio-7ff8410d" # Update this to match your Cloud SQL connection name if using Cloud SQL

$PROJECT_NUMBER = gcloud projects describe $PROJECT_ID --format="value(projectNumber)"
$SIGNING_SA_EMAIL = "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Read settings from backend/.env if available
$ENV_VARS = @(
    "ENVIRONMENT=production",
    "GOOGLE_CLOUD_PROJECT=$PROJECT_ID",
    "PROJECT_ID=$PROJECT_ID",
    "FRONTEND_URL=https://aetherisx.studio",
    "GENMEDIA_BUCKET=$PROJECT_ID-cs-development-bucket", # Matches standard deployment bucket names
    "SIGNING_SA_EMAIL=$SIGNING_SA_EMAIL"
)

# Append database settings
$ENV_VARS += "DB_USER=studio_user"
$ENV_VARS += "DB_PASS=studio_pass"
$ENV_VARS += "DB_NAME=creative_studio"
$ENV_VARS += "DB_HOST=127.0.0.1" # Cloud SQL Auth Proxy connects locally inside the container
$ENV_VARS += "USE_CLOUD_SQL_AUTH_PROXY=true"

# Load Pinata JWT if present in local .env
$LOCAL_ENV_PATH = Join-Path (Get-Location) "backend\.env"
if (Test-Path $LOCAL_ENV_PATH) {
    $PinataLine = Get-Content $LOCAL_ENV_PATH | Select-String "PINATA_JWT="
    if ($PinataLine) {
        $ENV_VARS += $PinataLine.ToString().Trim()
        Write-Host "Loaded PINATA_JWT configuration from local backend/.env" -ForegroundColor Green
    }
}

$ENV_VARS_STRING = [string]::Join(",", $ENV_VARS)

Write-Host "Triggering cloud build and deploying service..." -ForegroundColor Yellow

# Execute the deployment command
gcloud run deploy $SERVICE_NAME `
    --source ./backend `
    --region $REGION `
    --allow-unauthenticated `
    --set-env-vars $ENV_VARS_STRING `
    --add-cloudsql-instances $DB_CONNECTION_NAME `
    --timeout 3600 `
    --memory 2Gi `
    --cpu 2

if ($LASTEXITCODE -eq 0) {
    Write-Host "Deployment Completed Successfully!" -ForegroundColor Green
} else {
    Write-Error "Deployment failed. Please inspect the Cloud Build or Cloud Run logs in the GCP Console."
}
