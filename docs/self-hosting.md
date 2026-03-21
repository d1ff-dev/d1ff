# Self-Hosting d1ff

d1ff is a self-hosted GitHub App that performs automated AI-powered code reviews on pull requests. This guide covers everything you need to deploy d1ff on your own infrastructure.

**What you will set up:**
- A GitHub App installed on your repositories
- A running d1ff container with persistent storage
- Connection to your preferred LLM provider (OpenAI, Anthropic, Google Gemini, DeepSeek, or custom endpoint)

---

## Prerequisites

Before you begin, ensure you have:

- **Docker** installed and running ([get Docker](https://docs.docker.com/get-docker/))
- **A GitHub account** with rights to create GitHub Apps (Settings → Developer settings → GitHub Apps)
- **An account with an LLM provider** — you will need an API key from one of: OpenAI, Anthropic, Google AI Studio, or DeepSeek. Azure OpenAI and self-hosted models via custom endpoints are also supported.
- **A publicly accessible HTTPS URL** for your d1ff instance (GitHub must be able to deliver webhooks to it). Tools like [ngrok](https://ngrok.com/) work for local testing.

---

## Step 1: Create a GitHub App

GitHub Apps are the secure way to grant d1ff access to your repositories without using a personal token.

1. Go to **GitHub → Settings → Developer settings → GitHub Apps → New GitHub App**

2. Fill in the registration form:

   | Field | Value |
   |-------|-------|
   | **GitHub App name** | `d1ff` (or any name you prefer) |
   | **Homepage URL** | Your instance URL, e.g. `https://your-domain.com` |
   | **Webhook URL** | `https://your-domain.com/webhook/github` |
   | **Webhook secret** | Generate one (see command below) |

3. **Generate a webhook secret** — run this command and copy the output:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   Save this value — you will set it as `GITHUB_WEBHOOK_SECRET` in your environment.

4. **Set permissions** (under "Repository permissions"):
   - Pull requests: **Read & write**
   - Issues: **Read & write**
   - Metadata: **Read-only** (required, enabled by default)

5. **Subscribe to events** (under "Subscribe to events"):
   - Pull request
   - Issue comment

6. **Where can this GitHub App be installed?** — select "Only on this account" for a private deployment, or "Any account" if you want others to install it.

7. Click **Create GitHub App**.

8. On the app's settings page:
   - Note your **App ID** (you will set it as `GITHUB_APP_ID`)
   - Under "Private keys", click **Generate a private key** — a `.pem` file will download. Keep it safe.
   - Under "OAuth app", note your **Client ID** and generate a **Client secret** (for web UI login).

9. **Install the App** on the repositories you want reviewed: go to the App's "Install App" tab and select your repositories.

---

## Step 2: Configure Environment Variables

Create a `.env` file in your working directory. Start from the template:

```bash
cp .env.example .env
```

Then fill in the required values:

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GITHUB_APP_ID` | Your GitHub App's numeric ID | `123456` |
| `GITHUB_PRIVATE_KEY` | Contents of the `.pem` key file (newlines as `\n` literals in env files) | `"-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"` |
| `GITHUB_WEBHOOK_SECRET` | The webhook secret you generated in Step 1 | `a3f8c2...` |
| `GITHUB_CLIENT_ID` | OAuth client ID from your GitHub App | `Iv1.abc123` |
| `GITHUB_CLIENT_SECRET` | OAuth client secret from your GitHub App | `your-oauth-client-secret` |
| `ENCRYPTION_KEY` | Fernet key for encrypting stored API keys | see generation command below |
| `SESSION_SECRET` | Secret for web UI session cookies | any long random string |

Generate the `ENCRYPTION_KEY`:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | Default LLM provider: `openai`, `anthropic`, `gemini`, `deepseek` |
| `LLM_MODEL` | `gpt-4o` | Default model name |
| `LLM_API_KEY` | — | LLM provider API key (can also be set per-installation in the web UI) |
| `LLM_API_BASE` | provider default | Override API base URL (for Azure OpenAI or custom endpoints) |
| `LITELLM_DEFAULT_MODEL` | `gpt-4o-mini` | Default model passed to LiteLLM |
| `LITELLM_FALLBACK_MODEL` | — | Optional fallback model |
| `MAX_CONCURRENT_REVIEWS` | `5` | Maximum simultaneous review pipelines |
| `RATE_LIMIT_RPM` | `60` | Requests per minute limit |
| `DATABASE_URL` | `sqlite+aiosqlite:////data/d1ff.db` | SQLite path (replace with PostgreSQL URL for production) |
| `LOG_LEVEL` | `INFO` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |

See `.env.example` at the project root for a complete annotated reference.

> **PEM key formatting note:** When using `--env-file .env`, the private key must have literal `\n` characters instead of real newlines. To convert your downloaded `.pem` file:
> ```bash
> awk 'NF {printf "%s\\n", $0}' your-app.pem
> ```

---

## Step 3: Deploy with Docker

### Option A: Quick start with `docker run`

```bash
docker run -d \
  -v d1ff-data:/data \
  -p 8000:8000 \
  --env-file .env \
  --name d1ff \
  ghcr.io/d1ff-dev/d1ff:latest
```

This mounts a named volume `d1ff-data` to `/data` inside the container, where the SQLite database is stored.

### Option B: Production deployment with `docker-compose.yml`

Create a `docker-compose.yml` file:

```yaml
version: "3.9"
services:
  d1ff:
    image: ghcr.io/d1ff-dev/d1ff:latest
    ports:
      - "8000:8000"
    volumes:
      - d1ff-data:/data
    env_file:
      - .env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  d1ff-data:
```

Then start it:

```bash
docker compose up -d
```

View logs:

```bash
docker compose logs -f d1ff
```

---

## Step 4: Configure LLM Provider

After deploying, configure your LLM provider through the web UI:

1. Open `http://your-domain.com/settings` in your browser
2. Log in with your GitHub account (OAuth through the GitHub App you created)
3. Enter your LLM provider API key
4. Select your provider and model

### Supported Providers

| Provider | Example model | Notes |
|----------|--------------|-------|
| OpenAI | `gpt-4o`, `gpt-4-turbo` | Standard OpenAI API |
| Anthropic | `claude-3-5-sonnet-20241022` | Anthropic API |
| Google Gemini | `gemini-1.5-pro` | Google AI Studio API |
| DeepSeek | `deepseek-coder` | DeepSeek API |

### Custom Endpoint / Azure OpenAI

For Azure OpenAI or self-hosted models, set `LLM_API_BASE` in your `.env` to override the provider's default endpoint:

```env
LLM_API_BASE=https://your-resource.openai.azure.com/
LLM_MODEL=your-deployment-name
LLM_PROVIDER=openai
```

All provider communication goes through LiteLLM, which handles provider-specific authentication automatically.

---

## Verifying Your Deployment

### Health check endpoint

```bash
curl http://your-domain.com/health
```

Expected response (HTTP 200):

```json
{
  "status": "ok",
  "subsystems": {
    "database": "ok",
    "github_app": "ok"
  }
}
```

**Subsystem meanings:**

| Subsystem | Meaning if `"ok"` |
|-----------|-------------------|
| `database` | SQLite file at `/data/d1ff.db` is readable and writable |
| `github_app` | GitHub App credentials (App ID + private key) are valid and the App can be authenticated |

If a subsystem shows `"error"`, check the container logs:

```bash
docker logs d1ff
```

---

## Data Flow & Security

This section describes exactly what data d1ff persists, processes in memory, and sends externally. This is intended for enterprise security review teams evaluating d1ff for deployment in sensitive environments.

### What is persisted

d1ff stores data in SQLite at `/data/d1ff.db` (the path defined by `DATABASE_URL`). The following data is written to disk:

| Data | Storage format |
|------|---------------|
| GitHub Installation ID + metadata | Plain text |
| LLM provider API keys | AES-128 encrypted with Fernet (symmetric encryption); the `ENCRYPTION_KEY` env var is the master key and never leaves the server |
| User configuration (provider, model selection) | Plain text |
| Feedback reactions (thumbs up/down on review comments) | Plain text |

**Source code is never stored.** PR diffs and file contents are processed entirely in memory and garbage-collected after each review pipeline completes (NFR10).

### What is NOT persisted

| Data | Where it lives | Lifetime |
|------|---------------|---------|
| PR diffs and file contents | In-memory only | Duration of review pipeline; GC'd immediately after |
| GitHub API responses | In-memory cache per request lifecycle | Single request, no cross-request caching |
| LLM prompt inputs | Not stored anywhere | Discarded after sending to provider |
| LLM completion outputs | Not stored anywhere | Written to GitHub comments; not stored in d1ff |

### What is sent to your LLM provider

d1ff sends only the following to the LLM provider you configured:

- PR diff (changed lines)
- Full content of the changed files
- Content of import-resolved related files (up to the configured context limit)
- Prompt templates (loaded from the `prompts/` directory)

**Nothing else is sent to the LLM provider.** Specifically, the following are never sent:

- GitHub App JWT tokens or installation access tokens
- Your `ENCRYPTION_KEY` or any other secrets
- User account data or GitHub profile information
- Historical review data or previously processed code

### What stays internal

| Item | Where it stays |
|------|---------------|
| GitHub App JWT tokens | Generated in-memory for each GitHub API call; never leave the server |
| Installation access tokens | Used only for GitHub API calls; never forwarded to any third party |
| `ENCRYPTION_KEY` | Loaded into memory at startup; used to decrypt API keys on demand; never written to disk or transmitted |

### TLS guarantee

All outbound HTTP calls (to GitHub APIs and LLM providers) use TLS 1.2 or higher (NFR8). This is enforced by the underlying HTTP client libraries (httpx for GitHub, LiteLLM for LLM providers). No plain-text HTTP is used for external communication.

---

## Updating d1ff

Pull the latest image and restart the container. Your data volume is preserved.

### With `docker run`:

```bash
docker pull ghcr.io/d1ff-dev/d1ff:latest
docker stop d1ff && docker rm d1ff
docker run -d \
  -v d1ff-data:/data \
  -p 8000:8000 \
  --env-file .env \
  --name d1ff \
  ghcr.io/d1ff-dev/d1ff:latest
```

### With `docker compose`:

```bash
docker compose pull
docker compose up -d
```

The named volume `d1ff-data` persists across container replacements.

---

## Troubleshooting

### Webhooks are not being received

- Verify the Webhook URL in your GitHub App settings is exactly `https://your-domain.com/webhook/github` (no trailing slash)
- Check that d1ff is publicly accessible from GitHub's IP ranges: [GitHub's IP meta endpoint](https://api.github.com/meta)
- Confirm the `GITHUB_WEBHOOK_SECRET` in your `.env` matches the secret set in the GitHub App settings

### d1ff does not post review comments

- Check that the GitHub App has **Pull requests: Read & write** permission
- Confirm the App is installed on the repository receiving the PR
- Look for errors in `docker logs d1ff` — GitHub API errors are logged at ERROR level

### LLM API key errors

- If you see `AuthenticationError` in logs, verify your `LLM_API_KEY` is correct and not expired
- If you configured the API key via the web UI (`/settings`), ensure the correct provider is also selected
- For Azure OpenAI, verify `LLM_API_BASE` includes the resource URL (e.g., `https://your-resource.openai.azure.com/`)

### Health check failures

- `database: "error"` — the `/data` volume may not be writable; check Docker volume mount permissions
- `github_app: "error"` — the `GITHUB_APP_ID` or `GITHUB_PRIVATE_KEY` is incorrect; check `.env` formatting (PEM newlines must be `\n` literals)

### Container exits immediately

Run in foreground to see the startup error:

```bash
docker run --rm -v d1ff-data:/data -p 8000:8000 --env-file .env ghcr.io/d1ff-dev/d1ff:latest
```

Missing required environment variables will cause a `ValidationError` at startup with a clear message listing which variables are missing.
