# petrochemicals.jacksonsobservatory.com

Win95-style OSINT desktop for the Dow corporate-family tracker: interactive map, facility dossiers,
filters with link-confidence tiers, and an AI analyst (Cloudflare Workers AI) that can cite sources,
highlight the map, show aerial images, link records and create CSV files.

```
public/            static site + data (served by Cloudflare, no server)
  index.html app.js style.css render.js
  data/*.json      exported from DuckDB by scripts/export_data.py
src/               the Worker (only /api/* runs it)
  worker.js        routes, validation, rate limit, same-origin check
  agent.js         tool-calling loop + system prompt
  tools.js         find_facilities, aggregate, facility_detail, search_documents,
                   show_on_map, show_satellite, export_csv
  llm.js           Workers AI client with model fallback
  search.js        BM25 keyword search      verify.js  answer checks
test/              28 tests (npm test)
```

## Deploy (no command line needed)

1. Put this repo on GitHub (the `web/` folder must be in it) and push.
2. Cloudflare dashboard > **Workers & Pages** > **Create** > **Import a repository** > pick the repo.
3. Set **Root directory** to `web`. Leave Build command empty. Deploy command: `npx wrangler deploy`.
4. Deploy. `wrangler.toml` already declares the Workers AI binding and the custom domain
   `petrochemicals.jacksonsobservatory.com`, so there is nothing else to configure.
5. Open the site, then open `/api/health`. It should say `"ok":true` and `"facilities":292`.

Command-line alternative: `cd web && npm install && npx wrangler login && npx wrangler deploy`.
The repo also has `.github/workflows/deploy-web.yml` (optional): add repo secrets
`CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` and every push to `main` that touches `web/` deploys.

## Protect the AI endpoint (do this once, 2 minutes)

Workers AI bills per use, and `/api/chat` is public. The Worker already limits message size,
history, tool steps, cross-origin calls and does a soft per-instance rate limit. For a hard limit:
Cloudflare > the zone > **Security > WAF > Rate limiting rules** > new rule:
`http.host eq "petrochemicals.jacksonsobservatory.com" and http.request.uri.path eq "/api/chat"`,
20 requests per minute per IP, action Block. Check Workers AI usage in the dashboard after launch.

## Refresh the data

```
pip install duckdb zipcodes
python web/scripts/export_data.py --db notebooks/dow-edgar-echo-demo/out/dow.duckdb
git add web/public/data && git commit -m "Refresh data" && git push
```

## Change the AI model

Edit `CHAT_MODELS` in `wrangler.toml` (comma-separated; first that answers wins; the rest are fallbacks).
Browse models at https://developers.cloudflare.com/workers-ai/models/. The tool protocol is plain text,
so any chat model works, but stronger models follow it better. The active model shows in the terminal title bar.

## Local testing

`npm test` runs everything with a fake AI (no network). `npm run dev` runs the Worker against the real
Workers AI (needs `wrangler login`). Optional: `npm i --no-save jsdom` enables the in-browser page tests.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Deploy fails: hostname already has DNS records | Delete the existing `petrochemicals` DNS record in the zone, redeploy. |
| Deploy fails on the domain | `jacksonsobservatory.com` must be a zone on the same Cloudflare account. |
| Terminal says "AI service is unavailable" | Open `/api/chat` errors in Workers > Logs. The message lists which models failed. Try another model in `CHAT_MODELS`. |
| Answers show raw `<tool>` text or "unverified" warnings often | The model is not following the tool protocol. Put a stronger model first in `CHAT_MODELS`. |
| Map is blank but list works | Basemap tiles or the MapLibre CDN are blocked by the visitor's network or an extension. |
| Aerial image says "failed to load" | The Esri imagery service is rate-limited or down; it is a convenience, not required. |
