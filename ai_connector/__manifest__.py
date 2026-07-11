{
    "name": "AI Connector & Assistant",
    "summary": "Multi-provider AI + RAG live chat that answers customers from your product catalog.",
    "description": """
<p>
    <b>AI Connector &amp; Assistant</b> brings the power of modern Large Language Models
    directly inside your Odoo instance. Connect multiple AI providers, build reusable
    prompt templates, run secure chats, and generate content from any screen.
</p>

<h3>Key Features</h3>
<ul>
    <li>Multi-provider support: OpenAI, Anthropic Claude, Google Gemini, Mistral AI and local Ollama.</li>
    <li>Centralised, encrypted API key storage per provider.</li>
    <li>Reusable prompt templates with dynamic {{variables}}.</li>
    <li>Persistent AI conversations with full history.</li>
    <li>Quick "Ask AI" wizard available on almost every form view.</li>
    <li>Token usage tracking for cost control.</li>
    <li>Privacy-friendly: choose what data is sent to the model.</li>
</ul>

<h3>Why choose this module?</h3>
<p>
    One module, every provider. No need to install a separate app for each AI vendor.
    Switch providers instantly from the configuration panel and keep your templates
    and conversations intact.
</p>

<p>Visit <a href="https://www.odoo.com/apps">the Odoo Apps store</a> for support and updates.</p>
""",
    "category": "Productivity",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "author": "Your Company",
    "website": "https://www.example.com",
    "maintainer": "Your Company",
    "price": 99.0,
    "currency": "USD",
    "depends": ["base", "mail", "web", "product", "im_livechat"],
    "data": [
        "security/ai_connector_groups.xml",
        "security/ir.model.access.csv",
        "data/ai_provider_data.xml",
        "data/ai_prompt_template_data.xml",
        "data/ai_livechat_cron.xml",
        "views/res_config_settings_views.xml",
        "views/ai_provider_views.xml",
        "views/ai_prompt_template_views.xml",
        "views/ai_chat_views.xml",
        "views/ai_knowledge_views.xml",
        "views/ai_livechat_views.xml",
        "views/ai_connector_wizard_views.xml",
        "views/menus.xml",
    ],
    "qweb": [
        "static/src/xml/ai_chat_widget.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ai_connector/static/src/js/ai_chat_widget.js",
            "ai_connector/static/src/css/ai_connector.css",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": True,
    "sequence": 20,
}
