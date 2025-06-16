# maity/backend/tests/test_main_chat_api.py
import unittest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
import json # For WebSocket messages

from maity.backend.main import app

class TestChatAPI(unittest.IsolatedAsyncioTestCase): # Changed to IsolatedAsyncioTestCase

    def setUp(self):
        self.client = TestClient(app)
        # Mock WebSocket globally for all tests in this class if App establishes it on load
        # For more granular control, mock it per test or within specific test contexts
        self.ws_patcher = patch('maity.backend.main.WebSocket') # Path to WebSocket if used by main.py
        self.MockWebSocket = self.ws_patcher.start()

        # Define a reusable mock instance for WebSocket connections
        self.mock_ws_instance = MagicMock()
        self.mock_ws_instance.accept = AsyncMock()
        self.mock_ws_instance.receive_text = AsyncMock()
        self.mock_ws_instance.send_text = AsyncMock()
        self.mock_ws_instance.close = AsyncMock()
        # self.client.websocket_connect uses the actual WebSocket, so we need to mock how TestClient gets it,
        # or ensure that TestClient itself uses the mocked global WebSocket.
        # TestClient's websocket_connect will likely try to use the real WebSocket.
        # A more robust approach for testing WebSockets might involve a different setup or library,
        # or deeper patching of starlette's WebSocket.
        # For now, the global mock might not be fully effective with TestClient's websocket_connect.
        # The provided tests use client.websocket_connect, which is fine.
        # The global mock helps if App component itself tries to initiate WebSocket.

    def tearDown(self):
        self.ws_patcher.stop()

    @patch('maity.backend.main.get_maity_agent', new_callable=AsyncMock) # Corrected to AsyncMock
    async def test_chat_endpoint_success(self, mock_get_agent):
        mock_agent_instance = AsyncMock() # Make the instance async
        mock_agent_instance.handle_message.return_value = {
            "content": "Hello from mock Maity!",
            "conversation_id": "conv_123",
            "error": False,
            "debug_info": {}
        }
        # mock_get_agent is already an AsyncMock, its return_value should be awaitable if get_maity_agent is async
        # If get_maity_agent itself is async, its mock needs to handle await.
        # The dependency `agent: MaityAgent = Depends(get_maity_agent)` implies get_maity_agent is called.
        # If get_maity_agent is an async def, then mock_get_agent.return_value = mock_agent_instance is fine.
        # If get_maity_agent is a sync def but returns an awaitable (less common for Depends), then different.
        # Assuming get_maity_agent is async def as per `await get_maity_agent` in main.py
        mock_get_agent.return_value = mock_agent_instance

        response = self.client.post("/api/chat", json={
            "message": "Hi there!",
            "conversation_id": "conv_123"
            # "config" is optional, so preferred_model will be None
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["content"], "Hello from mock Maity!")
        self.assertEqual(data["conversation_id"], "conv_123")
        mock_agent_instance.handle_message.assert_called_once_with(
            message="Hi there!",
            preferred_model=None
        )

    def test_chat_endpoint_empty_message(self):
        response = self.client.post("/api/chat", json={"message": ""})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Message cannot be empty", response.json()["detail"])

    @patch('maity.backend.main.get_maity_agent', new_callable=AsyncMock)
    async def test_chat_endpoint_agent_exception(self, mock_get_agent):
        mock_agent_instance = AsyncMock()
        mock_agent_instance.handle_message.side_effect = Exception("Agent internal error")
        mock_agent_instance.conversation_id = "conv_err_123" # Ensure instance has this attribute
        mock_get_agent.return_value = mock_agent_instance

        response = self.client.post("/api/chat", json={
            "message": "Trigger error",
            "conversation_id": "conv_err_123"
        })
        self.assertEqual(response.status_code, 200) # Endpoint returns 200 but with error=True
        data = response.json()
        self.assertTrue(data["error"])
        # The content in main.py's exception handler is f"An internal server error occurred: {str(e)}"
        self.assertIn("An internal server error occurred: Agent internal error", data["content"])
        self.assertEqual(data["conversation_id"], "conv_err_123")

    @patch('maity.backend.main.get_maity_agent', new_callable=AsyncMock)
    def test_websocket_chat_endpoint(self, mock_get_agent_ws):
        mock_agent_instance_ws = AsyncMock()
        # Ensure the return value of handle_message matches ChatResponse model expectations
        mock_agent_instance_ws.handle_message.return_value = {
            "content": "WS Echo: Hello",
            "conversation_id": "ws_conv_123", # Should match the conversation_id in the URL for consistency
            "error": False,
            "debug_info": {"model_used": "test_model"}
        }
        # get_maity_agent is async, so its mock should reflect that when called by endpoint
        mock_get_agent_ws.return_value = mock_agent_instance_ws


        conversation_id = "ws_conv_123"
        with self.client.websocket_connect(f"/ws/chat/{conversation_id}") as websocket:
            websocket.send_text(json.dumps({"message": "Hello"}))

            # First message from server: status update
            response_status = websocket.receive_json()
            self.assertEqual(response_status["type"], "status")
            self.assertEqual(response_status["content"], "Agent processing...")

            # Second message from server: actual agent response
            response_final = websocket.receive_json()
            self.assertEqual(response_final["type"], "final_response")
            self.assertEqual(response_final["content"], "WS Echo: Hello")
            self.assertEqual(response_final["conversation_id"], conversation_id)
            self.assertFalse(response_final["error"])
            self.assertIsNotNone(response_final["debug_info"])
            self.assertEqual(response_final["debug_info"]["model_used"], "test_model")

            mock_agent_instance_ws.handle_message.assert_called_once_with(
                message="Hello", preferred_model=None
            )

if __name__ == '__main__':
    unittest.main()
