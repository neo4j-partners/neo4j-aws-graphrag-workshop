# Grounded AI Agents with Neo4j and AWS Workshop Site

This Antora microsite publishes the source material in `../workshop-content/`.
The build converts the workshop's Markdown and its directives into AsciiDoc, so
the content directory remains the single source of truth.

## Run locally

```bash
cd site
npm ci
npm run build
npm run serve
```

Open http://localhost:8080. The production deployment is handled by
`.github/workflows/deploy-site.yml` whenever `main` changes.
