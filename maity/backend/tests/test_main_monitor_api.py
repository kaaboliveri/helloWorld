# maity/backend/tests/test_main_monitor_api.py
import unittest
from unittest.mock import patch, AsyncMock # AsyncMock for async functions
from fastapi.testclient import TestClient

# Import the FastAPI app instance
from maity.backend.main import app

try:
    from openai_agents.tool import ToolError
except ImportError:
    print("Warning: Could not import ToolError from openai_agents.tool. Using a dummy ToolError for tests.")
    class ToolError(Exception):
        def __init__(self, tool_name, message):
            super().__init__(message)
            self.tool_name = tool_name
            self.message = message

class TestMonitoringAPI(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    # Patching 'setup_monitoring_tool_action' as it's aliased in main.py
    @patch('maity.backend.main.setup_monitoring_tool_action', new_callable=AsyncMock)
    def test_setup_monitoring_task_success(self, mock_setup_tool_action):
        mock_setup_tool_action.return_value = "Monitoring task 'AI News' configured with ID: task_123"

        response = self.client.post("/api/monitor/setup", json={
            "topic": "AI News",
            "keywords": "artificial intelligence, machine learning",
            "sources": "web_search",
            "frequency_hours": 12
        })
        # The endpoint in main.py for setup is setup_new_monitoring_task_endpoint
        # and it returns 201 upon successful creation.
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"message": "Monitoring task 'AI News' configured with ID: task_123"})
        mock_setup_tool_action.assert_called_once_with(
            topic="AI News",
            keywords="artificial intelligence, machine learning",
            sources="web_search",
            frequency_hours=12
        )

    @patch('maity.backend.main.setup_monitoring_tool_action', new_callable=AsyncMock)
    def test_setup_monitoring_task_tool_error(self, mock_setup_tool_action):
        # The actual ToolError is defined in openai_agents.tool
        # The endpoint should catch ToolError and convert it to HTTPException(400)
        mock_setup_tool_action.side_effect = ToolError(tool_name="setup_monitoring_tool", message="Invalid frequency value")

        response = self.client.post("/api/monitor/setup", json={
            "topic": "AI News",
            "keywords": "ai",
            "sources": "web_search", # Added to make the request valid before tool call
            "frequency_hours": 12 # Using a valid value, error comes from mock
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn("Tool Error: Invalid frequency value", response.json()["detail"])

    def test_setup_monitoring_task_invalid_input_pydantic(self):
        response = self.client.post("/api/monitor/setup", json={
            "keywords": "only keywords"
        })
        self.assertEqual(response.status_code, 422)
        self.assertIn("field required", response.text.lower())

    # Patching 'list_monitoring_tasks' as it's imported from tasks and used in main.py
    @patch('maity.backend.main.list_monitoring_tasks')
    def test_get_active_monitoring_tasks_success(self, mock_list_tasks_func):
        mock_tasks_data = [
            {"id": "task_123", "topic": "AI News", "frequency_hours": 12, "next_run": "2023-01-01T12:00:00Z"},
            {"id": "task_456", "topic": "Python Updates", "frequency_hours": 24, "next_run": "2023-01-02T08:00:00Z"}
        ]
        mock_list_tasks_func.return_value = mock_tasks_data

        response = self.client.get("/api/monitor/tasks")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), mock_tasks_data)
        mock_list_tasks_func.assert_called_once()

    @patch('maity.backend.main.list_monitoring_tasks')
    def test_get_active_monitoring_tasks_empty(self, mock_list_tasks_func):
        mock_list_tasks_func.return_value = []
        response = self.client.get("/api/monitor/tasks")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    # Patching 'get_monitoring_results' as it's imported from tasks and used in main.py
    @patch('maity.backend.main.get_monitoring_results')
    def test_get_task_monitoring_results_success(self, mock_get_results_func):
        task_id = "task_123"
        mock_results_data = [
            {"timestamp": "2023-01-01T10:00:00Z", "title": "New AI paper released", "source_url": "http://example.com/ai_paper"}
        ]
        mock_get_results_func.return_value = mock_results_data

        response = self.client.get(f"/api/monitor/results/{task_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), mock_results_data)
        mock_get_results_func.assert_called_once_with(task_id)

    @patch('maity.backend.main.get_monitoring_results')
    def test_get_task_monitoring_results_not_found_or_empty(self, mock_get_results_func):
        task_id = "task_unknown"
        mock_get_results_func.return_value = []

        response = self.client.get(f"/api/monitor/results/{task_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

if __name__ == '__main__':
    unittest.main()
