# maity/backend/tests/tools/test_local_system.py
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import os # For os.sep

# Assuming openai_agents.tool.ToolError is the correct path
# If not, adjust the import path for ToolError
try:
    from openai_agents.tool import ToolError
except ImportError:
    # Define a dummy ToolError if the real one isn't easily importable in test environment
    # This is not ideal but can help run tests.
    print("Warning: Could not import ToolError from openai_agents.tool. Using a dummy ToolError for tests.")
    class ToolError(Exception):
        def __init__(self, tool_name, message):
            super().__init__(message)
            self.tool_name = tool_name
            self.message = message

# We need to import the function to be tested.
# This requires careful handling of Python's import system, especially with relative imports.
# If 'maity' is the root package recognized by the test runner:
from maity.backend.app.tools.local_system import _resolve_sandbox_path
# We also need to mock the config values used by the function
# from maity.backend.app import config # This would load the actual config

class TestResolveSandboxPath(unittest.TestCase):

    @patch('maity.backend.app.tools.local_system.config') # Mock the config module used by local_system.py
    def test_valid_path_within_sandbox(self, mock_config):
        mock_config.LOCAL_SANDBOX_DIR = "/tmp/maity_test_sandbox"
        sandbox_root = Path(mock_config.LOCAL_SANDBOX_DIR)
        # Ensure sandbox exists for test - resolve() might fail if path doesn't exist
        sandbox_root.mkdir(parents=True, exist_ok=True)

        user_path = "some_project/file.txt"
        # Ensure parent of expected_path also exists for resolve() to work consistently
        (sandbox_root / "some_project").mkdir(parents=True, exist_ok=True)
        expected_path = (sandbox_root / user_path).resolve()

        resolved_path = _resolve_sandbox_path(user_path)
        self.assertEqual(resolved_path, expected_path)

    @patch('maity.backend.app.tools.local_system.config')
    def test_valid_path_at_sandbox_root(self, mock_config):
        mock_config.LOCAL_SANDBOX_DIR = "/tmp/maity_test_sandbox"
        sandbox_root = Path(mock_config.LOCAL_SANDBOX_DIR)
        sandbox_root.mkdir(parents=True, exist_ok=True)

        user_path = "file_at_root.txt"
        expected_path = (sandbox_root / user_path).resolve()
        resolved_path = _resolve_sandbox_path(user_path)
        self.assertEqual(resolved_path, expected_path)

    @patch('maity.backend.app.tools.local_system.config')
    def test_dot_path_resolves_to_sandbox_root_itself(self, mock_config):
        mock_config.LOCAL_SANDBOX_DIR = "/tmp/maity_test_sandbox"
        sandbox_root = Path(mock_config.LOCAL_SANDBOX_DIR)
        sandbox_root.mkdir(parents=True, exist_ok=True)

        expected_path = sandbox_root.resolve()
        # _resolve_sandbox_path was modified to handle "." correctly in a previous step
        resolved_path = _resolve_sandbox_path(".")
        self.assertEqual(resolved_path, expected_path)


    @patch('maity.backend.app.tools.local_system.config')
    def test_path_traversal_attempt_raises_error(self, mock_config):
        mock_config.LOCAL_SANDBOX_DIR = "/tmp/maity_test_sandbox"
        sandbox_root = Path(mock_config.LOCAL_SANDBOX_DIR)
        sandbox_root.mkdir(parents=True, exist_ok=True)

        user_path = f"..{os.sep}..{os.sep}..{os.sep}etc{os.sep}passwd" # Path traversal attempt
        with self.assertRaises(ToolError) as context:
            _resolve_sandbox_path(user_path)
        # The exact resolved path in the error message can be tricky due to how resolve() works.
        # Let's check for the key part of the message.
        self.assertIn("is outside the allowed sandbox", str(context.exception))
        self.assertIn(user_path.replace(f"..{os.sep}", ""), str(context.exception).replace(f"..{os.sep}", "")) # Check the problematic part


    @patch('maity.backend.app.tools.local_system.config')
    def test_absolute_path_attempt_outside_sandbox_raises_error(self, mock_config):
        # This test clarifies behavior when user_path is an absolute path.
        # The function prepends sandbox_root, so an absolute user_path becomes
        # sandbox_root / absolute_user_path.
        # If this resulting path resolves outside sandbox_root (which it will if user_path is truly absolute like /etc/passwd),
        # it should be caught.
        mock_config.LOCAL_SANDBOX_DIR = "/tmp/maity_test_sandbox"
        sandbox_root = Path(mock_config.LOCAL_SANDBOX_DIR)
        sandbox_root.mkdir(parents=True, exist_ok=True)

        user_path_abs = "/etc/shadow" # An absolute path

        with self.assertRaises(ToolError) as context:
            _resolve_sandbox_path(user_path_abs)
        self.assertIn(f"Path '{user_path_abs}' is outside the allowed sandbox", str(context.exception))


    @patch('maity.backend.app.tools.local_system.config')
    def test_empty_path_resolves_to_sandbox_root(self, mock_config):
        mock_config.LOCAL_SANDBOX_DIR = "/tmp/maity_test_sandbox"
        sandbox_root = Path(mock_config.LOCAL_SANDBOX_DIR)
        sandbox_root.mkdir(parents=True, exist_ok=True)

        expected_path = sandbox_root.resolve()
        # _resolve_sandbox_path was modified to handle "" by making it sandbox_root / "" -> sandbox_root
        resolved_path = _resolve_sandbox_path("")
        self.assertEqual(resolved_path, expected_path)

    # No explicit tearDown needed if using /tmp and OS handles cleanup,
    # or if each test ensures its specific paths are managed within the mock sandbox.
    # For more complex file operations, tempfile.TemporaryDirectory would be good.

if __name__ == '__main__':
    unittest.main()
