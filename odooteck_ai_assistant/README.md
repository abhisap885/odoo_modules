# OdooTeck AI Shopping Assistant (Odoo 19)

A fresh OdooTeck assistant for website shoppers, Odoo Live Chat and Discuss. It does not depend on the Webkul module used as a functional reference.

## What it does

- Shows a website chat widget with conversation history, approved answers, published product suggestions and source links.
- Replies in configured Live Chat and Discuss channels. Typing a handoff keyword requests a human; Live Chat also calls Odoo's operator forwarding method.
- Uses approved knowledge first. In **Knowledge only** mode, missing facts get a safe fallback. **Knowledge and AI** sends the retrieved facts to a configured provider. **General AI** permits broader answers.
- Imports approved knowledge from UTF-8 TXT, CSV or JSON files and lets assistants reuse another assistant's knowledge collection.
- Supports OpenAI, Groq, Gemini and OpenAI compatible or local endpoints. A second provider can take over when the first fails. With no provider configured, matching approved knowledge still works.
- Keeps per-session message history, provider and token usage, optional USD cost estimates, user feedback and a conversation summary that can be downloaded as text.
- Enforces per-session and per-visitor request limits plus daily token/cost budgets. Negative feedback can trigger human follow-up.
- Captures a CRM lead only after the visitor provides a name, valid email and contact consent.
- Redacts email addresses and phone-like strings in assistant replies when enabled.

## Install

1. Place `odooteck_ai_assistant` in an Odoo 19 addons path.
2. Install **OdooTeck AI Shopping Assistant**. Odoo installs `website_sale`, `website_livechat` and `crm` if needed.
3. Give an administrator the **AI Shopping Assistant / Manager** group. Give support staff the **User** group to read conversations.
4. Open **AI Shopping Assistant → Assistants**. The default assistant is active in Knowledge only mode, with one factual getting-started article. Add approved answers under **Knowledge**.
5. Optional: create a provider under **Providers**, enter its API key and exact model ID, then select it on the assistant. For local or OpenAI compatible providers, enter a reachable endpoint. Configure the fallback provider separately.

The website widget appears on pages using `website.layout`. It works without an API key for approved knowledge and published product lookup. No external AI request is made until a provider is configured and the response mode permits it.

## Live Chat and Discuss

In **Live Chat → Channels**, choose an **AI Assistant** on the desired channel. Odoo still needs a configured Live Chat operator to open visitor sessions. The assistant replies to visitor messages; operator messages do not trigger it. A human request stops automated replies for that session.

In **AI Shopping Assistant → Discuss Channels**, create a channel or assign an assistant to an existing channel, then add members in Discuss. The assistant replies to new channel comments. A handoff request stops automatic replies for that conversation.

## Knowledge and products

Create one article per approved answer. Give it a clear title, optional customer question, keywords and an optional public source URL. Matching uses local terms in the title, question, keywords and answer. Published shop products can be suggested from the public catalog. The assistant does not expose unpublished products.

Use **Import knowledge** on an assistant for a `.txt` document or up to 200 CSV/JSON entries. TXT documents are split into 10,000-character parts. CSV/JSON rows require an `answer` and may include `name`, `question`, `keywords`, and `source_url`. The file must be UTF-8 and at most 2 MB. Set **Use knowledge from** on an assistant to reuse another assistant's approved articles without duplicating them.

For controlled answers, keep **Knowledge only** mode. For AI phrasing over retrieved facts, use **Knowledge and AI** and a provider. Adjust the system prompt to fit the store, but keep product pricing and policy facts in approved knowledge or published products.

## Safety and operations

- Provider keys are visible only to AI managers and are stored in Odoo fields. Protect database backups accordingly.
- The public chat uses a random bearer token in browser local storage to reopen only its own conversation. Clear site storage to start a new one.
- The website limits new sessions and requests by a pseudonymous visitor key. It does not store a raw IP address in the assistant models.
- User messages, assistant replies, contact details and provider usage are stored in Odoo. Apply your own retention policy to conversations and CRM leads.
- Remote provider endpoints must use HTTPS and resolve to a public address. HTTP is allowed only for local loopback endpoints.
- Provider outages fall back to a second provider, then to a matching approved answer or the configured fallback text.

## Verification

The module was installed on the live Odoo 19 `demo` database. The website widget rendered on `/shop` without an asset compilation error; `/ot_ai/chat/start`, `/ot_ai/chat/send` and `/ot_ai/chat/feedback` returned expected responses, including a knowledge answer and a human handoff. Transactional smoke tests passed for knowledge import, shared knowledge, rate limits, feedback, lead creation, Discuss replies and Live Chat replies. A live website request also received a Groq response through the configured `openai/gpt-oss-20b` model, and Odoo recorded its token usage. API credentials remain in Odoo's provider record and are not part of this module or its screenshots.
