# Freelance Lead Hunter V4

V4 separates the system into two services:

1. **Hunter (GitHub Actions)** — searches automatically every 3 hours, scores/deduplicates leads, stores them in Supabase and pushes high-quality new leads to Telegram.
2. **Telegram Bot (Railway/Render/VPS)** — stays online so you can ask for `/leads`, filter by `/stack go`, mark leads as applied/saved/discarded, see `/stats`, and launch GitHub Actions with `/refresh`.

## What V4 searches

### Backend
Java, Spring Boot, Spring/WebFlux, Quarkus, **Go/Golang**, Node.js/NestJS, Python, Kotlin, REST APIs, API integrations and microservices.

### Cloud / Platform / DevOps
AWS, Azure, Kubernetes/K8s, Terraform, Docker, Helm, ArgoCD, GitHub Actions, Jenkins and CI/CD.

### Data / messaging
Redis, Kafka, RabbitMQ, PostgreSQL/SQL and DynamoDB.

### Observability
Grafana, Prometheus, Loki, Tempo and OpenTelemetry.

### Secondary opportunities
Android/Kotlin, Python/Bash automation and scripting.

### Intent signals
Freelance, contractor, contract, consultant, part-time, short-term, project-based, one-time, hourly, urgent/ASAP, "need help", "looking for someone", "seeking" and remote.

### Geography
Remote first. Positive signals include LATAM, Latin America, Peru, Americas, worldwide, US/Canada/Mexico/Colombia/Chile. Posts requiring US-only location/citizenship or onsite-only are penalized.

### Sources
Public LinkedIn posts via Serper/Google, Upwork public job pages, Freelancer, Workana, Contra, Remotive, RemoteOK and Arbeitnow.

The hunter does **not** automate LinkedIn/Upwork login or send DMs/applications. Telegram's `Abrir` button opens the original URL in your own browser/app, where your normal login session is used.

## Query rotation / Serper cost control

GitHub Actions runs every 3 hours. There are 4 rotating query groups, so each category is revisited at least every 12 hours. Two broad public-need LinkedIn queries run every execution. This keeps the hunter active all day without burning all Serper credits.

See the exact live plan locally with:

```bash
python -m hunter.show_search_plan
```

The bot also supports:

```text
/searchplan
```

## 1. Create Supabase

Create a free Supabase project, open **SQL Editor**, and run:

```text
sql/supabase_schema.sql
```

Then copy:

- Project URL -> `SUPABASE_URL`
- Service role key -> `SUPABASE_SERVICE_ROLE_KEY`

The service-role key is a server secret. Never put it in frontend/browser code or commit it to GitHub.

## 2. GitHub Actions secrets

Repository -> Settings -> Secrets and variables -> Actions -> New repository secret.

Create:

```text
SERPER_API_KEY
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

The workflow `.github/workflows/hunter.yml` runs automatically every 3 hours and can also be started manually.

## 3. Telegram bot commands

Run the bot as a long-running worker on Railway, Render, Fly.io or your own VPS/PC:

```bash
pip install -r requirements.txt
python -m bot.telegram_bot
```

Configure these environment variables on the bot host:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_ALLOWED_CHAT_ID
GITHUB_REPO=owner/repository
GITHUB_TOKEN=your_fine_grained_pat
GITHUB_WORKFLOW=hunter.yml
GITHUB_REF=main
```

Commands:

```text
/leads                 New/pending leads
/top                   Best NEW/SAVED leads
/today                 Leads found in the last 24h
/source LinkedIn       Filter by source
/source Upwork
/stack go              Go/Golang-related leads
/stack java
/stack kubernetes
/saved
/applied
/contacted
/replied
/stats
/searchplan             Show what the hunter targets
/refresh                Trigger GitHub Actions immediately
/help
```

Every Telegram lead card has buttons:

- **Abrir** — opens the original LinkedIn/Upwork/etc URL
- **Guardar** — status SAVED
- **Apliqué** — status APPLIED
- **Descartar** — status DISCARDED
- **Contacté** — status CONTACTED
- **Respondió** — status REPLIED
- **Cliente** — status CLIENT

## 4. GitHub token for `/refresh`

Create a fine-grained Personal Access Token that can access only this repository and has **Actions: Read and write**. Store it only on the Telegram bot host as `GITHUB_TOKEN`.

The scheduled workflow itself does not need this PAT. `/refresh` uses it to call GitHub's workflow-dispatch API.

## Local test

Copy `.env.example` to `.env`, fill your secrets, then:

```bash
pip install -r requirements.txt
python -m hunter.show_search_plan
python -m hunter.lead_hunter
python -m bot.telegram_bot
```

Do not commit `.env`.
