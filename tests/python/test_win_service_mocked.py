import sys
import unittest
from unittest.mock import MagicMock, patch
import importlib

class TestMockedWinService(unittest.TestCase):
    def setUp(self):
        # Mock the win32 modules
        self.mock_win32serviceutil = MagicMock()
        self.mock_win32service = MagicMock()
        self.mock_win32event = MagicMock()
        
        # ServiceFramework needs to be a class we can inherit from
        class MockServiceFramework:
            def __init__(self, args):
                pass
            def ReportServiceStatus(self, status):
                pass
        self.mock_win32serviceutil.ServiceFramework = MockServiceFramework
        
        sys.modules['win32serviceutil'] = self.mock_win32serviceutil
        sys.modules['win32service'] = self.mock_win32service
        sys.modules['win32event'] = self.mock_win32event

    def tearDown(self):
        sys.modules.pop('win32serviceutil', None)
        sys.modules.pop('win32service', None)
        sys.modules.pop('win32event', None)
        import captivity.daemon.win_service
        # Restore normal state
        importlib.reload(captivity.daemon.win_service)

    @patch('captivity.daemon.runner.DaemonRunner')
    def test_service_lifecycle(self, mock_runner_class):
        import captivity.daemon.win_service
        importlib.reload(captivity.daemon.win_service)
        
        self.assertTrue(captivity.daemon.win_service._WIN32_AVAILABLE)
        
        # Instantiate the service
        svc = captivity.daemon.win_service.CaptivityService(["arg1"])
        
        # Test stop
        svc.SvcStop()
        self.mock_win32event.SetEvent.assert_called_with(svc.stop_event)
        
        # Test stop with runner and monitor
        mock_runner_instance = MagicMock()
        mock_monitor = MagicMock()
        mock_runner_instance.monitor = mock_monitor
        svc._runner = mock_runner_instance
        svc.SvcStop()
        self.assertFalse(mock_runner_instance.should_run)
        mock_monitor.stop.assert_called_once()
        
        # Test run with Thread mock
        with patch('threading.Thread') as mock_thread_class:
            mock_thread_instance = mock_thread_class.return_value
            mock_thread_instance.is_alive.return_value = True
            
            svc.SvcDoRun()
            
            mock_runner_class.assert_called()
            self.mock_win32event.WaitForSingleObject.assert_called_with(svc.stop_event, self.mock_win32event.INFINITE)
            mock_thread_instance.join.assert_called_once_with(timeout=10.0)

    @patch('sys.argv', ['test_win_service.py', 'start'])
    def test_main_when_win32_available(self):
        import captivity.daemon.win_service
        importlib.reload(captivity.daemon.win_service)
        
        self.mock_win32serviceutil.HandleCommandLine = MagicMock()
        captivity.daemon.win_service.main()
        self.mock_win32serviceutil.HandleCommandLine.assert_called_once_with(captivity.daemon.win_service.CaptivityService)

if __name__ == '__main__':
    unittest.main()
