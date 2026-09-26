/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

const root = document.getElementById("ot-ai-chat");
if (root) {
    const panel = root.querySelector(".ot-ai-panel");
    const messages = root.querySelector(".ot-ai-messages");
    const error = root.querySelector(".ot-ai-error");
    const form = root.querySelector(".ot-ai-form");
    const input = form.querySelector("input[name=message]");
    const lead = root.querySelector(".ot-ai-lead");
    let token = localStorage.getItem("ot_ai_chat_token") || "";
    let busy = false;

    function addMessage(role, body, id, feedback, sources = []) {
        const item = document.createElement("div");
        item.className = `ot-ai-message ot-ai-${role}`;
        const text = document.createElement("p");
        text.textContent = body;
        item.append(text);
        for (const source of sources) {
            const link = document.createElement("a");
            link.href = source.url;
            link.textContent = source.label;
            link.rel = "noopener noreferrer";
            if (source.url.startsWith("http")) link.target = "_blank";
            item.append(link);
        }
        if (role === "assistant" && id && !feedback) {
            const controls = document.createElement("div");
            controls.className = "ot-ai-feedback";
            for (const [value, label] of [["positive", "Helpful"], ["negative", "Not helpful"]]) {
                const button = document.createElement("button");
                button.type = "button";
                button.textContent = label;
                button.addEventListener("click", async () => {
                    const result = await rpc("/ot_ai/chat/feedback", {token, message_id: id, value});
                    if (result.ok) controls.remove();
                    if (result.handoff) lead.hidden = false;
                });
                controls.append(button);
            }
            item.append(controls);
        }
        messages.append(item);
        messages.scrollTop = messages.scrollHeight;
    }

    async function start() {
        try {
            const data = await rpc("/ot_ai/chat/start", {token});
            if (!data.enabled) return;
            token = data.token;
            localStorage.setItem("ot_ai_chat_token", token);
            root.querySelector(".ot-ai-title").textContent = data.bot_name;
            for (const item of data.messages) addMessage(item.role, item.body, item.id, item.feedback);
            if (!data.messages.length) addMessage("assistant", data.welcome);
            lead.hidden = !data.handoff;
            root.hidden = false;
        } catch (_err) {
            root.hidden = true;
        }
    }

    async function send(message) {
        if (busy || !message.trim()) return;
        busy = true;
        error.textContent = "";
        addMessage("user", message);
        try {
            const result = await rpc("/ot_ai/chat/send", {token, message});
            if (result.error) error.textContent = result.error;
            else {
                addMessage("assistant", result.answer, result.message_id, false, result.sources);
                if (result.handoff) lead.hidden = false;
            }
        } catch (_err) {
            error.textContent = "Message could not be sent. Please try again.";
        } finally {
            busy = false;
            input.focus();
        }
    }

    root.querySelector(".ot-ai-launcher").addEventListener("click", () => { panel.hidden = false; input.focus(); });
    root.querySelector(".ot-ai-close").addEventListener("click", () => { panel.hidden = true; });
    root.querySelector(".ot-ai-human").addEventListener("click", () => send("human"));
    form.addEventListener("submit", event => {
        event.preventDefault();
        const value = input.value;
        input.value = "";
        send(value);
    });
    root.querySelector(".ot-ai-lead-send").addEventListener("click", async () => {
        const result = await rpc("/ot_ai/chat/lead", {
            token,
            name: lead.querySelector("input[name=name]").value,
            email: lead.querySelector("input[name=email]").value,
            consent: lead.querySelector("input[name=consent]").checked,
        });
        if (result.ok) {
            lead.textContent = "Thanks. Our team will follow up.";
        } else {
            error.textContent = result.error;
        }
    });
    start();
}
