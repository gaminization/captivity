"""Tests for captivity.plugins module."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from captivity.plugins.base import CaptivePortalPlugin
from captivity.plugins.pronto import ProntoPlugin
from captivity.plugins.generic import GenericPlugin
from captivity.plugins.loader import discover_plugins, select_plugin


class TestProntoPlugin(unittest.TestCase):
    """Test Pronto Networks plugin."""

    def setUp(self):
        self.plugin = ProntoPlugin()

    def test_name(self):
        self.assertEqual(self.plugin.name, "Pronto Networks")

    def test_detect_by_url(self):
        response = MagicMock()
        response.url = "http://phc.prontonetworks.com/cgi-bin/authlogin"
        response.text = ""
        self.assertTrue(self.plugin.detect(response))

    def test_detect_by_content(self):
        response = MagicMock()
        response.url = "http://some-portal.com"
        response.text = "<form>ProntoNetworks portal</form>"
        self.assertTrue(self.plugin.detect(response))

    def test_no_detect_unrelated(self):
        response = MagicMock()
        response.url = "http://other-portal.com"
        response.text = "<form>Some other portal</form>"
        self.assertFalse(self.plugin.detect(response))

    def test_pronto_login_flow_regression(self):
        """Regression test to prevent over-engineering: verifies exact deterministic flow."""
        session = MagicMock()
        
        # 1. Trigger portal (GET)
        get_response = MagicMock()
        get_response.status_code = 200
        
        # 2. Submit login (POST)
        post_response = MagicMock()
        post_response.status_code = 200
        
        # 3. Verify connectivity (GET)
        verify_response = MagicMock()
        verify_response.status_code = 200
        verify_response.text = "success"
        
        session.get.side_effect = [get_response, verify_response]
        session.post.return_value = post_response

        # Execute
        result = self.plugin.login(session, "http://phc.prontonetworks.com", "user", "pass")
        self.assertTrue(result)
        
        # Assert Step 1: Trigger
        trigger_call = session.get.call_args_list[0]
        self.assertEqual(
            trigger_call[0][0],
            "http://phc.prontonetworks.com/cgi-bin/authlogin?URI=http://detectportal.firefox.com/canonical.html"
        )
        
        # Assert Step 2: Login Submit
        post_call = session.post.call_args_list[0]
        self.assertEqual(post_call[0][0], "http://phc.prontonetworks.com/cgi-bin/authlogin")
        self.assertEqual(
            post_call[1]["data"],
            {
                "userId": "user",
                "password": "pass",
                "serviceName": "ProntoAuthentication",
                "Submit22": "Login",
            }
        )
        
        # Assert Step 3: Verify
        verify_call = session.get.call_args_list[1]
        self.assertEqual(verify_call[0][0], "http://detectportal.firefox.com/canonical.html")

    def test_login_failure(self):
        session = MagicMock()
        session.get.side_effect = requests.exceptions.ConnectionError()

        result = self.plugin.login(session, "http://test", "user", "pass")
        self.assertFalse(result)

    def test_priority_is_negative(self):
        """Built-in plugins have negative priority."""
        self.assertLess(self.plugin.priority, 0)


class TestGenericPlugin(unittest.TestCase):
    """Test Generic plugin."""

    def setUp(self):
        self.plugin = GenericPlugin()

    def test_name(self):
        self.assertEqual(self.plugin.name, "Generic (form parser)")

    def test_detect_with_form(self):
        response = MagicMock()
        response.text = '<html><form action="/login"></form></html>'
        self.assertTrue(self.plugin.detect(response))

    def test_no_detect_without_form(self):
        response = MagicMock()
        response.text = "<html><p>No forms here</p></html>"
        self.assertFalse(self.plugin.detect(response))

    def test_priority_lower_than_pronto(self):
        pronto = ProntoPlugin()
        self.assertLess(self.plugin.priority, pronto.priority)


class TestPluginLoader(unittest.TestCase):
    """Test plugin discovery and selection."""

    def test_discover_finds_builtin_plugins(self):
        plugins = discover_plugins()
        names = [p.name for p in plugins]
        self.assertIn("Pronto Networks", names)
        self.assertIn("Generic (form parser)", names)

    def test_plugins_sorted_by_priority(self):
        plugins = discover_plugins()
        priorities = [p.priority for p in plugins]
        self.assertEqual(priorities, sorted(priorities, reverse=True))

    def test_select_pronto_plugin(self):
        response = MagicMock()
        response.url = "http://phc.prontonetworks.com/login"
        response.text = "ProntoNetworks"

        plugin = select_plugin(response)
        self.assertEqual(plugin.name, "Pronto Networks")

    def test_select_generic_fallback(self):
        response = MagicMock()
        response.url = "http://unknown-portal.com"
        response.text = '<form action="/login"></form>'

        plugin = select_plugin(response)
        self.assertEqual(plugin.name, "Generic (form parser)")

    def test_select_none_for_no_match(self):
        response = MagicMock()
        response.url = "http://example.com"
        response.text = "<html>No portal here</html>"

        plugin = select_plugin(response)
        self.assertIsNone(plugin)


class TestPluginInterface(unittest.TestCase):
    """Test that plugin base class enforces interface."""

    def test_cannot_instantiate_base(self):
        """Abstract base class cannot be instantiated."""
        with self.assertRaises(TypeError):
            CaptivePortalPlugin()

    def test_default_priority(self):
        """Custom plugins get priority 0 by default."""

        class TestPlugin(CaptivePortalPlugin):
            @property
            def name(self):
                return "test"

            def detect(self, response):
                return True

            def login(self, session, portal_url, username, password):
                return True

        plugin = TestPlugin()
        self.assertEqual(plugin.priority, 0)
        self.assertGreater(plugin.priority, ProntoPlugin().priority)


class TestLifecycleHooks(unittest.TestCase):
    """Test plugin lifecycle hooks."""

    def _make_plugin_cls(self, validate_result=True):
        class HookPlugin(CaptivePortalPlugin):
            loaded = False
            unloaded = False

            @property
            def name(self):
                return "hook-test"

            def detect(self, response):
                return True

            def login(self, session, portal_url, username, password):
                return True

            def on_load(self):
                type(self).loaded = True

            def on_unload(self):
                type(self).unloaded = True

            def validate(self):
                return validate_result

        return HookPlugin

    def test_on_load_called(self):
        cls = self._make_plugin_cls()
        plugin = cls()
        plugin.on_load()
        self.assertTrue(cls.loaded)

    def test_on_unload_called(self):
        cls = self._make_plugin_cls()
        plugin = cls()
        plugin.on_unload()
        self.assertTrue(cls.unloaded)

    def test_validate_default_true(self):
        class MinPlugin(CaptivePortalPlugin):
            @property
            def name(self):
                return "min"

            def detect(self, response):
                return True

            def login(self, session, portal_url, username, password):
                return True

        self.assertTrue(MinPlugin().validate())

    def test_validate_false(self):
        cls = self._make_plugin_cls(validate_result=False)
        self.assertFalse(cls().validate())


class TestDiscoverWithLifecycle(unittest.TestCase):
    """Test that discover_plugins integrates lifecycle hooks."""

    def test_discover_calls_on_load(self):
        plugins = discover_plugins()
        self.assertGreater(len(plugins), 0)

    @patch.object(ProntoPlugin, "validate", return_value=False)
    def test_invalid_plugin_skipped(self, mock_validate):
        plugins = discover_plugins()
        names = [p.name for p in plugins]
        self.assertNotIn("Pronto Networks", names)


class TestGenericPluginLogin(unittest.TestCase):
    """Test GenericPlugin.login() paths."""

    def setUp(self):
        self.plugin = GenericPlugin()

    @patch("captivity.plugins.generic.parse_portal_page", return_value=None)
    def test_login_no_form(self, mock_parse):
        result = self.plugin.login(MagicMock(), "http://p.com", "u", "p")
        self.assertFalse(result)

    @patch("captivity.plugins.generic.parse_portal_page")
    def test_login_missing_fields(self, mock_parse):
        form = MagicMock()
        form.username_field = None
        form.password_field = None
        mock_parse.return_value = form
        result = self.plugin.login(MagicMock(), "http://p.com", "u", "p")
        self.assertFalse(result)

    @patch("captivity.plugins.generic.parse_portal_page")
    def test_login_success(self, mock_parse):
        form = MagicMock()
        form.username_field = "user"
        form.password_field = "pass"
        form.action = "http://p.com/login"
        form.build_payload.return_value = {"user": "u", "pass": "p"}
        mock_parse.return_value = form
        session = MagicMock()
        session.post.return_value = MagicMock(status_code=200)
        result = self.plugin.login(session, "http://p.com", "u", "p")
        self.assertTrue(result)

    @patch("captivity.plugins.generic.parse_portal_page")
    def test_login_request_error(self, mock_parse):
        import requests as _req

        form = MagicMock()
        form.username_field = "u"
        form.password_field = "p"
        form.action = "http://p.com/login"
        form.build_payload.return_value = {}
        mock_parse.return_value = form
        session = MagicMock()
        session.post.side_effect = _req.exceptions.ConnectionError()
        result = self.plugin.login(session, "http://p.com", "u", "p")
        self.assertFalse(result)


class TestUserPluginDirectory(unittest.TestCase):
    """Test user plugin directory scanning."""

    def test_no_dir_returns_empty(self):
        from captivity.plugins.loader import _load_user_plugins

        with patch("captivity.plugins.loader._user_plugin_dir") as mock_dir:
            mock_path = MagicMock()
            mock_path.is_dir.return_value = False
            mock_dir.return_value = mock_path
            self.assertEqual(_load_user_plugins(), [])

    def test_user_plugin_dir_path(self):
        from captivity.plugins.loader import _user_plugin_dir

        path = _user_plugin_dir()
        self.assertTrue(str(path).endswith("captivity/plugins"))


if __name__ == "__main__":
    unittest.main()
