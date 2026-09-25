# -*- coding: utf-8 -*-
import json
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class AIAgentTool(models.Model):
    _name = 'ai.agent.tool'
    _description = 'Agentic AI Tool Definition'
    _order = 'name asc'

    name = fields.Char(string='Tool Identifier', required=True, index=True, help='e.g. search_trains')
    label = fields.Char(string='Label', required=True)
    description = fields.Text(string='Tool Description for AI', required=True)
    parameters_schema = fields.Text(string='Parameters JSON Schema', required=True)
    active = fields.Boolean(default=True)

    def execute_tool(self, agent, args_dict, task=None):
        """Executes the tool with the given arguments within Odoo and returns a JSON-serializable dict."""
        self.ensure_one()
        handler_name = f"_tool_{self.name}"
        if hasattr(self, handler_name):
            try:
                result = getattr(self, handler_name)(agent, args_dict, task=task)
                return {"status": "success", "data": result}
            except Exception as e:
                _logger.exception("Error executing tool %s: %s", self.name, e)
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": f"No handler implemented for tool: {self.name}"}

    # -------------------------------------------------------------
    # Tool 1: search_trains
    # -------------------------------------------------------------
    def _tool_search_trains(self, agent, args, task=None):
        origin = (args.get('origin') or '').strip().upper()
        destination = (args.get('destination') or '').strip().upper()
        date = args.get('date')

        station_obj = self.env['train.station']
        source_stations = station_obj.search([
            '|', '|',
            ('code', '=ilike', origin),
            ('name', 'ilike', origin),
            ('city', 'ilike', origin)
        ])
        dest_stations = station_obj.search([
            '|', '|',
            ('code', '=ilike', destination),
            ('name', 'ilike', destination),
            ('city', 'ilike', destination)
        ])

        if not source_stations:
            return {"error": f"Origin station '{origin}' could not be identified."}
        if not dest_stations:
            return {"error": f"Destination station '{destination}' could not be identified."}

        trains = self.env['train.train'].search([
            ('source_station_id', 'in', source_stations.ids),
            ('destination_station_id', 'in', dest_stations.ids),
            ('active', '=', True)
        ])

        if not trains:
            # Fallback: search trains originating from source
            return {
                "message": f"No direct trains found between {source_stations[0].display_name} and {dest_stations[0].display_name}.",
                "trains": []
            }

        train_list = []
        for t in trains:
            classes = []
            for rule in t.fare_rule_ids:
                classes.append({
                    "class": rule.travel_class,
                    "available_seats": rule.available_seats,
                    "fare": rule.base_fare
                })
            train_list.append({
                "train_number": t.number,
                "train_name": t.name,
                "train_type": dict(t._fields['train_type'].selection).get(t.train_type, t.train_type),
                "origin": t.source_station_id.display_name,
                "destination": t.destination_station_id.display_name,
                "departure_time": t.departure_time,
                "arrival_time": t.arrival_time,
                "duration_hours": t.duration_hours,
                "running_days": t.running_days,
                "classes": classes
            })

        return {
            "origin": source_stations[0].display_name,
            "destination": dest_stations[0].display_name,
            "count": len(train_list),
            "trains": train_list
        }

    # -------------------------------------------------------------
    # Tool 2: check_seat_availability
    # -------------------------------------------------------------
    def _tool_check_seat_availability(self, agent, args, task=None):
        train_query = str(args.get('train_number') or '').strip()
        travel_class = (args.get('travel_class') or '').strip().upper()
        # Normalize class name (e.g. 2AC -> 2A, 3AC -> 3A, SLEEPER -> SL)
        travel_class = travel_class.replace('AC', '').replace('TIER', '').strip()
        if travel_class == 'SLEEPER':
            travel_class = 'SL'
        elif travel_class == 'CHAIR':
            travel_class = 'CC'

        train = self.env['train.train'].search([
            '|',
            ('number', '=ilike', train_query),
            ('name', 'ilike', train_query)
        ], limit=1)

        if not train:
            return {"error": f"Train matching '{train_query}' not found."}

        rule = self.env['train.fare.rule'].search([
            ('train_id', '=', train.id),
            ('travel_class', '=', travel_class)
        ], limit=1)

        if not rule:
            available_classes = [r.travel_class for r in train.fare_rule_ids]
            return {
                "error": f"Class '{travel_class}' is not configured for train {train.display_name}. Available classes: {available_classes}"
            }

        return {
            "train_number": train.number,
            "train_name": train.name,
            "travel_class": rule.travel_class,
            "total_quota": rule.total_seats,
            "available_seats": rule.available_seats,
            "base_fare": rule.base_fare,
            "availability_status": "AVAILABLE" if rule.available_seats > 0 else "REGRET / FULL"
        }

    # -------------------------------------------------------------
    # Tool 3: book_train_ticket
    # -------------------------------------------------------------
    def _tool_book_train_ticket(self, agent, args, task=None):
        train_query = str(args.get('train_number') or '').strip()
        travel_class = (args.get('travel_class') or '3A').strip().upper()
        travel_class = travel_class.replace('AC', '').replace('TIER', '').strip()
        if travel_class == 'SLEEPER':
            travel_class = 'SL'
        elif travel_class == 'CHAIR':
            travel_class = 'CC'

        journey_date = args.get('journey_date') or fields.Date.today()
        customer_name = args.get('customer_name') or 'Valued Passenger'
        customer_email = args.get('customer_email')
        auto_confirm = args.get('auto_confirm')
        if auto_confirm is None:
            auto_confirm = (agent.autonomous_level == 'full_auto')

        train = self.env['train.train'].search([
            '|',
            ('number', '=ilike', train_query),
            ('name', 'ilike', train_query)
        ], limit=1)

        if not train:
            return {"error": f"Train '{train_query}' not found."}

        # Check fare rule
        rule = self.env['train.fare.rule'].search([
            ('train_id', '=', train.id),
            ('travel_class', '=', travel_class)
        ], limit=1)
        if not rule:
            rule = train.fare_rule_ids[:1]
            if not rule:
                return {"error": f"No fare rule found for train {train.display_name}."}
            travel_class = rule.travel_class

        # Find or create partner
        partner = None
        if customer_email:
            partner = self.env['res.partner'].search([('email', '=ilike', customer_email)], limit=1)
        if not partner:
            partner = self.env['res.partner'].search([('name', '=ilike', customer_name)], limit=1)
        if not partner:
            partner = self.env['res.partner'].create({
                'name': customer_name,
                'email': customer_email or False,
            })

        # Process passengers list
        raw_passengers = args.get('passengers') or []
        if not raw_passengers:
            # Fallback single passenger from customer name
            raw_passengers = [{'name': customer_name, 'age': 30, 'gender': 'male', 'berth_preference': 'lower'}]

        passenger_vals = []
        for p in raw_passengers:
            gender = (p.get('gender') or 'male').lower()
            if gender not in ['male', 'female', 'other']:
                gender = 'male'
            pref = (p.get('berth_preference') or 'no_preference').lower()
            passenger_vals.append((0, 0, {
                'name': p.get('name') or customer_name,
                'age': int(p.get('age') or 30),
                'gender': gender,
                'berth_preference': pref if pref in ['lower', 'middle', 'upper', 'side_lower', 'side_upper', 'window'] else 'no_preference',
                'fare': rule.base_fare,
            }))

        booking_vals = {
            'partner_id': partner.id,
            'train_id': train.id,
            'source_station_id': train.source_station_id.id,
            'destination_station_id': train.destination_station_id.id,
            'journey_date': journey_date,
            'travel_class': travel_class,
            'booking_type': 'agentic_ai',
            'ai_task_id': task.id if task else False,
            'passenger_ids': passenger_vals,
            'booking_notes': f"Automatically reserved by AI Agent: {agent.name}",
        }

        booking = self.env['train.booking'].create(booking_vals)

        if task:
            task.booking_id = booking.id

        active_irctc = self.env['irctc.credential'].search([('state', '=', 'active')], limit=1)
        if active_irctc:
            booking.irctc_account_id = active_irctc.id
            if auto_confirm:
                booking.action_book_on_irctc()
        elif auto_confirm:
            booking.action_confirm()

        allocated_info = []
        for p in booking.passenger_ids:
            allocated_info.append({
                "passenger": p.name,
                "coach": p.allocated_coach or "Pending",
                "berth": p.allocated_berth or "Pending",
                "berth_type": p.allocated_berth_type or "Pending",
            })

        return {
            "booking_id": booking.id,
            "pnr": booking.name,
            "status": booking.state.upper(),
            "train_number": train.number,
            "train_name": train.name,
            "route": f"{train.source_station_id.code} -> {train.destination_station_id.code}",
            "journey_date": str(booking.journey_date),
            "travel_class": booking.travel_class,
            "passenger_count": len(booking.passenger_ids),
            "total_fare": booking.total_fare,
            "passengers": allocated_info,
            "message": "Train ticket successfully booked and confirmed!" if booking.state == 'confirmed' else "Ticket reserved in draft state awaiting confirmation."
        }

    # -------------------------------------------------------------
    # Tool 4: confirm_ticket
    # -------------------------------------------------------------
    def _tool_confirm_ticket(self, agent, args, task=None):
        pnr = (args.get('pnr') or '').strip()
        booking_id = args.get('booking_id')

        domain = []
        if pnr:
            domain = [('name', '=ilike', pnr)]
        elif booking_id:
            domain = [('id', '=', booking_id)]
        else:
            return {"error": "Please provide either 'pnr' or 'booking_id' to confirm."}

        booking = self.env['train.booking'].search(domain, limit=1)
        if not booking:
            return {"error": f"Booking with PNR '{pnr}' not found."}

        if booking.state == 'confirmed':
            return {"message": f"Booking {booking.name} is already CONFIRMED.", "pnr": booking.name}

        booking.action_confirm()
        return {
            "pnr": booking.name,
            "status": "CONFIRMED",
            "total_fare": booking.total_fare,
            "passengers": [
                {"name": p.name, "coach": p.allocated_coach, "berth": p.allocated_berth, "type": p.allocated_berth_type}
                for p in booking.passenger_ids
            ],
            "message": f"PNR {booking.name} has been successfully confirmed!"
        }

    # -------------------------------------------------------------
    # Tool 5: get_pnr_status
    # -------------------------------------------------------------
    def _tool_get_pnr_status(self, agent, args, task=None):
        pnr = (args.get('pnr') or '').strip()
        booking = self.env['train.booking'].search([('name', '=ilike', pnr)], limit=1)
        if not booking:
            return {"error": f"PNR '{pnr}' not found in the reservation database."}

        passengers_data = []
        for p in booking.passenger_ids:
            passengers_data.append({
                "name": p.name,
                "age": p.age,
                "gender": p.gender,
                "coach": p.allocated_coach or "N/A",
                "berth": p.allocated_berth or "WL",
                "berth_type": p.allocated_berth_type or "N/A"
            })

        return {
            "pnr": booking.name,
            "status": booking.state.upper(),
            "train": booking.train_id.display_name,
            "journey_date": str(booking.journey_date),
            "origin": booking.source_station_id.display_name,
            "destination": booking.destination_station_id.display_name,
            "class": booking.travel_class,
            "total_fare": booking.total_fare,
            "passengers": passengers_data
        }

    # -------------------------------------------------------------
    # Tool 6: cancel_ticket
    # -------------------------------------------------------------
    def _tool_cancel_ticket(self, agent, args, task=None):
        pnr = (args.get('pnr') or '').strip()
        booking = self.env['train.booking'].search([('name', '=ilike', pnr)], limit=1)
        if not booking:
            return {"error": f"PNR '{pnr}' not found."}

        if booking.state == 'cancelled':
            return {"message": f"PNR {booking.name} is already cancelled."}

        booking.action_cancel()
        return {
            "pnr": booking.name,
            "status": "CANCELLED",
            "message": f"Booking {booking.name} cancelled successfully. Seats returned to quota."
        }
