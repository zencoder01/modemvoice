import pytest
from unittest.mock import Mock, patch, MagicMock
import serial

from backend.modem import HuaweiModem
from backend.schemas import ModemStatus, SmsMessage


class TestHuaweiModem:
    @pytest.fixture
    def modem(self):
        with patch('backend.modem.serial.Serial') as mock_serial:
            mock_ser = MagicMock()
            mock_serial.return_value = mock_ser
            mock_ser.is_open = True
            mock_ser.in_waiting = 0
            
            modem = HuaweiModem(port="COM3", baudrate=115200, timeout=5)
            modem.ser = mock_ser
            yield modem

    def test_send_command_ok(self, modem):
        modem.ser.readline.return_value = b"OK\r\n"
        result = modem.send_command("AT")
        assert "OK" in result

    def test_send_command_error(self, modem):
        modem.ser.readline.return_value = b"ERROR\r\n"
        result = modem.send_command("AT")
        assert "ERROR" in result

    def test_get_status_signal_strength(self, modem):
        modem.send_command = Mock(side_effect=[
            "+CSQ: 20,99\r\nOK",  # AT+CSQ
            "+COPS: 0,0,\"Airtel\",2\r\nOK",  # AT+COPS?
            "+CPIN: READY\r\nOK"  # AT+CPIN?
        ])
        
        status = modem.get_status()
        assert "20" in status.signal_strength
        assert "Airtel" in status.operator

    def test_send_ussd_success(self, modem):
        modem.ser.readline = Mock(side_effect=[
            b"+CUSD: 0,\"Your balance is 50.00 PKR\",15\r\n",
            b"OK\r\n"
        ])
        
        response = modem.send_ussd("*100#")
        assert "50.00" in response

    def test_send_sms_success(self, modem):
        modem.ser.readline.return_value = b">\r\n"
        modem.ser.readline.side_effect = [
            b">\r\n",  # prompt
            b"+CMGS: 1\r\n",  # response
            b"OK\r\n"
        ]
        
        result = modem.send_sms("+1234567890", "Test message")
        assert result is True

    def test_parse_sms_list(self, modem):
        modem.send_command = Mock(return_value=(
            '+CMGL: 1,"REC UNREAD","+1234567890","","24/09/22,10:30:00+00"\n'
            'Hello world\r\n'
            '+CMGL: 2,"REC READ","+0987654321","","24/09/21,15:45:00+00"\n'
            'Another message\r\n'
            'OK\r\n'
        ))
        
        messages = modem.list_sms()
        assert len(messages) == 2
        assert messages[0].sender == "+1234567890"
        assert messages[0].content == "Hello world"
        assert messages[1].sender == "+0987654321"

    def test_dial(self, modem):
        modem.ser.write = Mock()
        modem.ser.readline.return_value = b"OK\r\n"
        
        result = modem.dial("+1234567890")
        assert result is True

    def test_hangup(self, modem):
        modem.send_command = Mock(return_value="OK\r\n")
        result = modem.hangup()
        assert result is True

    def test_answer(self, modem):
        modem.send_command = Mock(return_value="OK\r\n")
        result = modem.answer()
        assert result is True

    def test_disconnect(self, modem):
        modem.ser.is_open = True
        modem.disconnect()
        modem.ser.close.assert_called_once()


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])