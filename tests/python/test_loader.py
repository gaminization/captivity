import unittest
from unittest.mock import MagicMock, patch
from captivity.plugins.loader import (
    discover_plugins,
    _load_user_plugins,
    select_plugin,
)


class TestLoader(unittest.TestCase):
    @patch("captivity.plugins.loader._load_class")
    @patch("captivity.plugins.loader._load_user_plugins")
    @patch("importlib.metadata.entry_points")
    def test_discover_plugins(self, mock_ep, mock_load_user, mock_load_class):
        mock_load_user.return_value = []

        # Test built-in failure
        mock_load_class.side_effect = Exception("failed")

        # Test entry points dict format
        mock_ep.return_value = {"captivity.plugins": []}

        plugins = discover_plugins()
        self.assertEqual(len(plugins), 0)

        # Test entry points select format
        mock_ep_obj = MagicMock()
        mock_ep_obj.select.return_value = []
        mock_ep.return_value = mock_ep_obj
        discover_plugins()

    @patch("captivity.plugins.loader._user_plugin_dir")
    def test_load_user_plugins(self, mock_dir):
        mock_path = MagicMock()
        mock_path.is_dir.return_value = False
        mock_dir.return_value = mock_path
        self.assertEqual(_load_user_plugins(), [])

        mock_path.is_dir.return_value = True
        mock_py = MagicMock()
        mock_py.name = "test.py"
        mock_py.stem = "test"
        mock_path.glob.return_value = [mock_py]

        with patch("importlib.util.spec_from_file_location") as mock_spec:
            mock_spec.return_value = None
            self.assertEqual(_load_user_plugins(), [])

    def test_select_plugin(self):
        plugin = MagicMock()
        plugin.detect.return_value = True
        self.assertEqual(select_plugin(None, [plugin]), plugin)

        plugin.detect.side_effect = Exception("error")
        self.assertIsNone(select_plugin(None, [plugin]))


if __name__ == "__main__":
    unittest.main()

    @patch("captivity.plugins.loader._user_plugin_dir")
    def test_load_user_plugins_exceptions(self, mock_dir):
        mock_path = MagicMock()
        mock_path.is_dir.return_value = True
        mock_dir.return_value = mock_path

        mock_py = MagicMock()
        mock_py.name = "test.py"
        mock_py.stem = "test"
        mock_path.glob.return_value = [mock_py]

        with patch("importlib.util.spec_from_file_location") as mock_spec:
            mock_spec.side_effect = Exception("failed to load spec")
            self.assertEqual(_load_user_plugins(), [])

        with patch("importlib.util.spec_from_file_location") as mock_spec:
            mock_spec_obj = MagicMock()
            mock_spec_obj.loader = None
            mock_spec.return_value = mock_spec_obj
            self.assertEqual(_load_user_plugins(), [])
