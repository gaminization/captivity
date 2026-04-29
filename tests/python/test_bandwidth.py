"""Tests for captivity.telemetry.bandwidth module."""

import os
import tempfile
import unittest

from captivity.telemetry.bandwidth import (
    InterfaceStats,
    format_bytes,
    read_interface_stats,
    detect_wifi_interface,
    BandwidthMonitor,
)

MOCK_PROC_NET_DEV = """\
Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 1234567       0    0    0    0     0          0         0  1234567       0    0    0    0     0       0          0
  eth0: 9876543    1000    0    0    0     0          0         0  5432100     500    0    0    0     0       0          0
wlan0: 50000000   25000    0    0    0     0          0         0 10000000   12000    0    0    0     0       0          0
"""


class TestInterfaceStats(unittest.TestCase):
    """Test InterfaceStats class."""

    def test_create(self):
        s = InterfaceStats("wlan0", rx_bytes=1000, tx_bytes=500)
        self.assertEqual(s.interface, "wlan0")
        self.assertEqual(s.total_bytes, 1500)

    def test_subtraction(self):
        a = InterfaceStats("wlan0", rx_bytes=1000, tx_bytes=500)
        b = InterfaceStats("wlan0", rx_bytes=300, tx_bytes=100)
        diff = a - b
        self.assertEqual(diff.rx_bytes, 700)
        self.assertEqual(diff.tx_bytes, 400)

    def test_repr(self):
        s = InterfaceStats("wlan0", rx_bytes=1024, tx_bytes=512)
        self.assertIn("wlan0", repr(s))


class TestFormatBytes(unittest.TestCase):
    """Test format_bytes function."""

    def test_bytes(self):
        self.assertEqual(format_bytes(500), "500 B")

    def test_kilobytes(self):
        result = format_bytes(1536)
        self.assertIn("KB", result)

    def test_megabytes(self):
        result = format_bytes(1_500_000)
        self.assertIn("MB", result)

    def test_gigabytes(self):
        result = format_bytes(2_000_000_000)
        self.assertIn("GB", result)

    def test_negative(self):
        self.assertEqual(format_bytes(-1), "0 B")


class TestReadInterfaceStats(unittest.TestCase):
    """Test read_interface_stats function."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        )
        self.tmpfile.write(MOCK_PROC_NET_DEV)
        self.tmpfile.close()

    def tearDown(self):
        os.unlink(self.tmpfile.name)

    def test_read_wlan0(self):
        stats = read_interface_stats("wlan0", self.tmpfile.name)
        self.assertIsNotNone(stats)
        self.assertEqual(stats.rx_bytes, 50000000)
        self.assertEqual(stats.tx_bytes, 10000000)

    def test_read_eth0(self):
        stats = read_interface_stats("eth0", self.tmpfile.name)
        self.assertIsNotNone(stats)
        self.assertEqual(stats.rx_bytes, 9876543)

    def test_read_nonexistent(self):
        stats = read_interface_stats("wlan99", self.tmpfile.name)
        self.assertIsNone(stats)


class TestDetectWifiInterface(unittest.TestCase):
    """Test detect_wifi_interface function."""

    def test_detects_wlan(self):
        tmpfile = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        tmpfile.write(MOCK_PROC_NET_DEV)
        tmpfile.close()
        try:
            iface = detect_wifi_interface(tmpfile.name)
            self.assertEqual(iface, "wlan0")
        finally:
            os.unlink(tmpfile.name)

    def test_no_wifi(self):
        tmpfile = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        tmpfile.write("Inter-|\n face |\n    lo: 0 0 0 0 0 0 0 0 0 0\n")
        tmpfile.close()
        try:
            self.assertIsNone(detect_wifi_interface(tmpfile.name))
        finally:
            os.unlink(tmpfile.name)


class TestBandwidthMonitor(unittest.TestCase):
    """Test BandwidthMonitor class."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        )
        self.tmpfile.write(MOCK_PROC_NET_DEV)
        self.tmpfile.close()

    def tearDown(self):
        os.unlink(self.tmpfile.name)

    def test_auto_detect_interface(self):
        bw = BandwidthMonitor(proc_path=self.tmpfile.name)
        self.assertEqual(bw.interface, "wlan0")

    def test_start_session(self):
        bw = BandwidthMonitor(interface="wlan0", proc_path=self.tmpfile.name)
        bw.start_session()
        self.assertIsNotNone(bw.baseline)

    def test_get_session_usage(self):
        bw = BandwidthMonitor(interface="wlan0", proc_path=self.tmpfile.name)
        bw.baseline = InterfaceStats("wlan0", rx_bytes=40000000, tx_bytes=5000000)
        usage = bw.get_session_usage()
        self.assertIsNotNone(usage)
        self.assertEqual(usage.rx_bytes, 10000000)
        self.assertEqual(usage.tx_bytes, 5000000)

    def test_no_interface(self):
        bw = BandwidthMonitor(interface="", proc_path=self.tmpfile.name)
        self.assertIsNone(bw.get_session_usage())

    def test_get_current_stats(self):
        bw = BandwidthMonitor(interface="wlan0", proc_path=self.tmpfile.name)
        stats = bw.get_current_stats()
        self.assertIsNotNone(stats)
        self.assertEqual(stats.rx_bytes, 50000000)


if __name__ == "__main__":
    unittest.main()
