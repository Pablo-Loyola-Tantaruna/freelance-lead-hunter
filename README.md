# FreeBot V6 — AI-assisted applications

## V6.1: More usable leads, less silence

A real V5 scheduled run found 223 raw candidates, 7 above its minimum score,
4 new database records, and only 1 Telegram notification. That did **not** mean
only one opportunity existed; the notification threshold was too restrictive
for a competitive market.

- Telegram alerts: eligible project/agency/buyer leads scored **5+** rather than 6+.
- Max **5** alerts per run; sending remains *never* equivalent to applying.
- `/queue`: the top five eligible **NEW or SAVED** leads from the past 72 hours.
- `/backlog`: up to 15 eligible leads scored 4+ from the past seven days.
- More buyer/problem-oriented queries, without increasing the query count per run.
- GitHub Actions now prints stage diagnostics: old postings, low scores,
  duplicate URLs, new versus previously stored records, and alert candidates.
- We keep explicit location restrictions, generic-page rejection, and manual
  review before any outbound application.

The V6 Telegram commands require redeploying/restarting the **Telegram bot
worker**, while search/filter changes take effect on the next GitHub Actions
run after merge. A new PR merge does **not** restart a separate Railway/Render
worker automatically unless its deployment was configured to do so.

If `/queue` returns zero, check `/backlog`. If both are empty, read the
**Pipeline diagnostics** section of GitHub Actions logs to distinguish a quiet
market from filter or search problems.

---


V6 solves the **application bottleneck**: instead of just collecting job posts,
it prepares tailored pitches and makes permitted outbound email applications
possible after explicit human review. It does **not** automate marketplace
websites, login sessions, captchas, or direct messages.

### Telegram workflow

1. In an existing lead alert tap **🤖 Preparar candidatura**, or send
   `/queue` (the five highest-scoring NEW leads found in the past 48h).
2. The Telegram service creates an AI proposal **on demand**, with a safe
   deterministic template if the optional API is missing/unavailable.
3. For Upwork/Freelancer/Workana/Contra, tap **Abrir oferta y postular**
   and submit inside the platform. These sites are **never auto-contacted by email**.
4. For legitimate **email-based applications explicitly invited by the advertiser**,
   tap **Preparar correo** if the snippet includes an application address, or use
   `/email 123 jobs@company.com` after verifying the address on the original listing.
5. Telegram displays **the exact recipient, subject and body** in a signed preview.
   Only tapping **✅ CONFIRMAR Y ENVIAR EMAIL** sends the email, if delivery is enabled.
   The bot records a successful send as `CONTACTED` in Supabase and prevents repeated
   sends for the same lead. Review confirmations expire after 24 hours.

Commands: `/queue`, `/pitch 123`, `/email 123 jobs@company.com`, `/stats`.
**This is an opt-in, review-before-send workflow, not unattended auto-apply.**

### Optional AI drafts — configure on the Telegram bot host

```dotenv
OPENAI_API_KEY=<your API key>
OPENAI_MODEL=gpt-4.1-mini
FREELANCER_PROFILE="Backend engineer with professional Java/Spring Boot/Kubernetes experience..."
```

AI API usage is **separately billed** from ChatGPT subscriptions and sends
the public listing title/snippet and your configured public professional profile
to the provider. Keep confidential employer/customer information out of the
profile. The bot calls AI only after a draft/preview request, not every 3h scan.
Never commit API credentials.

Without `OPENAI_API_KEY`, the bot keeps working with a deterministic pitch template.

### Optional approved outbound email — configure on the Telegram bot host

```dotenv
EMAIL_SEND_ENABLED=1
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USER=<mailbox username>
SMTP_PASSWORD=<app password or SMTP credential>
SMTP_FROM=<verified sender email>
```

Use secure TLS ports 465/587. Choose a provider whose policies permit
transactional, individually approved job applications. Do not use your
corporate email, laptop, or confidential employer data. All values are server
secrets, **not** browser variables or GitHub repository code.

Outbound sending stays **disabled** until these env vars are configured. You
must redeploy/restart the **long-running Telegram bot** service for the new
commands; simply merging GitHub Actions does not update the deployed bot.
You may run `python -m bot.telegram_bot` locally with the environment configured
for testing. To receive alerts on schedule, GitHub Actions remains separate.

### Risk controls and limitations

- Manual review/approval before **every** outbound message; no mass cold-email.
- No bot-driven LinkedIn/Upwork/etc. browser submissions or unauthorized scraping.
- A job's **snippet is not proof** that an email is real or still accepting applications;
  check the original offer before confirming.
- Email delivery can fail or time out after reaching the provider. If uncertain,
  inspect your sent folder before retrying. Never assume an email was delivered
  solely because an SMTP connection was attempted.
- Using the bot creates no contracts and does not guarantee earnings. Track
  contacted, replied and client statuses to measure conversion.

### V6 verification

```bash
pip install -r requirements.txt
python -m compileall -q bot hunter storage tests
python -m unittest discover -s tests -v
```

---

## V5: qualified prospects, not just keyword matches

V5 prioritizes actual buying signals over listing technologies. A result is classified as
**CLIENTE_DIRECTO**, **PROYECTO_FREELANCE**, **AGENCIA**, **PROYECTO_POR_VALIDAR**,
**EMPLEO_REMOTO**, or **SIN_INTENCION_CONFIRMADA**.

- The rating is bounded at **0–10**. Words in the search query never raise a lead's score.
- Exact-term matching prevents false positives (e.g. Go inside Google).
- Generic result pages and explicit US-only/onsite restrictions are rejected.
- Dates parse ISO and relative timestamps, excluding posts older than `MAX_AGE_HOURS`.
  Unknown publication dates are **not confirmed fresh**; check the original post.
- Telegram alerts now include source date and a bilingual **draft**, to be checked and
  personalized manually before contacting anyone. No automatic DMs or applications.
- Recent unsent V5 leads are retried if a Telegram request fails, without resetting your
  existing Supabase statuses. No schema migration or new secret is required.
- Notifications target qualified leads, not generic full-time remote job listings.
- Workflow runs `python -m unittest discover -s tests -v` before hunting.

**Important:** V5 improves lead prioritization; it does not validate that a prospect will pay
or guarantee eligibility, pay rates, or client acquisition. The draft must never be sent unreviewed.

### Recommended rollout

Review the Pull Request, merge after CI passes, then use **Actions → Freelance Lead Hunter →
Run workflow** once. Inspect the logs and a few Telegram alerts before relying on the
scheduled search. The Telegram long-polling service does not need a database migration.

---

# Freelance Lead Hunter V5 (Client Acquisition)

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
