# AI Connector & Assistant

A single, vendor-neutral Odoo 19 module that integrates the leading Large Language
Models directly inside Odoo: **OpenAI, Anthropic Claude, Google Gemini, Mistral AI**
and **local Ollama**.

> Odoo App Store listing: one module, every provider. No separate app per vendor.

---

## Features

- **Multi-provider support** — OpenAI, Anthropic, Gemini, Mistral, Ollama.
- **Encrypted API keys** — keys are encrypted at rest (Fernet when `cryptography`
  is installed, base64 obfuscation otherwise).
- **Prompt templates** — reusable templates with `{{variables}}`.
- **Persistent chats** — full conversation history + token tracking.
- **Quick "Ask AI" wizard** — launchable from anywhere in the UI.
- **AI Assistant panel** — a chat widget accessible from the menu.
- **RAG over your products** — index product data into embeddings and answer
  customer questions with retrieved, sourced context.
- **AI Live Chat auto-reply** — hook the website live chat so the AI answers
  visitors using your product knowledge base (better than a fixed scripted bot).
- **Multi-company** ready (each company can have its own providers).
- **Privacy-friendly** — you control exactly what data is sent to the model.

## Supported Odoo versions

- Odoo 19.0 (this branch) and forward-compatible design.

## Dependencies

- Standard Odoo 19 `base`, `mail`, `web`.
- `requests` (bundled with Odoo).
- *(Optional)* `cryptography` for strong key encryption (graceful fallback otherwise).

## Installation

1. Place this folder (`ai_connector`) inside your Odoo `addons` path.
2. Update the app list (`-u base` or via Apps > Update Apps List).
3. Install **AI Connector & Assistant**.

## Configuration

1. Go to **AI Connector ▸ Configuration ▸ Providers** and create a provider.
2. Choose the provider type, enter the model (e.g. `gpt-4o-mini`,
   `claude-3-5-sonnet-latest`, `gemini-1.5-flash`, `mistral-large-latest`, `llama3.1`).
3. Paste your API key (stored encrypted). Click **Test Connection**.
4. *(Recommended)* Set `ai_connector.secret` system parameter to a strong random
   value (`python -c "from ai_connector.utils import encryption; print(encryption.generate_secret())"`).
5. Set the **Default AI Provider** under **Settings ▸ AI Connector**.
6. Open **AI Assistant** from the menu to start chatting.

> For Ollama, set the **Base URL** to your Ollama host (default `http://localhost:11434`)
> and no API key is required.

## Usage

- **AI Assistant** (menu): persistent chat with history.
- **Ask AI** (menu): one-shot wizard — pick a template, ask a question, get a reply.
- **Prompt Templates** (Configuration): build reusable, variable-driven prompts.

## AI Live Chat (RAG)

Turn the Odoo website live chat into an AI shopping assistant:

1. Go to **Website ▸ Configuration ▸ Live Chat** (or **Settings ▸ Live Chat**)
   and open a channel.
2. Enable **AI Auto-Reply** and pick an **AI Provider** (chat model).
3. Keep **Use Product Knowledge (RAG)** on; choose how many chunks to retrieve
   (**Retrieved Chunks**) and tune the **System Prompt**.
4. Index your catalog: open **AI Connector ▸ Configuration ▸ Product Knowledge
   (RAG) ▸ Index All Products**, or use the per-product **AI: Index** button.
   A weekly cron keeps embeddings fresh.
5. When a visitor messages the live chat, the AI retrieves the most relevant
   product chunks (cosine similarity) and answers with citations. If nothing
   matches, it can fall back to a general answer (toggle **Allow General Answers**).

This beats a fixed scripted chatbot: answers are grounded in *your* real product
data, support multiple LLM vendors, include source citations, and track token
usage.

### How RAG works

- Each product is serialized (name, category, price, attributes, description, tags)
  and split into overlapping text chunks.
- An embedding model (e.g. `text-embedding-3-small`) turns each chunk into a vector.
- A visitor question is embedded and matched (cosine similarity) against all chunks;
   the top-K chunks are injected as context into the LLM prompt.

## Security & Privacy

- API keys are never shown back in plaintext in the UI (`password=True` + encryption).
- Only the data you explicitly include in a prompt/question is transmitted to the
  configured provider. Review each provider's data policy before use.
- Token usage is tracked on each provider for cost control.

## License & Pricing

This module is distributed under the **Odoo Proprietary License (OPL-1)**.

| Plan            | Price (USD) | Notes                                   |
|-----------------|-------------|-----------------------------------------|
| Single app      | $99         | One-time license, 1 production database |
| 5-database pack | $399        | 5 production databases                  |
| Unlimited       | $999        | Unlimited production databases + support|

The price shown on the Odoo App Store is **$99 USD** (one-time). The store handles
billing; the `price` field in `__manifest__.py` documents the list price for your
own deployments / re-publishing.

## Support

Open an issue in the repository or use the **Author** contact link on the Odoo App
Store page.

---

© Your Company. All rights reserved.
