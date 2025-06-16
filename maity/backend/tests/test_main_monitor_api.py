# maity/backend/tests/test_main_monitor_api.py
import unittest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

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

    @patch('maity.backend.main.setup_monitoring_tool_action', new_callable=AsyncMock)
    def test_setup_monitoring_task_success(self, mock_setup_tool_action):
        # Current main.py returns 201 for this endpoint
        mock_setup_tool_action.return_value = "Monitoring task 'AI News' configured with ID: task_123"

        response = self.client.post("/api/monitor/setup", json={
            "topic": "AI News",
            "keywords": "artificial intelligence, machine learning",
            "sources": "web_search",
            "frequency_hours": 12
        })
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
        mock_setup_tool_action.side_effect = ToolError(tool_name="setup_monitoring_tool", message="Mocked Tool Error")
        response = self.client.post("/api/monitor/setup", json={
            "topic": "Fail Test", "keywords": "fail", "sources": "web_search", "frequency_hours": 1
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("Mocked Tool Error", response.json()["detail"])

    @patch('maity.backend.main.setup_monitoring_tool_action', new_callable=AsyncMock)
    def test_setup_monitoring_task_unexpected_exception(self, mock_setup_tool_action):
        mock_setup_tool_action.side_effect = Exception("Unexpected internal error")
        response = self.client.post("/api/monitor/setup", json={
            "topic": "Unexpected", "keywords": "boom", "sources": "web_search", "frequency_hours": 2
        })
        self.assertEqual(response.status_code, 500)
        self.assertIn("Unexpected internal error", response.json()["detail"])

    def test_setup_monitoring_task_invalid_frequency_pydantic(self): # Renamed for clarity
        response = self.client.post("/api/monitor/setup", json={
            "topic": "Low Freq", "keywords": "test", "sources": "web_search", "frequency_hours": 0
        })
        self.assertEqual(response.status_code, 422)

    def test_setup_monitoring_task_missing_topic_pydantic(self): # Added specific test for missing field
        response = self.client.post("/api/monitor/setup", json={
             "keywords": "only keywords", "sources": "web_search", "frequency_hours": 12
        })
        self.assertEqual(response.status_code, 422)
        # Ensure the response detail contains information about the missing 'topic' field
        response_data = response.json()
        self.assertTrue(any("topic" in err.get("loc", []) and "field required" in err.get("msg", "").lower() for err in response_data.get("detail", [])))


    @patch('maity.backend.main.list_monitoring_tasks')
    def test_get_active_monitoring_tasks_success(self, mock_list_tasks_func):
        mock_tasks_data = [
            {"id": "task_123", "topic": "AI News", "frequency_hours": 12, "next_run_time": "2023-01-01T12:00:00Z"}, # next_run -> next_run_time
        ]
        mock_list_tasks_func.return_value = mock_tasks_data
        response = self.client.get("/api/monitor/tasks")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), mock_tasks_data)
        mock_list_tasks_func.assert_called_once()

    @patch('maity.backend.main.list_monitoring_tasks')
    def test_get_active_monitoring_tasks_unexpected_exception(self, mock_list_tasks_func):
        mock_list_tasks_func.side_effect = Exception("DB connection failed")
        response = self.client.get("/api/monitor/tasks")
        self.assertEqual(response.status_code, 500)
        self.assertIn("DB connection failed", response.json()["detail"])

    @patch('maity.backend.main.list_monitoring_tasks') # Added from original prompt
    def test_get_active_monitoring_tasks_empty(self, mock_list_tasks_func): # Added from original prompt
        mock_list_tasks_func.return_value = []
        response = self.client.get("/api/monitor/tasks")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

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
    def test_get_task_monitoring_results_returns_non_list_error_structure(self, mock_get_results_func):
        mock_get_results_func.return_value = {"error": "Corrupted data file"} # type: ignore
        response = self.client.get("/api/monitor/results/task_789")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"error": "Corrupted data file"})

    @patch('maity.backend.main.get_monitoring_results')
    def test_get_task_monitoring_results_unexpected_exception(self, mock_get_results_func):
        mock_get_results_func.side_effect = Exception("File system read error")
        response = self.client.get("/api/monitor/results/task_abc")
        self.assertEqual(response.status_code, 500)
        self.assertIn("File system read error", response.json()["detail"])

    @patch('maity.backend.main.get_monitoring_results') # Added from original prompt
    def test_get_task_monitoring_results_not_found_or_empty(self, mock_get_results_func): # Added from original prompt
        task_id = "task_unknown"
        mock_get_results_func.return_value = []
        response = self.client.get(f"/api/monitor/results/{task_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])


if __name__ == '__main__':
    unittest.main()
