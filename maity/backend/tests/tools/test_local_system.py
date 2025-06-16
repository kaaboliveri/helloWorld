# maity/backend/tests/tools/test_local_system.py
import unittest
from unittest.mock import patch, MagicMock, mock_open, call # Added mock_open and call
import os
from pathlib import Path

try:
    from openai_agents.tool import ToolError
except ImportError:
    print("Warning: Could not import ToolError from openai_agents.tool. Using a dummy ToolError for tests.")
    class ToolError(Exception):
        def __init__(self, tool_name, message):
            super().__init__(message)
            self.tool_name = tool_name
            self.message = message

from maity.backend.app.tools.local_system import (
    _resolve_sandbox_path,
    list_files_tool,
    read_file_tool,
    write_file_tool
)

class TestResolveSandboxPath(unittest.TestCase):
    @patch('maity.backend.app.tools.local_system.config')
    def test_valid_path_within_sandbox(self, mock_config):
        mock_config.LOCAL_SANDBOX_DIR = "/tmp/maity_test_sandbox_resolve" # Unique dir for this test class
        sandbox_root = Path(mock_config.LOCAL_SANDBOX_DIR)
        sandbox_root.mkdir(parents=True, exist_ok=True)
        user_path_dir = sandbox_root / "some_project" # Create intermediate dir for resolve()
        user_path_dir.mkdir(parents=True, exist_ok=True)

        user_path = "some_project/file.txt"
        expected_path = (sandbox_root / user_path).resolve()
        resolved_path = _resolve_sandbox_path(user_path)
        self.assertEqual(resolved_path, expected_path)

    @patch('maity.backend.app.tools.local_system.config')
    def test_valid_path_at_sandbox_root(self, mock_config):
        mock_config.LOCAL_SANDBOX_DIR = "/tmp/maity_test_sandbox_resolve"
        sandbox_root = Path(mock_config.LOCAL_SANDBOX_DIR)
        sandbox_root.mkdir(parents=True, exist_ok=True)
        user_path = "file_at_root.txt"
        expected_path = (sandbox_root / user_path).resolve()
        resolved_path = _resolve_sandbox_path(user_path)
        self.assertEqual(resolved_path, expected_path)

    @patch('maity.backend.app.tools.local_system.config')
    def test_dot_path_resolves_to_sandbox_root_itself(self, mock_config):
        mock_config.LOCAL_SANDBOX_DIR = "/tmp/maity_test_sandbox_resolve"
        sandbox_root = Path(mock_config.LOCAL_SANDBOX_DIR)
        sandbox_root.mkdir(parents=True, exist_ok=True)
        expected_path = sandbox_root.resolve()
        resolved_path = _resolve_sandbox_path(".")
        self.assertEqual(resolved_path, expected_path)

    @patch('maity.backend.app.tools.local_system.config')
    def test_path_traversal_attempt_raises_error(self, mock_config):
        mock_config.LOCAL_SANDBOX_DIR = "/tmp/maity_test_sandbox_resolve"
        sandbox_root = Path(mock_config.LOCAL_SANDBOX_DIR)
        sandbox_root.mkdir(parents=True, exist_ok=True)
        user_path = f"..{os.sep}..{os.sep}..{os.sep}etc{os.sep}passwd"
        with self.assertRaises(ToolError) as context:
            _resolve_sandbox_path(user_path)
        # Check parts of the message as resolve() behavior on non-existent paths can vary
        self.assertIn("is outside the allowed sandbox", str(context.exception))
        # Check that the reported path in error message is related to the input user_path
        self.assertTrue(any(part in str(context.exception) for part in ["etc/passwd", f"etc{os.sep}passwd"]))


    @patch('maity.backend.app.tools.local_system.config')
    def test_absolute_path_attempt_outside_sandbox_raises_error(self, mock_config):
        mock_config.LOCAL_SANDBOX_DIR = "/tmp/maity_test_sandbox_resolve"
        sandbox_root = Path(mock_config.LOCAL_SANDBOX_DIR)
        sandbox_root.mkdir(parents=True, exist_ok=True)
        user_path_abs = "/etc/shadow"
        with self.assertRaises(ToolError) as context:
            _resolve_sandbox_path(user_path_abs)
        self.assertIn(f"Path '{user_path_abs}' is outside the allowed sandbox", str(context.exception))

    @patch('maity.backend.app.tools.local_system.config')
    def test_empty_path_resolves_to_sandbox_root(self, mock_config):
        mock_config.LOCAL_SANDBOX_DIR = "/tmp/maity_test_sandbox_resolve"
        sandbox_root = Path(mock_config.LOCAL_SANDBOX_DIR)
        sandbox_root.mkdir(parents=True, exist_ok=True)
        expected_path = sandbox_root.resolve()
        resolved_path = _resolve_sandbox_path("")
        self.assertEqual(resolved_path, expected_path)

class TestFileOperationTools(unittest.IsolatedAsyncioTestCase): # Use IsolatedAsyncioTestCase for async def test_ methods

    def setUp(self):
        self.mock_sandbox_path_str = "/tmp/maity_test_sandbox_files"
        # No actual directory creation here for most tests, Path objects will be mocked.

    @patch('maity.backend.app.tools.local_system.Path')
    @patch('maity.backend.app.tools.local_system.config')
    async def test_list_files_tool_success(self, mock_config, mock_Path_constructor):
        mock_config.LOCAL_SANDBOX_DIR = self.mock_sandbox_path_str

        mock_sandbox_root_obj = MagicMock(spec=Path) # Returned by Path(config.LOCAL_SANDBOX_DIR)
        mock_target_dir_obj = MagicMock(spec=Path)   # Returned by (sandbox_root / user_path).resolve()

        mock_Path_constructor.side_effect = lambda p: mock_sandbox_root_obj if p == self.mock_sandbox_path_str else MagicMock(spec=Path)

        mock_sandbox_root_obj.__truediv__.return_value.resolve.return_value = mock_target_dir_obj
        mock_sandbox_root_obj.resolve.return_value = mock_sandbox_root_obj # For Path(config.LOCAL_SANDBOX_DIR).resolve()

        mock_target_dir_obj.is_dir.return_value = True
        mock_target_dir_obj.resolve.return_value = mock_target_dir_obj # Resolve returns self
        # Ensure the parents check passes in _resolve_sandbox_path
        # The direct parent of mock_target_dir_obj should be mock_sandbox_root_obj
        mock_target_dir_obj.parent = mock_sandbox_root_obj
        # The list of parents for mock_target_dir_obj should include mock_sandbox_root_obj
        mock_target_dir_obj.parents = [mock_sandbox_root_obj, Path("/tmp")] # Example parent list


        mock_file1 = MagicMock(spec=Path); mock_file1.name = "file1.txt"; mock_file1.is_dir.return_value = False
        mock_dir1 = MagicMock(spec=Path); mock_dir1.name = "subdir"; mock_dir1.is_dir.return_value = True
        mock_target_dir_obj.iterdir.return_value = [mock_file1, mock_dir1]

        user_dir_to_list = "test_dir"
        result = await list_files_tool(user_dir_to_list)

        self.assertIn("file1.txt", result)
        self.assertIn("subdir/", result)
        mock_target_dir_obj.is_dir.assert_called_once()
        mock_target_dir_obj.iterdir.assert_called_once()
        # Check if __truediv__ was called on mock_sandbox_root_obj with user_dir_to_list
        mock_sandbox_root_obj.__truediv__.assert_called_with(user_dir_to_list)


    @patch('maity.backend.app.tools.local_system._resolve_sandbox_path')
    @patch('maity.backend.app.tools.local_system.config')
    async def test_list_files_tool_not_a_directory(self, mock_ls_config, mock_resolve):
        mock_ls_config.LOCAL_SANDBOX_DIR = self.mock_sandbox_path_str # Not directly used if _resolve_sandbox_path is mocked

        mock_resolved_target_path = MagicMock(spec=Path)
        mock_resolved_target_path.is_dir.return_value = False
        mock_resolve.return_value = mock_resolved_target_path

        with self.assertRaisesRegex(ToolError, "not a valid directory"): # Use assertRaisesRegex for message part
            await list_files_tool("not_a_dir.txt")

    @patch('maity.backend.app.tools.local_system._resolve_sandbox_path')
    @patch('maity.backend.app.tools.local_system.config')
    async def test_read_file_tool_success(self, mock_rf_config, mock_resolve):
        mock_rf_config.LOCAL_SANDBOX_DIR = self.mock_sandbox_path_str

        mock_file_content = "Hello, Maity!"
        mock_resolved_file_path = MagicMock(spec=Path)
        mock_resolved_file_path.is_file.return_value = True
        mock_resolved_file_path.stat.return_value.st_size = len(mock_file_content)
        mock_resolved_file_path.read_text.return_value = mock_file_content
        mock_resolve.return_value = mock_resolved_file_path

        result = await read_file_tool("test_file.txt")
        self.assertEqual(result, mock_file_content)
        mock_resolved_file_path.read_text.assert_called_once_with(encoding='utf-8')

    @patch('maity.backend.app.tools.local_system._resolve_sandbox_path')
    @patch('maity.backend.app.tools.local_system.config')
    async def test_read_file_tool_too_large(self, mock_rf_config, mock_resolve):
        mock_rf_config.LOCAL_SANDBOX_DIR = self.mock_sandbox_path_str
        mock_resolved_file_path = MagicMock(spec=Path)
        mock_resolved_file_path.is_file.return_value = True
        mock_resolved_file_path.stat.return_value.st_size = (1024 * 1024) + 1
        mock_resolve.return_value = mock_resolved_file_path

        with self.assertRaisesRegex(ToolError, "too large"):
            await read_file_tool("large_file.txt")

    @patch('maity.backend.app.tools.local_system._needs_confirmation')
    @patch('maity.backend.app.tools.local_system._resolve_sandbox_path')
    @patch('maity.backend.app.tools.local_system.config')
    async def test_write_file_tool_success(self, mock_wf_config, mock_resolve, mock_needs_confirm):
        mock_wf_config.LOCAL_SANDBOX_DIR = self.mock_sandbox_path_str
        mock_wf_config.REQUIRE_CONFIRMATION_LOCAL = False
        mock_needs_confirm.return_value = True

        mock_resolved_file_path = MagicMock(spec=Path)
        mock_parent_dir = MagicMock(spec=Path)
        mock_resolved_file_path.parent = mock_parent_dir
        mock_resolve.return_value = mock_resolved_file_path

        file_content = "Content to write."
        result = await write_file_tool("output.txt", file_content)

        mock_parent_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_resolved_file_path.write_text.assert_called_once_with(file_content, encoding='utf-8')
        self.assertIn("Successfully wrote content", result)

    @patch('maity.backend.app.tools.local_system._needs_confirmation')
    @patch('maity.backend.app.tools.local_system._resolve_sandbox_path') # Mock to prevent its Path usage
    @patch('maity.backend.app.tools.local_system.config')
    async def test_write_file_tool_confirmation_denied(self, mock_wf_config, mock_resolve, mock_needs_confirm):
        mock_wf_config.LOCAL_SANDBOX_DIR = self.mock_sandbox_path_str
        mock_wf_config.REQUIRE_CONFIRMATION_LOCAL = True
        mock_needs_confirm.return_value = False

        mock_resolve.return_value = MagicMock(spec=Path) # Needs to return a mock Path for the tool

        with self.assertRaisesRegex(ToolError, "Action denied by user confirmation"):
            await write_file_tool("output.txt", "some content")
        mock_needs_confirm.assert_called_once()

if __name__ == '__main__':
    unittest.main()
