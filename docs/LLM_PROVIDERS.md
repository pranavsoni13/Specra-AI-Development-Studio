# Specra LLM providers

Specra supports three LLM provider modes through the existing shared client. No provider is enabled by changing source code; configure the backend environment.

## Supported providers

| `LLM_PROVIDER` | Required key | API endpoint | Default model |
|---|---|---|---|
| `ollama` (default) | None for local Ollama; `OLLAMA_API_KEY` may be required for a hosted endpoint | `OLLAMA_HOST`, or local Ollama default | Qwen 3 local models |
| `xai` | `XAI_API_KEY` | `https://api.x.ai/v1` by default | `grok-4.7` |
| `openrouter` | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` | `x-ai/grok-4.7` |

OpenRouter model identifiers use the provider/model format, for example `x-ai/grok-4.7`. xAI direct API models use xAI's model name, for example `grok-4.7`. Confirm model availability and pricing in the provider dashboard before running production workloads.

## Select a provider

Local development can omit `LLM_PROVIDER`; the default remains Ollama:

```dotenv
LLM_PROVIDER=ollama
```

To use Grok directly through xAI:

```dotenv
LLM_PROVIDER=xai
XAI_API_KEY=replace-with-a-server-side-key
XAI_MODEL=grok-4.7
```

To use Grok through OpenRouter:

```dotenv
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=replace-with-a-server-side-key
OPENROUTER_MODEL=x-ai/grok-4.7
OPENROUTER_APP_NAME=Specra
# Optional: set this to the deployed app URL for OpenRouter attribution.
OPENROUTER_SITE_URL=https://specra-ai-development-studio.vercel.app
```

Do not commit keys or place them in Vite/frontend environment variables. Add keys only to the backend's local `.env` (ignored by Git) or the backend hosting provider's secret environment settings.

### Per-agent model selection

The shared provider can be selected once, while each agent can still be assigned a specific model through:

- `REQUIREMENT_ANALYST_MODEL`
- `PROJECT_PLANNER_MODEL`
- `SOFTWARE_ARCHITECT_MODEL`
- `TECHNICAL_REVIEWER_MODEL`

When using xAI or OpenRouter, ensure any per-agent model overrides use identifiers supported by the selected provider. Otherwise, the default models above are selected for the configured provider.

## Output validation

The existing agents rely on Pydantic schemas. The remote adapters request JSON-object output, include the target schema in the prompt, and validate the result locally with the same Pydantic model used by Ollama. Invalid results raise an error instead of being passed to an agent as trusted structured data. Model support and adherence still need to be measured with Specra's regression set.

## Selection recommendation

Keep local Ollama as the development default and evaluate Grok/OpenRouter against representative project briefs before switching the hosted service. Record output quality, structured-output pass rate, latency, token usage, and approximate cost. Hosted API usage may incur fees; access to Grok in the consumer chat product is separate from API credentials and billing.
