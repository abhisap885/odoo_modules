# 🚆 Agentic AI Autonomous Train Ticket Booking for Odoo 19

[![Odoo Version](https://img.shields.io/badge/Odoo-19.0-blue.svg)](https://www.odoo.com)
[![License](https://img.shields.io/badge/License-LGPL--3-green.svg)](https://www.gnu.org/licenses/lgpl-3.0.html)
[![AI Providers](https://img.shields.io/badge/Providers-OpenAI%20%7C%20Gemini%20%7C%20Claude%20%7C%20Ollama%20%7C%20Local-orange.svg)]()

An end-to-end **Agentic AI** module for Odoo 19 that replaces manual reservation workflows with an autonomous reasoning and action loop. Instead of simply generating chat text, the AI Agent acts autonomously: it queries live train schedules, checks quota seat availability, reserves tickets, allocates coaches and berths, and confirms bookings directly inside Odoo!

---

## 🌟 What is Agentic AI in this Module?

Traditional AI assistants only generate natural language responses without executing actions in the ERP. 
In contrast, **Agentic AI** combines:
1. **Perception & Goal Understanding**: Interprets complex, ambiguous human instructions (*"Book a 2AC ticket from New Delhi to Mumbai tomorrow for Amit Sharma, 34 M"*).
2. **Autonomous Decomposition**: Breaks the high-level goal into a sequence of tool calls.
3. **Execution Loop (ReAct)**:
   - **Thought**: Formulates rationale and selects the next tool.
   - **Tool Call**: Executes real Odoo ORM methods with structured parameters.
   - **Observation**: Inspects the returned database data (seats remaining, fares, train delays).
   - **Iterative Refinement**: Adapts if an option is unavailable or needs confirmation.
4. **Final Fulfillment**: Creates permanent records in Odoo (`train.booking`, `train.booking.passenger`), decrements inventory quotas, issues a PNR, and reports the complete itinerary to the user.

---

## 🛠️ Registered Agent Tools

The module registers 6 core tools with JSON Schema validation that the AI Agent can invoke dynamically:

| Tool Identifier | Purpose | Inputs |
| :--- | :--- | :--- |
| `search_trains` | Finds direct trains between origin and destination stations | `origin`, `destination`, `date` |
| `check_seat_availability` | Queries live remaining seats and class fares | `train_number`, `travel_class`, `date` |
| `book_train_ticket` | Creates reservation and passenger records in Odoo | `train_number`, `travel_class`, `journey_date`, `passengers` |
| `confirm_ticket` | Finalizes booking, allocates coaches & berths (e.g. B1-24 Lower) | `pnr` or `booking_id` |
| `get_pnr_status` | Retrieves real-time status and passenger details | `pnr` |
| `cancel_ticket` | Cancels booking and restores seats back to quota | `pnr`, `reason` |

---

## 🚀 Key Features

* **Multi-Provider AI Support**:
  - **Deterministic Local Engine (Default)**: Ready-to-run out of the box with zero external dependencies or API keys required.
  - **OpenAI**: GPT-4o, GPT-4o-mini with native function calling.
  - **Google Gemini**: Gemini 1.5 Pro / Flash.
  - **Anthropic Claude**: Claude 3.5 Sonnet.
  - **Local Ollama**: Run private offline models (e.g. `llama3.1`, `mistral`).
* **Autonomy Levels**:
  - **Fully Autonomous**: The agent searches, checks seats, reserves, allocates berths, and confirms the ticket automatically.
  - **Supervised (Human-in-the-Loop)**: The agent creates the reservation in Draft state and awaits human approval before confirming.
* **Train Management**:
  - Master catalogs for Stations, Trains, Routes, Running Days, and Class Fare Rules (1A, 2A, 3A, CC, EC, SL).
  - Pre-seeded with iconic Indian Railway routes (New Delhi, Mumbai Central, Howrah, Bengaluru, Varanasi, Chennai, etc.).
* **Passenger & Seat Allocation**:
  - Automatic coach assignment (e.g. H1, A1, B2, C1, S3) and berth assignment (Lower, Middle, Upper, Window, Side Lower).
  - Unique 10-digit PNR generation (e.g., `PNR-2849102847`).
* **Interactive AI Console**:
  - Wizard accessible directly from the menu with sample presets and real-time execution outputs.
* **Audit & Traceability**:
  - Complete step-by-step logs (`ai.agent.step`) recording each Thought, Action, Arguments, and Observation.
* **Automated Cron / Background Execution**:
  - Scheduled Action to automatically process pending batch booking requests.

---

## 📂 Module Structure

```
ai_agent_train_booking/
├── __init__.py
├── __manifest__.py
├── README.md
├── security/
│   ├── agent_security.xml             # User & Manager access groups
│   └── ir.model.access.csv            # Security ACLs
├── data/
│   ├── station_data.xml               # NDLS, MMCT, HWH, SBC, MAS, BSB, etc.
│   ├── train_data.xml                 # Rajdhani, Vande Bharat, Shatabdi, etc.
│   ├── agent_tools_data.xml           # 6 Tool definitions with JSON Schemas
│   ├── agent_config_data.xml          # Default RailBot Agent configuration
│   └── automated_cron_data.xml        # Background automated task processor
├── models/
│   ├── __init__.py
│   ├── train_station.py               # Railway station model
│   ├── train_train.py                 # Train model with schedule and routes
│   ├── train_fare_rule.py             # Class quota and fare rules
│   ├── train_booking.py               # Booking lifecycle (Draft, Confirmed, Cancelled)
│   ├── train_passenger.py             # Passenger details, coach and berth allocation
│   ├── ai_agent_tool.py               # Tool execution dispatcher
│   ├── ai_agent.py                    # Agent settings, provider, instructions
│   ├── ai_agent_task.py               # Execution session model
│   ├── ai_agent_step.py               # Step-by-step trace logger
│   └── res_config_settings.py         # System configuration
├── utils/
│   ├── __init__.py
│   └── agent_engine.py                # Dual Agentic Loop (LLM + Deterministic Engine)
├── views/
│   ├── train_station_views.xml        # Station list and forms
│   ├── train_train_views.xml          # Train list, forms, quotas
│   ├── train_booking_views.xml        # Booking list, form, chatter
│   ├── ai_agent_views.xml             # Agent and Tool configurations
│   ├── ai_agent_task_views.xml        # Task execution and trace views
│   ├── res_config_settings_views.xml  # Settings
│   └── menus.xml                      # Menus and action links
├── wizard/
│   ├── __init__.py
│   ├── agent_prompt_wizard.py         # Interactive prompt wizard model
│   └── agent_prompt_wizard_views.xml  # Interactive console UI
└── static/
    └── description/
        ├── icon.png                   # Module icon
        └── index.html                 # App store presentation
```

---

## ⚡ Quick Start Guide

### 1. Installation
1. Place the `ai_agent_train_booking` folder in your Odoo custom addons directory.
2. Restart your Odoo server:
   ```bash
   ./odoo-bin -c /path/to/odoo.conf -u ai_agent_train_booking
   ```
3. Activate Developer Mode in Odoo, go to **Apps**, click **Update Apps List**, search for **Agentic AI Train Ticket Booking**, and click **Install**.

### 2. Running an Autonomous Booking
1. Open the top menu: **Train AI Agent &rarr; AI Agent &rarr; Quick Agent Console**.
2. Select or enter a natural language prompt, for example:
   > *"Book a ticket from New Delhi to Mumbai tomorrow for Amit Sharma, age 34, male in 2AC"*
3. Click **Run AI Agent**.
4. The agent will:
   - Search available trains between New Delhi (`NDLS`) and Mumbai (`MMCT`).
   - Check seat availability on the Mumbai Tejas Rajdhani Express (`12952`) for class `2A`.
   - Create a reservation record in Odoo with passenger details.
   - Allocate Coach (`A1`) and Berth (`34 Lower`).
   - Issue a unique PNR (e.g., `PNR-7294018294`) and mark the booking **Confirmed**!
5. Click **Open Booking Record** to view the generated booking in Odoo with full chatter history.
6. Click **View Full Agent Trace** to inspect every reasoning thought and database tool execution.

---

## 🔒 Configuration & External LLMs

To use an external LLM instead of the built-in deterministic engine:
1. Navigate to **Train AI Agent &rarr; AI Agent &rarr; AI Agents**.
2. Open **RailBot - Autonomous Train Booking Agent**.
3. Set **AI Provider** to `OpenAI`, `Google Gemini`, `Anthropic Claude`, or `Local Ollama`.
4. Enter your **API Key** and select your desired model (e.g. `gpt-4o-mini`, `gemini-1.5-flash`).
5. Choose your **Autonomy Level**:
   - `Fully Autonomous`: Auto-confirms bookings when seats are available.
   - `Supervised`: Reserves in Draft and waits for human approval.
