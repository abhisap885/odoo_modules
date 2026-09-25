# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
import datetime

class TestTrainBookingAgent(TransactionCase):

    def setUp(self):
        super().setUp()
        self.station_delhi = self.env['train.station'].create({
            'name': 'New Delhi',
            'code': 'NDLS',
            'city': 'Delhi',
            'zone': 'Northern Railway',
        })
        self.station_mumbai = self.env['train.station'].create({
            'name': 'Mumbai Central',
            'code': 'MMCT',
            'city': 'Mumbai',
            'zone': 'Western Railway',
        })
        self.train = self.env['train.train'].create({
            'name': 'Tejas Rajdhani Express',
            'number': '12952',
            'train_type': 'rajdhani',
            'source_station_id': self.station_delhi.id,
            'destination_station_id': self.station_mumbai.id,
            'departure_time': '16:55',
            'arrival_time': '08:35',
            'duration_hours': 15.6,
        })
        self.fare_rule = self.env['train.fare.rule'].create({
            'train_id': self.train.id,
            'travel_class': '2A',
            'base_fare': 2850.0,
            'total_seats': 50,
            'available_seats': 50,
        })
        self.agent = self.env['ai.agent'].create({
            'name': 'Test RailBot',
            'provider': 'simulated',
            'autonomous_level': 'full_auto',
            'max_iterations': 6,
        })

    def test_01_booking_creation_and_confirm(self):
        """Test manual/ORM booking creation and seat deduction."""
        booking = self.env['train.booking'].create({
            'train_id': self.train.id,
            'journey_date': datetime.date.today() + datetime.timedelta(days=1),
            'travel_class': '2A',
            'passenger_ids': [(0, 0, {
                'name': 'Priya Singh',
                'age': 28,
                'gender': 'female',
                'berth_preference': 'lower',
            })],
        })
        self.assertTrue(booking.name.startswith('PNR-'))
        self.assertEqual(booking.state, 'draft')
        self.assertEqual(self.fare_rule.available_seats, 50)

        # Confirm booking
        booking.action_confirm()
        self.assertEqual(booking.state, 'confirmed')
        self.assertEqual(self.fare_rule.available_seats, 49)
        self.assertTrue(booking.passenger_ids[0].allocated_coach)
        self.assertTrue(booking.passenger_ids[0].allocated_berth)

        # Cancel booking
        booking.action_cancel()
        self.assertEqual(booking.state, 'cancelled')
        self.assertEqual(self.fare_rule.available_seats, 50)

    def test_02_agent_task_execution(self):
        """Test autonomous Agent task execution from natural language."""
        task = self.env['ai.agent.task'].create({
            'agent_id': self.agent.id,
            'prompt': "Book 1 ticket from Delhi (NDLS) to Mumbai (MMCT) tomorrow for Amit Sharma, age 34, male in 2AC",
        })
        task.action_run()
        self.assertEqual(task.state, 'done')
        self.assertTrue(task.booking_id)
        self.assertEqual(task.booking_id.state, 'confirmed')
        self.assertTrue(len(task.step_ids) >= 3)
        self.assertIn("PNR", task.final_response)
