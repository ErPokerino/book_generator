# Guida Deploy su Google Cloud Run

Questa guida descrive come deployare NarrAI su Google Cloud Run.

## Prerequisiti

1. Account Google Cloud Platform con billing abilitato
2. Google Cloud SDK installato (`gcloud`)
3. Docker installato (per test locale)
4. Accesso al progetto GCP

## Setup Iniziale

### 1. Configurare il progetto GCP

```bash
# Imposta il progetto
gcloud config set project YOUR_PROJECT_ID

# Abilita le API necessarie
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable artifactregistry.googleapis.com
```

### 2. Creare Artifact Registry

```bash
gcloud artifacts repositories create narrai \
    --repository-format=docker \
    --location=europe-west1 \
    --description="NarrAI Docker images"
```

### 3. Creare i Secrets in Secret Manager

```bash
# Creare i secrets
gcloud secrets create gemini-api-key --replication-policy="automatic"
gcloud secrets create mongodb-uri --replication-policy="automatic"
gcloud secrets create jwt-secret --replication-policy="automatic"

# Aggiungere i valori (sostituisci con i tuoi valori reali)
echo -n "YOUR_GEMINI_KEY" | gcloud secrets versions add gemini-api-key --data-file=-
echo -n "mongodb+srv://user:pass@cluster.mongodb.net/narrai?retryWrites=true&w=majority" | gcloud secrets versions add mongodb-uri --data-file=-
echo -n "your-super-secret-jwt-key-change-this" | gcloud secrets versions add jwt-secret --data-file=-
```

**Nota**: Per GCP credentials, puoi:
- Includere il file JSON nel container (attuale)
- Oppure usare Workload Identity (consigliato per produzione)

### 4. Configurare IAM per Cloud Build

```bash
# Concedi permessi a Cloud Build per deployare su Cloud Run
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
    --role="roles/run.admin"

# Concedi permessi per accedere ai secrets
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Concedi permessi per push su Artifact Registry
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
    --role="roles/artifactregistry.writer"
```

### 5. Configurare Service Account per Cloud Run

```bash
# Concedi permessi al service account di Cloud Run per accedere ai secrets
gcloud run services add-iam-policy-binding narrai \
    --region=europe-west1 \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

## Deploy

### Opzione 1: Deploy Automatico con Cloud Build (Consigliato)

```bash
# Trigger Cloud Build da GitHub (configurare trigger nel Cloud Console)
# Oppure esegui manualmente:
gcloud builds submit --config=cloudbuild.yaml
```

### Opzione 2: Deploy Manuale

```bash
# 1. Build locale (test)
docker build -t narrai .

# 2. Tag e push a Artifact Registry
docker tag narrai europe-west1-docker.pkg.dev/YOUR_PROJECT_ID/narrai/backend:v1
docker push europe-west1-docker.pkg.dev/YOUR_PROJECT_ID/narrai/backend:v1

# 3. Deploy su Cloud Run
gcloud run deploy narrai \
    --image=europe-west1-docker.pkg.dev/YOUR_PROJECT_ID/narrai/backend:v1 \
    --region=europe-west1 \
    --platform=managed \
    --allow-unauthenticated \
    --memory=2Gi \
    --cpu=2 \
    --timeout=3600 \
    --set-secrets=GOOGLE_API_KEY=gemini-api-key:latest,MONGODB_URI=mongodb-uri:latest,JWT_SECRET_KEY=jwt-secret:latest \
    --set-env-vars=GCS_ENABLED=true,GCS_BUCKET_NAME=narrai-books-483022
```

## Configurazioni Aggiuntive

### MongoDB Atlas Whitelist

Cloud Run usa IP dinamici. Su MongoDB Atlas:
1. Vai su Network Access
2. Aggiungi `0.0.0.0/0` (Allow Access from Anywhere)
3. **Importante**: Assicurati che l'autenticazione sia forte (password complessa)

### GCS CORS (se necessario)

Se hai bisogno di CORS per GCS:

```bash
# Crea cors.json
cat > cors.json << EOF
[
  {
    "origin": ["https://narrai-xyz.run.app"],
    "method": ["GET", "PUT", "POST"],
    "responseHeader": ["Content-Type"],
    "maxAgeSeconds": 3600
  }
]
EOF

# Applica CORS
gsutil cors set cors.json gs://narrai-books-483022
```

### Aggiornare FRONTEND_URL dopo il deploy

Dopo il primo deploy, ottieni l'URL di Cloud Run e aggiorna il secret:

```bash
SERVICE_URL=$(gcloud run services describe narrai --region=europe-west1 --format="value(status.url)")

# Aggiungi come env var (non secret)
gcloud run services update narrai \
    --region=europe-west1 \
    --update-env-vars="FRONTEND_URL=$SERVICE_URL"
```

## Monitoraggio

```bash
# Visualizza logs
gcloud run services logs read narrai --region=europe-west1

# Visualizza metriche
gcloud run services describe narrai --region=europe-west1
```

## Troubleshooting

### Container non si avvia

- Verifica i logs: `gcloud run services logs read narrai --region=europe-west1`
- Controlla che i secrets esistano: `gcloud secrets list`
- Verifica che il service account abbia i permessi necessari

### Errori di connessione MongoDB

- Verifica che MongoDB Atlas permetta accesso da `0.0.0.0/0`
- Controlla che `MONGODB_URI` nel secret sia corretto
- Verifica la connection string nel secret

### File statici non serviti

- Verifica che `static/` esista nel container: `gcloud run services describe narrai --region=europe-west1 --format="yaml(spec.template.spec.containers)"`
- Controlla i logs per errori di mount dei file statici

## Costi Stimati

- Cloud Run: ~$0.40 per milione di richieste + CPU/Memory usage
- Artifact Registry: ~$0.10 per GB/mese
- Secret Manager: Gratuito per < 6 milioni di accessi/mese

Per generazioni lunghe (libri), considera che Cloud Run ha timeout massimo di 60 minuti. Per job più lunghi, considera Cloud Tasks in futuro.
