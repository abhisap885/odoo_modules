# -*- coding: utf-8 -*-
import json
import logging
import requests

_logger = logging.getLogger(__name__)

class IrctcApiService:
    """Service client for Live Indian Railways / IRCTC endpoints.
    Allows real-time train search, live seat availability, and live PNR tracking.
    """

    def __init__(self, api_key, api_host="irctc1.p.rapidapi.com"):
        self.api_key = api_key
        self.api_host = api_host
        self.base_url = f"https://{api_host}/api/v3"

    def _headers(self):
        return {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.api_host,
            "Content-Type": "application/json"
        }

    def test_connection(self):
        try:
            url = f"{self.base_url}/trainBetweenStations"
            params = {"fromStationCode": "NDLS", "toStationCode": "MMCT", "dateOfJourney": "2026-09-10"}
            resp = requests.get(url, headers=self._headers(), params=params, timeout=15)
            if resp.status_code == 200:
                return {"status": "success", "data": resp.json()}
            return {"status": "error", "message": f"HTTP {resp.status_code}: {resp.text[:300]}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def search_live_trains(self, origin_code, dest_code, journey_date):
        url = f"{self.base_url}/trainBetweenStations"
        params = {
            "fromStationCode": origin_code.upper(),
            "toStationCode": dest_code.upper(),
            "dateOfJourney": journey_date
        }
        try:
            resp = requests.get(url, headers=self._headers(), params=params, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                trains = []
                for item in data.get('data', []):
                    trains.append({
                        "train_number": item.get('train_number'),
                        "train_name": item.get('train_name'),
                        "departure_time": item.get('from_std'),
                        "arrival_time": item.get('to_std'),
                        "duration": item.get('duration'),
                        "running_days": item.get('run_days', []),
                        "classes": item.get('class_type', [])
                    })
                return {"status": "success", "trains": trains}
            return {"status": "error", "message": resp.text[:300]}
        except Exception as e:
            _logger.exception("Error calling live train API: %s", e)
            return {"status": "error", "message": str(e)}

    def check_live_seat_availability(self, train_no, origin_code, dest_code, journey_date, travel_class, quota="GN"):
        url = f"{self.base_url}/checkSeatAvailability"
        params = {
            "trainNo": train_no,
            "fromStationCode": origin_code.upper(),
            "toStationCode": dest_code.upper(),
            "date": journey_date,
            "classType": travel_class.upper(),
            "quota": quota
        }
        try:
            resp = requests.get(url, headers=self._headers(), params=params, timeout=20)
            if resp.status_code == 200:
                data = resp.json().get('data', {})
                return {
                    "status": "success",
                    "train_no": train_no,
                    "class": travel_class,
                    "availability_status": data.get('current_status', 'AVAILABLE'),
                    "seats_count": data.get('availablity_count', 0),
                    "fare": data.get('total_fare', 0.0),
                    "raw_data": data
                }
            return {"status": "error", "message": resp.text[:300]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def check_live_pnr(self, pnr):
        url = f"{self.base_url}/getPNRStatus"
        params = {"pnrNumber": pnr}
        try:
            resp = requests.get(url, headers=self._headers(), params=params, timeout=20)
            if resp.status_code == 200:
                data = resp.json().get('data', {})
                return {
                    "status": "success",
                    "pnr": pnr,
                    "train_no": data.get('train_number'),
                    "train_name": data.get('train_name'),
                    "chart_prepared": data.get('chart_prepared', False),
                    "passengers": data.get('passenger_info', []),
                    "booking_status": data.get('booking_status')
                }
            return {"status": "error", "message": resp.text[:300]}
        except Exception as e:
            return {"status": "error", "message": str(e)}
