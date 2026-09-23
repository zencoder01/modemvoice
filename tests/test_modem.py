import pytest
from unittest.mock import Mock, patch, MagicMock
import sys


# We need to mock serial BEFORE importing the modem module
@pytest.fixture(autouse=True)
def mock_serial():
    """Mock the serial module before any imports."""
    with patch('backend.modem.serial.Serial') as mock_serial_class:
        mock_ser = MagicMock()
        mock_serial_class.return_value = mock_ser
        mock_ser.is_open = True
        mock_ser.in_waiting = 0
        mock_ser.readline.return_value = b"OK\r\n"
        yield mock_ser


# Import AFTER the mock is set up
from backend.modem import HuaweiModem, modem
from backend.schemas import ModemStatus, SmsMessage


class TestHuaweiModemBasic:
    @pytest.fixture
    def fresh_modem(self):
        """Create a fresh modem instance with mocked serial."""
        with patch('backend.modem.serial.Serial') as mock_serial_class:
            mock_ser = MagicMock()
            mock_serial_class.return_value = mock_ser
            mock_ser.is_open = True
            mock_ser.in_waiting = 0
            mock_ser.readline.return_value = b"OK\r\n"
            
            modem_instance = HuaweiModem(port="COM3", baudrate=115200, timeout=5)
            modem_instance.ser = mock_ser
            yield modem_instance

    def test_send_command_ok(self, fresh_modem):
        fresh_modem.ser.readline.return_value = b"OK\r\n"
        result = fresh_modem.send_command("AT")
        assert "OK" in result

    def test_send_command_error(self, fresh_modem):
        fresh_modem.ser.readline.return_value = b"ERROR\r\n"
        result = fresh_modem.send_command("AT")
        assert "ERROR" in result

    def test_get_status_signal_strength(self, fresh_modem):
        fresh_modem.send_command = Mock(side_effect=[
            "+CSQ: 20,99\r\nOK",  # AT+CSQ
            "+COPS: 0,0,\"Airtel\",2\r\nOK",  # AT+COPS?
            "+CPIN: READY\r\nOK"  # AT+CPIN?
        ])
        
        status = fresh_modem.get_status()
        assert "20" in status.signal_strength
        assert "Airtel" in status.operator

    def test_send_ussd_success(self, fresh_modem):
        fresh_modem.send_command = Mock(return_value='+CUSD: 0,"Your balance is 50.00 PKR",15\r\nOK')
        
        response = fresh_modem.send_ussd("*100#")
        assert "50.00" in response

    def test_send_sms_success(self, fresh_modem):
        fresh_modem.send_command = Mock(side_effect=[
            "OK",  # AT+CMGF=1
            "OK"   # final response
        ])
        fresh_modem.ser.readline.side_effect = [
            b">\r\n",  # prompt
            b"+CMGS: 1\r\n",  # response
            b"OK\r\n"
        ]
        
        result = fresh_modem.send_sms("+1234567890", "Test message")
        assert result is True

    def test_parse_sms_list(self, fresh_modem):
        fresh_modem.send_command = Mock(return_value=(
            '+CMGL: 1,"REC UNREAD","+1234567890","","24/09/22,10:30:00+00"\n'
            'Hello world\r\n'
            '+CMGL: 2,"REC READ","+0987654321","","24/09/21,15:45:00+00"\n'
            'Another message\r\n'
            'OK\r\n'
        ))
        
        messages = fresh_modem.list_sms()
        assert len(messages) == 2
        assert messages[0].sender == "+1234567890"
        assert messages[0].content == "Hello world"
        assert messages[1].sender == "+0987654321"

    def test_dial(self, fresh_modem):
        fresh_modem.send_command = Mock(return_value="OK")
        result = fresh_modem.dial("+1234567890")
        assert result is True

    def test_hangup(self, fresh_modem):
        fresh_modem.send_command = Mock(return_value="OK")
        result = fresh_modem.hangup()
        assert result is True

    def test_answer(self, fresh_modem):
        fresh_modem.send_command = Mock(return_value="OK")
        result = fresh_modem.answer()
        assert result is True

    def test_disconnect(self, fresh_modem):
        fresh_modem.disconnect()
        fresh_modem.ser.close.assert_called_once()


# Test schemas
class TestSchemas:
    def test_modem_status(self):
        status = ModemStatus(
            signal_strength="20/31 (-73 dBm)",
            operator="Airtel",
            sim_status="READY",
            network_type="3G"
        )
        assert status.signal_strength == "20/31 (-73 dBm)"
        assert status.operator == "Airtel"

    def test_sms_message(self):
        msg = SmsMessage(
            index=1,
            status="REC UNREAD",
            sender="+1234567890",
            timestamp="24/09/22,10:30:00+00",
            content="Test message"
        )
        assert msg.sender == "+1234567890"
        assert msg.index == 1