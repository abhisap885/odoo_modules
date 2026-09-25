# -*- coding: utf-8 -*-
import json
import re
import time
import datetime
import logging
import requests

_logger = logging.getLogger(__name__)

class AgentExecutionEngine:
    """Multi-turn Agentic AI Engine supporting both real LLM Tool-Calling
    and a Deterministic Autonomous Fallback Engine for zero-dependency operation.
    """

    def __init__(self, task):
        self.task = task
        self.agent = task.agent_id
        self.env = task.env

    def run(self):
        start_time = time.time()
        self.task.state = 'running'
        # Clear previous steps if re-running
        self.task.step_ids.unlink()

        try:
            if self.agent.provider == 'simulated' or not self.agent.api_key:
                result = self._run_deterministic_agent()
            else:
                result = self._run_llm_agent()

            self.task.final_response = result
            if self.agent.autonomous_level == 'human_in_the_loop' and self.task.booking_id and self.task.booking_id.state == 'draft':
                self.task.state = 'waiting_approval'
            else:
                self.task.state = 'done'
        except Exception as e:
            _logger.exception("Agent execution failed: %s", e)
            self.task.state = 'failed'
            self.task.final_response = f"Agent encountered an error: {str(e)}"
            self._log_step(
                sequence=len(self.task.step_ids) + 1,
                step_type='final_answer',
                thought="Execution terminated with error",
                tool_result=str(e),
                is_error=True
            )
        finally:
            self.task.execution_time = round(time.time() - start_time, 2)

    def _log_step(self, sequence, step_type, thought=None, tool_name=None, tool_args=None, tool_result=None, is_error=False):
        return self.env['ai.agent.step'].create({
            'task_id': self.task.id,
            'sequence': sequence,
            'step_type': step_type,
            'thought': thought or '',
            'tool_name': tool_name or '',
            'tool_args': json.dumps(tool_args, indent=2) if isinstance(tool_args, (dict, list)) else (tool_args or ''),
            'tool_result': json.dumps(tool_result, indent=2) if isinstance(tool_result, (dict, list)) else (tool_result or ''),
            'is_error': is_error
        })

    # =========================================================================
    # DETERMINISTIC AGENTIC ENGINE (Out-of-the-box autonomous execution)
    # =========================================================================
    def _run_deterministic_agent(self):
        prompt = self.task.prompt or ""
        lower_prompt = prompt.lower()
        seq = 1

        # 1. Detect Intent
        if any(w in lower_prompt for w in ['cancel', 'refund']):
            return self._handle_deterministic_cancel(prompt, seq)
        elif any(w in lower_prompt for w in ['pnr', 'status', 'track']):
            return self._handle_deterministic_pnr(prompt, seq)
        elif any(w in lower_prompt for w in ['search', 'find', 'check train', 'available train', 'list train']):
            if not any(w in lower_prompt for w in ['book', 'reserve', 'ticket for']):
                return self._handle_deterministic_search_only(prompt, seq)

        # Default Workflow: End-to-End Autonomous Train Ticket Booking
        return self._handle_deterministic_booking(prompt, seq)

    def _handle_deterministic_booking(self, prompt, seq):
        # Extract details with heuristic parsing
        origin, destination = self._extract_route(prompt)
        travel_date = self._extract_date(prompt)
        travel_class = self._extract_class(prompt)
        passengers = self._extract_passengers(prompt)

        # Step 1: Reasoning & Search Trains
        thought_1 = f"I need to book a train ticket from '{origin}' to '{destination}' on {travel_date}. First, I will search for available trains running on this route."
        tool_search = self.env['ai.agent.tool'].search([('name', '=', 'search_trains')], limit=1)
        if not tool_search:
            raise Exception("Required tool 'search_trains' is not registered!")

        args_1 = {"origin": origin, "destination": destination, "date": str(travel_date)}
        self._log_step(seq, 'thought', thought=thought_1)
        seq += 1

        self._log_step(seq, 'tool_call', tool_name='search_trains', tool_args=args_1)
        res_1 = tool_search.execute_tool(self.agent, args_1, task=self.task)
        self._log_step(seq, 'observation', tool_name='search_trains', tool_result=res_1)
        seq += 1

        if res_1.get('status') != 'success' or not res_1.get('data', {}).get('trains'):
            msg = f"Could not find any trains running from '{origin}' to '{destination}'. Please verify station codes/names."
            self._log_step(seq, 'final_answer', thought="Search yielded no results.", tool_result=msg)
            return msg

        train_data = res_1['data']['trains'][0]
        train_no = train_data['train_number']
        train_name = train_data['train_name']

        # Step 2: Check Seats
        thought_2 = f"Found train {train_no} ({train_name}). Now checking seat availability and fare for class '{travel_class}'."
        tool_check = self.env['ai.agent.tool'].search([('name', '=', 'check_seat_availability')], limit=1)
        args_2 = {"train_number": train_no, "travel_class": travel_class, "date": str(travel_date)}
        self._log_step(seq, 'thought', thought=thought_2)
        seq += 1

        self._log_step(seq, 'tool_call', tool_name='check_seat_availability', tool_args=args_2)
        res_2 = tool_check.execute_tool(self.agent, args_2, task=self.task)
        self._log_step(seq, 'observation', tool_name='check_seat_availability', tool_result=res_2)
        seq += 1

        # Fallback class if not available
        available_seats = res_2.get('data', {}).get('available_seats', 0)
        if available_seats <= 0 and train_data.get('classes'):
            travel_class = train_data['classes'][0]['class']

        # Step 3: Book Ticket
        thought_3 = f"Seats are available in class '{travel_class}'. Proceeding to reserve the booking in Odoo for passenger(s): {[p['name'] for p in passengers]}."
        tool_book = self.env['ai.agent.tool'].search([('name', '=', 'book_train_ticket')], limit=1)
        args_3 = {
            "train_number": train_no,
            "travel_class": travel_class,
            "journey_date": str(travel_date),
            "passengers": passengers,
            "customer_name": passengers[0]['name'] if passengers else "Passenger",
            "auto_confirm": (self.agent.autonomous_level == 'full_auto')
        }
        self._log_step(seq, 'thought', thought=thought_3)
        seq += 1

        self._log_step(seq, 'tool_call', tool_name='book_train_ticket', tool_args=args_3)
        res_3 = tool_book.execute_tool(self.agent, args_3, task=self.task)
        self._log_step(seq, 'observation', tool_name='book_train_ticket', tool_result=res_3)
        seq += 1

        booking_info = res_3.get('data', {})
        pnr = booking_info.get('pnr', 'N/A')
        total_fare = booking_info.get('total_fare', 0.0)

        # Step 4: Confirm (if required)
        if self.agent.autonomous_level == 'full_auto' and booking_info.get('status') != 'CONFIRMED':
            thought_4 = f"Confirming ticket reservation for PNR {pnr} and allocating coach and berths."
            tool_confirm = self.env['ai.agent.tool'].search([('name', '=', 'confirm_ticket')], limit=1)
            args_4 = {"pnr": pnr}
            self._log_step(seq, 'thought', thought=thought_4)
            seq += 1

            self._log_step(seq, 'tool_call', tool_name='confirm_ticket', tool_args=args_4)
            res_4 = tool_confirm.execute_tool(self.agent, args_4, task=self.task)
            self._log_step(seq, 'observation', tool_name='confirm_ticket', tool_result=res_4)
            seq += 1

        # Step 5: Final Answer
        passenger_lines = []
        for p in booking_info.get('passengers', []):
            passenger_lines.append(f"• {p.get('passenger')}: Coach {p.get('coach')}, Berth {p.get('berth')} ({p.get('berth_type')})")

        passengers_str = "\n".join(passenger_lines) if passenger_lines else f"• {passengers[0]['name']}"

        status_str = "CONFIRMED" if self.agent.autonomous_level == 'full_auto' else "RESERVED (Pending Approval)"
        final_text = (
            f"🚆 **Train Ticket Booking Completed Successfully!**\n\n"
            f"• **PNR Number:** `{pnr}`\n"
            f"• **Train:** {train_no} - {train_name}\n"
            f"• **Route:** {train_data['origin']} ➔ {train_data['destination']}\n"
            f"• **Departure:** {train_data.get('departure_time', 'N/A')} | **Arrival:** {train_data.get('arrival_time', 'N/A')}\n"
            f"• **Journey Date:** {travel_date}\n"
            f"• **Class:** {travel_class}\n"
            f"• **Booking Status:** {status_str}\n"
            f"• **Total Fare:** ₹{total_fare:,.2f}\n\n"
            f"**Passenger & Seat Allocation:**\n"
            f"{passengers_str}\n\n"
            f"The booking record has been generated in Odoo and is linked to this task."
        )

        self._log_step(seq, 'final_answer', thought="Workflow complete. Generating booking itinerary for user.", tool_result=final_text)
        return final_text

    def _handle_deterministic_search_only(self, prompt, seq):
        origin, destination = self._extract_route(prompt)
        travel_date = self._extract_date(prompt)
        tool_search = self.env['ai.agent.tool'].search([('name', '=', 'search_trains')], limit=1)

        self._log_step(seq, 'thought', thought=f"User wants to search trains from {origin} to {destination}.")
        seq += 1
        args = {"origin": origin, "destination": destination, "date": str(travel_date)}
        self._log_step(seq, 'tool_call', tool_name='search_trains', tool_args=args)
        res = tool_search.execute_tool(self.agent, args, task=self.task)
        self._log_step(seq, 'observation', tool_name='search_trains', tool_result=res)
        seq += 1

        trains = res.get('data', {}).get('trains', [])
        if not trains:
            msg = f"No trains found running between {origin} and {destination}."
            self._log_step(seq, 'final_answer', tool_result=msg)
            return msg

        lines = [f"Found {len(trains)} train(s) running between {origin} and {destination}:\n"]
        for t in trains:
            classes_str = ", ".join([f"{c['class']} (₹{c['fare']}, {c['available_seats']} seats)" for c in t['classes']])
            lines.append(f"• **{t['train_number']} {t['train_name']}** ({t['train_type']})\n  Dep: {t['departure_time']} | Arr: {t['arrival_time']} ({t['duration_hours']} hrs)\n  Available Classes: {classes_str}")

        final_msg = "\n\n".join(lines)
        self._log_step(seq, 'final_answer', tool_result=final_msg)
        return final_msg

    def _handle_deterministic_pnr(self, prompt, seq):
        pnr_match = re.search(r'PNR-?\d+', prompt, re.IGNORECASE)
        pnr = pnr_match.group(0).upper() if pnr_match else "PNR-1234567890"
        if not pnr.startswith("PNR-"):
            pnr = f"PNR-{pnr.replace('PNR', '')}"

        tool = self.env['ai.agent.tool'].search([('name', '=', 'get_pnr_status')], limit=1)
        self._log_step(seq, 'thought', thought=f"Retrieving PNR status for {pnr}.")
        seq += 1
        args = {"pnr": pnr}
        self._log_step(seq, 'tool_call', tool_name='get_pnr_status', tool_args=args)
        res = tool.execute_tool(self.agent, args, task=self.task)
        self._log_step(seq, 'observation', tool_name='get_pnr_status', tool_result=res)
        seq += 1

        data = res.get('data', {})
        if 'error' in data:
            msg = data['error']
        else:
            msg = f"**PNR Status for {data.get('pnr')}:**\n• Status: {data.get('status')}\n• Train: {data.get('train')}\n• Date: {data.get('journey_date')}\n• Route: {data.get('origin')} ➔ {data.get('destination')}\n• Fare: ₹{data.get('total_fare')}"
        self._log_step(seq, 'final_answer', tool_result=msg)
        return msg

    def _handle_deterministic_cancel(self, prompt, seq):
        pnr_match = re.search(r'PNR-?\d+', prompt, re.IGNORECASE)
        pnr = pnr_match.group(0).upper() if pnr_match else ""
        if not pnr:
            booking = self.env['train.booking'].search([('state', '=', 'confirmed')], limit=1, order='id desc')
            pnr = booking.name if booking else "PNR-0000000000"

        tool = self.env['ai.agent.tool'].search([('name', '=', 'cancel_ticket')], limit=1)
        self._log_step(seq, 'thought', thought=f"Processing cancellation for {pnr}.")
        seq += 1
        args = {"pnr": pnr}
        self._log_step(seq, 'tool_call', tool_name='cancel_ticket', tool_args=args)
        res = tool.execute_tool(self.agent, args, task=self.task)
        self._log_step(seq, 'observation', tool_name='cancel_ticket', tool_result=res)
        seq += 1

        msg = res.get('data', {}).get('message', f"Cancellation processed for {pnr}.")
        self._log_step(seq, 'final_answer', tool_result=msg)
        return msg

    # =========================================================================
    # HEURISTIC EXTRACTION HELPERS
    # =========================================================================
    def _extract_route(self, prompt):
        # Known common Indian stations/cities
        stations = {
            'delhi': 'NDLS', 'new delhi': 'NDLS', 'ndls': 'NDLS',
            'mumbai': 'MMCT', 'bombay': 'MMCT', 'mmct': 'MMCT', 'csmt': 'CSMT',
            'bangalore': 'SBC', 'bengaluru': 'SBC', 'sbc': 'SBC',
            'chennai': 'MAS', 'madras': 'MAS', 'mas': 'MAS',
            'kolkata': 'HWH', 'calcutta': 'HWH', 'howrah': 'HWH', 'hwh': 'HWH',
            'patna': 'PNBE', 'pnbe': 'PNBE',
            'varanasi': 'BSB', 'bsb': 'BSB',
            'ahmedabad': 'ADI', 'adi': 'ADI',
            'gorakhpur': 'GKP', 'gkp': 'GKP',
            'pune': 'PUNE',
        }

        origin = 'NDLS'
        destination = 'MMCT'

        # Look for "from <X> to <Y>"
        m = re.search(r'from\s+([A-Za-z\s]+?)\s+to\s+([A-Za-z\s]+?)(?:\s+on|\s+for|\s+in|\s+tomorrow|\s+next|$)', prompt, re.IGNORECASE)
        if m:
            raw_orig = m.group(1).strip().lower()
            raw_dest = m.group(2).strip().lower()
            for key, code in stations.items():
                if key in raw_orig:
                    origin = code
                if key in raw_dest:
                    destination = code
        else:
            # Check station codes directly
            matches = []
            words = re.findall(r'\b[A-Za-z]{3,10}\b', prompt.lower())
            for w in words:
                if w in stations and stations[w] not in matches:
                    matches.append(stations[w])
            if len(matches) >= 2:
                origin, destination = matches[0], matches[1]

        return origin, destination

    def _extract_date(self, prompt):
        today = datetime.date.today()
        lower = prompt.lower()
        if 'tomorrow' in lower:
            return today + datetime.timedelta(days=1)
        elif 'day after tomorrow' in lower:
            return today + datetime.timedelta(days=2)

        # Look for YYYY-MM-DD
        m = re.search(r'\b(20\d{2}-\d{2}-\d{2})\b', prompt)
        if m:
            try:
                return datetime.datetime.strptime(m.group(1), '%Y-%m-%d').date()
            except ValueError:
                pass
        return today + datetime.timedelta(days=1)

    def _extract_class(self, prompt):
        upper = prompt.upper()
        if '1A' in upper or 'FIRST AC' in upper:
            return '1A'
        elif '2A' in upper or '2ND AC' in upper or '2 AC' in upper or '2-TIER' in upper:
            return '2A'
        elif '3A' in upper or '3RD AC' in upper or '3 AC' in upper or '3-TIER' in upper:
            return '3A'
        elif 'EC' in upper or 'EXECUTIVE' in upper:
            return 'EC'
        elif 'CC' in upper or 'CHAIR' in upper:
            return 'CC'
        elif 'SL' in upper or 'SLEEPER' in upper:
            return 'SL'
        return '2A'

    def _extract_passengers(self, prompt):
        # Look for e.g. "for Rajesh Kumar, 34 M" or "passenger John Doe, age 28"
        passengers = []
        m = re.search(r'for\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)(?:.*?(\d{1,2}))?(?:.*?\b(male|female|m|f)\b)?', prompt, re.IGNORECASE)
        if m and m.group(1).lower() not in ['tomorrow', 'train', 'ticket', 'next']:
            name = m.group(1).strip()
            age = int(m.group(2)) if m.group(2) else 30
            gender = 'female' if m.group(3) and m.group(3).lower() in ['f', 'female'] else 'male'
            passengers.append({
                "name": name,
                "age": age,
                "gender": gender,
                "berth_preference": "lower"
            })
        else:
            passengers.append({
                "name": "Amitabh Sharma",
                "age": 34,
                "gender": "male",
                "berth_preference": "lower"
            })
        return passengers

    # =========================================================================
    # REAL LLM FUNCTION CALLING ENGINE (OpenAI / Gemini / Anthropic / Ollama)
    # =========================================================================
    def _run_llm_agent(self):
        tools = self.agent.tool_ids.filtered(lambda t: t.active)
        openai_tools = []
        for t in tools:
            try:
                schema = json.loads(t.parameters_schema)
            except Exception:
                schema = {"type": "object", "properties": {}}
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": schema
                }
            })

        system_instruction = self.agent.system_prompt or (
            "You are RailBot, an autonomous agentic AI in Odoo responsible for train ticket booking and travel operations.\n"
            "You have direct access to database tools: search_trains, check_seat_availability, book_train_ticket, confirm_ticket, get_pnr_status, cancel_ticket.\n"
            "Always reason step-by-step: first search for trains, verify seat availability and fare, execute the booking, and confirm it.\n"
            "Do not stop until the user's goal has been accomplished."
        )

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": self.task.prompt}
        ]

        seq = 1
        max_iters = self.agent.max_iterations or 6

        for iteration in range(max_iters):
            # Call provider API
            response_data = self._call_provider(messages, openai_tools)
            if isinstance(response_data, list):
                response_data = response_data[0] if response_data else {}
            elif not isinstance(response_data, dict):
                response_data = {}

            choices = response_data.get("choices", [{}])
            if isinstance(choices, list) and choices:
                message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
            else:
                message = {}
            content = message.get("content") or ""
            tool_calls = message.get("tool_calls") or []

            messages.append(message)

            if content:
                self._log_step(seq, 'thought', thought=content)
                seq += 1

            if not tool_calls:
                # Agent finished without calling further tools
                self._log_step(seq, 'final_answer', tool_result=content)
                return content

            for tool_call in tool_calls:
                func = tool_call.get("function", {})
                tool_name = func.get("name")
                try:
                    tool_args = json.loads(func.get("arguments", "{}"))
                except Exception:
                    tool_args = {}

                tool_rec = self.env['ai.agent.tool'].search([('name', '=', tool_name)], limit=1)
                self._log_step(seq, 'tool_call', tool_name=tool_name, tool_args=tool_args)
                seq += 1

                if tool_rec:
                    exec_res = tool_rec.execute_tool(self.agent, tool_args, task=self.task)
                else:
                    exec_res = {"error": f"Tool '{tool_name}' not found."}

                self._log_step(seq, 'observation', tool_name=tool_name, tool_result=exec_res)
                seq += 1

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", f"call_{iteration}_{seq}"),
                    "content": json.dumps(exec_res)
                })

        return "Agent reached maximum iteration limit."

    def _call_provider(self, messages, tools):
        provider = self.agent.provider
        api_key = self.agent.api_key
        model = self.agent.model or "gpt-4o-mini"
        base_url = self.agent.base_url

        if provider == 'openai':
            url = (base_url or "https://api.openai.com/v1") + "/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {"model": model, "messages": messages, "tools": tools, "tool_choice": "auto"}
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            return resp.json()

        elif provider == 'gemini':
            # Support Gemini via OpenAI-compatible endpoint or v1beta
            url = (base_url or "https://generativelanguage.googleapis.com/v1beta/openai") + "/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {"model": model or "gemini-1.5-flash", "messages": messages, "tools": tools}
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            return resp.json()

        elif provider == 'ollama':
            url = (base_url or "http://localhost:11434") + "/v1/chat/completions"
            payload = {"model": model or "llama3.1", "messages": messages, "tools": tools}
            resp = requests.post(url, json=payload, timeout=60)
            return resp.json()

        raise Exception(f"Unsupported LLM provider: {provider}")
