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
gcloud secrets create smtp-password --replication-policy="automatic"

# Aggiungere i valori (sostituisci con i tuoi valori reali)
# IMPORTANTE: Non committare mai i valori reali in questo file!
echo -n "YOUR_GEMINI_API_KEY_HERE" | gcloud secrets versions add gemini-api-key --data-file=-
echo -n "mongodb+srv://USERNAME:PASSWORD@CLUSTER.mongodb.net/DATABASE?retryWrites=true&w=majority" | gcloud secrets versions add mongodb-uri --data-file=-
echo -n "your-super-secret-session-key-minimum-32-characters-long" | gcloud secrets versions add jwt-secret --data-file=-
echo -n "YOUR_SMTP_APP_PASSWORD" | gcloud secrets versions add smtp-password --data-file=-
```

**Secrets utilizzati**:
- `gemini-api-key`: Chiave API Google Gemini
- `mongodb-uri`: Connection string MongoDB Atlas
- `jwt-secret`: Chiave segreta per sessioni (SESSION_SECRET)
- `smtp-password`: Password/App Password per invio email SMTP

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

Il file `cloudbuild.yaml` contiene tutti i passi necessari:
1. Build immagine Docker con tag BUILD_ID e latest
2. Push a Artifact Registry
3. Deploy su Cloud Run con secrets e env vars configurati

**Nota**: `cloudbuild.yaml` contiene configurazioni specifiche (bucket, email). Modifica prima del deploy se necessario.

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
    --set-secrets=GOOGLE_API_KEY=gemini-api-key:latest,MONGODB_URI=mongodb-uri:latest,JWT_SECRET_KEY=jwt-secret:latest,SMTP_PASSWORD=smtp-password:latest \
    --set-env-vars=GCS_ENABLED=true,GCS_BUCKET_NAME=YOUR_BUCKET_NAME,SMTP_HOST=smtp.gmail.com,SMTP_PORT=587,SMTP_USER=your_email@gmail.com,FRONTEND_URL=https://YOUR_SERVICE_URL
```

**Variabili d'ambiente**:
- `GCS_ENABLED`: Abilita storage su Google Cloud Storage
- `GCS_BUCKET_NAME`: Nome bucket GCS per libri e copertine
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`: Configurazione email SMTP
- `FRONTEND_URL`: URL del servizio Cloud Run (per link in email)

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
gsutil cors set cors.json gs://YOUR_BUCKET_NAME
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
