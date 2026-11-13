# Ask the Portfolio – optional AI endpoint

The website's **Ask the Portfolio** agent works without this endpoint: it answers from
`data/agent.json` and `data/knowledge.json` (built from the resume and the case studies)
inside the visitor's browser, with voice input and spoken answers. No keys are needed.

Deploy this Cloudflare Worker only if you want free-form AI answers. GitHub Pages is
static, so the AI key must live here, never in the site.

## What is required

1. A Cloudflare account (free plan is enough) and `npm i -g wrangler`, then `wrangler login`.
2. An Anthropic API key (console.anthropic.com) with billing enabled.
3. A Claude model id for `MODEL` (see docs.anthropic.com/en/docs/about-claude/models).

```bash
cd serverless/ask-portfolio
wrangler secret put ANTHROPIC_API_KEY      # paste the key when prompted
# set MODEL in wrangler.toml [vars] (or: wrangler secret put MODEL)
wrangler deploy                            # prints https://ask-portfolio.<you>.workers.dev
```

4. Put that URL in `site/config.json` → `"agent_endpoint": "https://ask-portfolio.<you>.workers.dev"`
   and push. The agent then labels answers "AI answer · grounded in portfolio content" and falls
   back to the built-in answers if the endpoint fails.

## Safety

- Only `ALLOWED_ORIGIN` may call it (CORS + origin check); questions are capped at 300 characters.
- The worker fetches grounding data from the live site itself; the browser cannot inject context.
- The system prompt forbids invented employers, metrics, salary or certifications and keeps
  employer results and portfolio-lab results separate.
- Consider a Cloudflare rate-limiting rule on the route to cap cost.
