import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from server.app import app


class ServerAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_health(self) -> None:
        response = self.client.get("/v1/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertIn("llm_available", body)

    def test_actions(self) -> None:
        response = self.client.get("/v1/actions")
        self.assertEqual(response.status_code, 200)
        self.assertIn("open_app", response.json()["actions"])

    def test_contacts(self) -> None:
        response = self.client.get("/v1/contacts")
        self.assertEqual(response.status_code, 200)
        names = [contact["name"] for contact in response.json()["contacts"]]
        self.assertIn("zaria", names)

    def test_interpret_open_spotify(self) -> None:
        response = self.client.post(
            "/v1/interpret", json={"text": "can you open spotfy for me pls"}
        )
        self.assertEqual(response.status_code, 200)
        decision = response.json()["decision"]
        self.assertEqual(decision["action"], "open_app")
        self.assertEqual(decision["target"], "spotify")

    def test_reminder_parse(self) -> None:
        response = self.client.post(
            "/v1/reminder/parse", json={"text": "remind me on friday to buy groceries"}
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["text"].lower(), "buy groceries")
        self.assertIn("datetime", body)
        self.assertIn("frequency", body)

    def test_route_gui_action_needs_no_network(self) -> None:
        response = self.client.post(
            "/v1/route", json={"text": "whatsapp rohin that i'm running late"}
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["execution"], "gui")
        self.assertEqual(body["decision"]["action"], "send_message")

    def test_route_calendar_is_headless(self) -> None:
        with patch("actions.calendar.check_calendar", return_value="No events"):
            response = self.client.post("/v1/route", json={"text": "what is on my calendar"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["execution"], "headless")
        self.assertEqual(response.json()["decision"]["action"], "check_calendar")


if __name__ == "__main__":
    unittest.main()
