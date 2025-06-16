# maity/backend/tests/test_main_appgen_api.py
import unittest
from unittest.mock import patch, AsyncMock, MagicMock, call # Added call
from fastapi.testclient import TestClient
import json
from collections import defaultdict # For mocking active_appgen_websockets

from maity.backend.main import app

class TestAppGenAPI(unittest.IsolatedAsyncioTestCase): # Changed to IsolatedAsyncioTestCase

    def setUp(self):
        self.client = TestClient(app)

    @patch('maity.backend.main.generate_app_tool_action', new_callable=AsyncMock)
    async def test_start_app_generation_success(self, mock_generate_tool_action):
        mock_generate_tool_action.return_value = "App generation started with Project ID: proj_abc123. Path: /sandbox/appgen_proj_abc123."

        response = self.client.post("/api/app/generate", json={"prompt": "Create a blog app"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["project_id"], "proj_abc123")
        self.assertIn("App generation started", data["initial_message"])
        mock_generate_tool_action.assert_called_once_with(prompt="Create a blog app")

    def test_start_app_generation_empty_prompt(self):
        response = self.client.post("/api/app/generate", json={"prompt": "  "})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Prompt cannot be empty", response.json()["detail"])

    @patch('maity.backend.main.generate_app_tool_action', new_callable=AsyncMock)
    async def test_start_app_generation_tool_exception(self, mock_generate_tool_action):
        try:
            from openai_agents.tool import ToolError
        except ImportError:
            class ToolError(Exception):
                def __init__(self, tool_name, message): self.message = message; self.tool_name = tool_name

        mock_generate_tool_action.side_effect = ToolError(tool_name="generate_app_tool", message="LLM unavailable")

        response = self.client.post("/api/app/generate", json={"prompt": "Trigger tool error"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("LLM unavailable", response.json()["detail"])
        self.assertIn("Tool Error", response.json()["detail"])


    @patch('maity.backend.main.active_appgen_websockets', new_callable=lambda: defaultdict(list))
    def test_websocket_appgen_status_connect_and_disconnect(self, mock_active_websockets_dict):
        # active_appgen_websockets is a global dict in app_generator, imported into main
        # We patch it where it's accessed by the endpoint: maity.backend.main.active_appgen_websockets

        project_id = "proj_ws_test1"

        # Test connection
        with self.client.websocket_connect(f"/ws/appgen/{project_id}") as websocket:
            self.assertIn(project_id, mock_active_websockets_dict)
            self.assertIn(websocket, mock_active_websockets_dict[project_id])

            # Simulate client sending a message (server currently just logs and ignores)
            websocket.send_text("ping from client")
            # No response is expected from server based on current endpoint logic for client messages

        # Test disconnection and cleanup
        self.assertNotIn(websocket, mock_active_websockets_dict.get(project_id, []))
        # The key might still exist if other connections were there, or be deleted if it was the last one.
        # If it was the last one, the key should be deleted.
        if not mock_active_websockets_dict.get(project_id): # Checks if list is empty or key doesn't exist
            self.assertNotIn(project_id, mock_active_websockets_dict)


if __name__ == '__main__':
    unittest.main()
