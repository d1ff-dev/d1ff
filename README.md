# d1ff — State-of-the-art AI code review. Open source.

The only code review tool that saves money for **you**, not for itself.

d1ff uses smart model routing: frontier models for complex logic, lightweight models for simple changes. You pay only for the tokens used — no per-seat fees, no markup. The result: review quality on par with the best commercial tools at a fraction of the cost.

[![CI](https://github.com/d1ff-dev/d1ff/actions/workflows/ci.yml/badge.svg)](https://github.com/d1ff-dev/d1ff/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

> **Demo GIF coming soon — see [releases](https://github.com/d1ff-dev/d1ff/releases) for preview screenshots**
>
> ![demo](docs/demo.gif)

---

## Why d1ff?

### State-of-the-art review quality

d1ff doesn't cut corners. Every PR goes through a **3-pass pipeline** — Architecture, Logic, Style — using the same frontier models (GPT-5.4, Claude Opus 4.6, Gemini 3.1 Pro) that power the most expensive commercial tools.

### Smart Model Routing

Not every diff needs a $0.10 frontier-model call. d1ff analyzes each change and automatically picks the right model:

| Change complexity | Model tier | Cost per review |
|-------------------|------------|-----------------|
| Simple (typos, formatting, renames) | `gpt-5.4-nano`, `gemini-3.1-flash-lite` | ~$0.002 |
| Medium (new functions, refactors) | `gpt-5.4-mini`, `claude-sonnet-4-6` | ~$0.01 |
| Complex (architecture, security) | `gpt-5.4`, `claude-opus-4-6` | ~$0.05 |

Average cost across a typical team: **~$0.02 per review**.

### Open source. Full control.

- **MIT licensed** — fork it, modify it, deploy it commercially
- **Self-hosted** — your code never leaves your infrastructure
- **BYOK (Bring Your Own Key)** — use your own API keys, no middleman
- **No vendor lock-in** — swap providers anytime, no data held hostage

### We save money for you, not for ourselves

Traditional SaaS code review tools charge **per seat** — they profit when your team grows, regardless of how much you actually use the tool. d1ff flips the model: you pay only for the LLM tokens consumed. We have zero incentive to waste your tokens.

| Team Size | CodeRabbit Pro (6 mo) | d1ff BYOK (6 mo, ~200 PRs/mo) | 6-Month Savings |
|-----------|----------------------|-------------------------------|-----------------|
| 5 devs    | $900                 | ~$24 in tokens                | **~$876**       |
| 10 devs   | $1,800               | ~$48 in tokens                | **~$1,752**     |
| 20 devs   | $3,600               | ~$96 in tokens                | **~$3,504**     |

> CodeRabbit Pro: $30/dev/mo. d1ff estimate based on ~$0.02/review with smart model routing. Actual cost depends on PR size and complexity.

---

## Quickstart (2 minutes)

### Hosted (GitHub App)

1. [Sign up at app.d1ff.dev](https://app.d1ff.dev) with your GitHub account
2. Add your LLM API key in the d1ff dashboard
3. Open a pull request — d1ff will post a review automatically

### Self-Hosted (Docker)

```bash
cp .env.example .env
# Fill in your values in .env
docker run -d \
  --env-file .env \
  -p 8000:8000 \
  ghcr.io/d1ff-dev/d1ff:latest
```

See [docs/self-hosting.md](docs/self-hosting.md) for full configuration options.

---

## Features

- **3-Pass Review** — Architecture → Logic → Style, each pass focused and noise-free
- **Smart Model Routing** — Frontier models for hard problems, fast models for simple ones
- **Suggestion Blocks** — Inline code suggestions you can apply with one click
- **Slash Commands** — `/review`, `/explain`, `/suggest` directly in PR comments
- **BYOK** — Use your own OpenAI, Anthropic, Google, or DeepSeek API key
- **Self-Hosted** — Full control: your data stays in your infrastructure

---

## Supported LLM Providers

| Provider   | Example Models                                    |
|------------|---------------------------------------------------|
| OpenAI     | `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.4-nano`        |
| Anthropic  | `claude-opus-4-6`, `claude-sonnet-4-6`             |
| Google     | `gemini-3.1-pro`, `gemini-3.1-flash-lite`          |
| DeepSeek   | `deepseek-v3`, `deepseek-r1`                       |
| Custom     | Any OpenAI-compatible endpoint via `LLM_API_BASE`  |

---

## Self-Hosting

Full self-hosting guide: [docs/self-hosting.md](docs/self-hosting.md)

---

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

[MIT](LICENSE) — free to use, fork, and deploy commercially.
