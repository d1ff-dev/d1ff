# Contributing to d1ff

Welcome! d1ff is an open-source AI code review tool, and we are glad you are here. All contributions are welcome — whether it is a small prompt tweak, a bug fix, or a new feature.

This document explains the different ways you can contribute and how to get started with each.

---

## Ways to Contribute

There are three main paths, ordered from lowest to highest friction:

1. **[Prompt improvements](#prompt-contributions-easiest)** — edit plain-text template files, no deep codebase knowledge required
2. **[Code contributions](#code-contributions)** — fix bugs, add features, improve performance
3. **[Documentation improvements](#documentation-contributions)** — improve guides, fix typos, add examples

All three are equally valued. The project improves most quickly when all three happen together.

---

## Prompt Contributions (Easiest)

**You do not need to understand the codebase to improve prompts.**

d1ff's review quality comes largely from the prompts it uses. If you have noticed a pattern of false positives, missed issues, or unhelpful comments on a particular kind of code, you can improve that by editing a prompt file.

### How prompts work

Prompt files live in the `prompts/` directory at the project root:

```
prompts/
├── summary.md.j2        # Summarises the PR before review
├── review.md.j2         # The main review pass — finds issues
└── verification.md.j2   # Verifies that findings are genuine (reduces false positives)
```

These are [Jinja2](https://jinja.palletsprojects.com/) templates. They are plain text with `{{ variable }}` placeholders. The loader (`src/d1ff/prompts/loader.py`) reads these files at startup and the registry (`src/d1ff/prompts/registry.py`) makes them available to the review pipeline.

The three pass types:

| Pass | File | Purpose |
|------|------|---------|
| `summary` | `summary.md.j2` | Generates a short PR summary posted as the first comment |
| `review` | `review.md.j2` | Identifies code issues, bugs, and suggestions |
| `verification` | `verification.md.j2` | Re-evaluates findings to filter out false positives before posting |

### How to submit a prompt improvement

1. **Fork and clone** the repository
2. Edit one of the prompt files in `prompts/`
3. **Test your change** using the benchmark runner:
   ```bash
   uv run python benchmark/runner.py
   ```
   This runs your modified prompt against the benchmark dataset and shows how findings change.
4. Open a PR with a description like:
   - "Improved verification pass prompt to reduce false positives for TypeScript generics"
   - "Updated review prompt to catch missing null checks in async functions"
   - "Clarified summary prompt output format for multi-file PRs"

### Example contribution

> "I noticed d1ff was flagging every use of `any` in TypeScript as a high-severity issue, even in legacy migration files. I updated `verification.md.j2` to consider the file path and context before flagging `any` usages, which reduced false positives on my team's codebase by ~60%."

Even small improvements to existing prompts are welcome. You do not need a GitHub account for the benchmark — just fork, edit, and open a PR.

---

## Code Contributions

### Development setup

1. **Fork and clone** the repository:
   ```bash
   git clone https://github.com/your-username/d1ff.git
   cd d1ff
   ```

2. **Install dependencies** using [uv](https://docs.astral.sh/uv/):
   ```bash
   uv sync
   ```

3. **Create a personal dev GitHub App** (see [below](#creating-a-dev-github-app))

4. **Copy the environment template** and fill in the values from your dev App:
   ```bash
   cp .env.example .env
   # Edit .env — see the dev App setup section for which values to use
   ```

5. **Run the development server:**
   ```bash
   uv run fastapi dev src/d1ff/main.py
   ```

6. **Run the frontend dev server** (in a separate terminal):
   ```bash
   cd frontend && npm install && npm run dev
   ```

7. **Run the test suite:**
   ```bash
   uv run pytest
   ```

8. **Run linting:**
   ```bash
   uv run ruff check .
   ```

9. **Run type checking:**
   ```bash
   uv run mypy src/
   ```

### Creating a dev GitHub App

Each developer needs their own GitHub App for local testing. The production App (`d1ff`) cannot be shared for development because GitHub Apps only support a single Webhook URL.

#### Why a separate App?

| Setting | Production App | Dev App |
|---------|---------------|---------|
| Callback URL | `https://app.d1ff.dev/auth/github/callback` | `http://localhost:8000/auth/github/callback` |
| Webhook URL | `https://app.d1ff.dev/webhook/github` | `https://smee.io/YOUR_CHANNEL` |
| Setup URL | `https://app.d1ff.dev/auth/github/callback` | `http://localhost:8000/auth/github/callback` |

The **Callback URL** and **Setup URL** are browser redirects — `localhost` works fine. The **Webhook URL** is a server-to-server POST from GitHub — it cannot reach `localhost` directly, so we use [smee.io](https://smee.io) as a tunnel.

#### Step-by-step

1. **Create a smee channel** — go to https://smee.io and click "Start a new channel". Save the URL (e.g. `https://smee.io/abc123xyz`).

2. **Create a GitHub App** — go to GitHub → Settings → Developer settings → GitHub Apps → New GitHub App:

   | Field | Value |
   |-------|-------|
   | App name | `d1ff-dev-YOURNAME` |
   | Homepage URL | `http://localhost:8000` |
   | Callback URL | `http://localhost:8000/auth/github/callback` |
   | Setup URL (optional) | `http://localhost:8000/auth/github/callback` |
   | Webhook URL | Your smee.io channel URL |
   | Webhook secret | Generate with `python -c "import secrets; print(secrets.token_hex(32))"` |

3. **Set permissions** (Repository permissions):
   - Pull requests: **Read & write**
   - Issues: **Read & write**
   - Metadata: **Read-only** (enabled by default)

4. **Subscribe to events:**
   - Pull request
   - Issue comment

5. **Enable OAuth during installation:**
   - Check "Request user authorization (OAuth) during installation"

6. **After creation**, on the App settings page:
   - Note the **App ID**
   - Generate a **private key** (downloads a `.pem` file)
   - Under "OAuth", note the **Client ID** and generate a **Client secret**

7. **Install the App** on a test repository (Install App tab → select repositories).

8. **Fill in your `.env`:**
   ```bash
   GITHUB_APP_ID=<your dev app id>
   GITHUB_PRIVATE_KEY="<contents of the .pem file>"
   GITHUB_WEBHOOK_SECRET=<the secret you generated>
   GITHUB_CLIENT_ID=<oauth client id>
   GITHUB_CLIENT_SECRET=<oauth client secret>
   ENCRYPTION_KEY=<generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
   SESSION_SECRET_KEY=<any random string>
   DATABASE_URL=sqlite+aiosqlite:///./d1ff-dev.db
   ```

#### Running locally with webhooks

```bash
# Terminal 1: smee proxy (install once: npm install -g smee-client)
smee -u https://smee.io/YOUR_CHANNEL -t http://localhost:8000/webhook/github

# Terminal 2: backend
uv run fastapi dev src/d1ff/main.py

# Terminal 3: frontend
cd frontend && npm run dev
```

Open `http://localhost:5173`, log in with GitHub, then create a PR in your test repository — the webhook will arrive via smee and d1ff will process it.

#### What works without webhooks

If you only need to test the UI (OAuth, settings page, API endpoints), you can skip smee entirely. Just run the backend and frontend — OAuth login works because it is a browser redirect, not a server-to-server call.

### PR checklist

Before opening a pull request, verify:

- [ ] All existing tests pass: `uv run pytest`
- [ ] Type checks pass: `uv run mypy src/`
- [ ] Lint passes: `uv run ruff check .`
- [ ] New functionality has corresponding tests
- [ ] Changes are scoped to what is described in the PR

### Project structure

```
d1ff/
├── src/d1ff/
│   ├── main.py           # FastAPI app entry point
│   ├── webhook/          # GitHub webhook receiver and signature validation
│   ├── context/          # PR context gathering (diff, file contents, imports)
│   ├── pipeline/         # Review pipeline: summary → review → verification
│   ├── comments/         # GitHub comment posting
│   ├── prompts/          # Prompt loader and registry
│   ├── providers/        # LLM provider abstraction (via LiteLLM)
│   ├── storage/          # SQLite persistence layer
│   └── web/              # Web UI (settings, OAuth, feedback)
├── prompts/              # Jinja2 prompt templates (edit these to improve review quality)
├── tests/                # Test suite (mirrors src/d1ff/ structure)
├── benchmark/            # Benchmark runner for evaluating prompt quality
└── docs/                 # Operator and architecture documentation
```

The main data flow is: `webhook → context → pipeline → comments`. Each module is independently testable.

For architecture details, see [docs/self-hosting.md](docs/self-hosting.md#data-flow--security) and the architecture documentation in `_bmad-output/planning-artifacts/architecture.md`.

---

## Documentation Contributions

Documentation lives in two places:

- **`README.md`** (project root) — the landing page; covers what d1ff is, quick start, and links
- **`docs/`** directory — in-depth guides (currently: `self-hosting.md`)

What makes a good documentation contribution:

- Fix a step that was unclear or incorrect
- Add an example that would have helped you when you were setting things up
- Document a common error you encountered and how you solved it
- Improve the troubleshooting sections with real-world cases

To contribute docs, the same fork → edit → PR flow applies. No local setup is required for documentation-only changes.

---

## Good First Issues

Look for the **[good first issue](https://github.com/d1ff-dev/d1ff/labels/good%20first%20issue)** label in the issue tracker.

The easiest first contribution is a **prompt improvement** — it requires no Python knowledge, takes minutes to test, and has direct impact on review quality. If you use d1ff and find a prompt that produces unhelpful output on your codebase, that is an excellent candidate for your first PR.

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you agree to uphold a welcoming and respectful environment for everyone.

If you have concerns, please reach out to the maintainers via GitHub issues.
