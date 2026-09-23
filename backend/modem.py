import serial
import time
import logging
import re
from typing import List, Optional, Tuple

from backend.config import get_settings
from backend.schemas import ModemStatus, SmsMessage

logger = logging.getLogger(__name__)


class HuaweiModem:
    def __init__(self, port: str = None, baudrate: int = None, timeout: int = None):
        settings = get_settings()
        self.port = port or settings.modem_port
        self.baudrate = baudrate or settings.modem_baudrate
        self.timeout = timeout or settings.modem_timeout
        self.ser = None

    def connect(self) -> bool:
        """Connect to the modem serial port."""
        try:
            if not self.ser or not self.ser.is_open:
                self.ser = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=self.timeout,
                    rtscts=True,
                    dsrdtr=True,
                )
                logger.info(f"Connected to modem on {self.port}")
                
                # Initialize modem
                self.send_command("ATZ")  # Reset
                self.send_command("ATE0") # Echo off
                self.send_command("AT+CMGF=1") # SMS text mode
            return True
        except serial.SerialException as e:
            logger.error(f"Failed to connect to modem on {self.port}: {e}")
            return False

    def disconnect(self):
        """Disconnect from the modem."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info("Disconnected from modem")

    def send_command(self, cmd: str, wait_for_response: bool = True) -> str:
        """Send an AT command to the modem and return the response."""
        if not self.connect():
            return "ERROR: Modem not connected"

        try:
            # Clear input buffer
            self.ser.reset_input_buffer()
            
            # Send command
            full_cmd = f"{cmd}\r\n"
            self.ser.write(full_cmd.encode("utf-8"))
            logger.debug(f"Sent: {cmd}")

            if not wait_for_response:
                return "OK"

            # Read response
            response = ""
            start_time = time.time()
            
            while (time.time() - start_time) < self.timeout:
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        logger.debug(f"Recv: {line}")
                        response += line + "\n"
                        
                        # Stop reading when OK or ERROR is received, unless it's a multi-line response
                        # like CMGL where we need to keep reading until OK
                        if line == "OK" and cmd != "AT+CMGL=\"ALL\"":
                            break
                        if line == "ERROR" or "+CME ERROR" in line or "+CMS ERROR" in line:
                            break
                else:
                    time.sleep(0.1)

            return response.strip()

        except serial.SerialException as e:
            logger.error(f"Serial communication error: {e}")
            self.disconnect() # Force reconnect next time
            return f"ERROR: {e}"

    def get_status(self) -> ModemStatus:
        """Get current modem status."""
        status = ModemStatus()
        
        # Check signal strength
        res_csq = self.send_command("AT+CSQ")
        match_csq = re.search(r"\+CSQ:\s*(\d+),", res_csq)
        if match_csq:
            rssi = int(match_csq.group(1))
            if rssi == 99:
                status.signal_strength = "Not known or not detectable"
            else:
                # Convert RSSI to dBm
                dbm = -113 + (rssi * 2)
                status.signal_strength = f"{rssi}/31 ({dbm} dBm)"

        # Check operator
        res_cops = self.send_command("AT+COPS?")
        match_cops = re.search(r'\+COPS:\s*\d+,\d+,"([^"]+)",(\d)', res_cops)
        if match_cops:
            status.operator = match_cops.group(1)
            act = match_cops.group(2)
            act_map = {"0": "GSM", "2": "UTRAN (3G)", "7": "E-UTRAN (4G)"}
            status.network_type = act_map.get(act, f"Unknown ({act})")

        # Check SIM status
        res_cpin = self.send_command("AT+CPIN?")
        match_cpin = re.search(r"\+CPIN:\s*(\w+)", res_cpin)
        if match_cpin:
            status.sim_status = match_cpin.group(1)

        return status

    def send_ussd(self, code: str) -> str:
        """Send USSD code and return the response."""
        # Ensure USSD text mode
        self.send_command("AT+CUSD=1")
        
        # Send USSD command
        cmd = f'AT+CUSD=1,"{code}",15'
        
        # Custom wait for USSD response (can take longer)
        if not self.connect():
            return "ERROR: Modem not connected"

        try:
            self.ser.reset_input_buffer()
            self.ser.write(f"{cmd}\r\n".encode("utf-8"))
            logger.debug(f"Sent: {cmd}")

            response = ""
            start_time = time.time()
            ussd_timeout = 15 # USSD needs longer timeout
            
            while (time.time() - start_time) < ussd_timeout:
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        logger.debug(f"Recv: {line}")
                        response += line + "\n"
                        
                        # Wait for the actual USSD response +CUSD: ...
                        if "+CUSD:" in line:
                            break
                        if line == "ERROR":
                            break
                else:
                    time.sleep(0.1)

            # Extract just the message part
            match = re.search(r'\+CUSD:\s*\d+,"([^"]+)"', response)
            if match:
                return match.group(1)
            
            return response.strip()

        except serial.SerialException as e:
            logger.error(f"USSD communication error: {e}")
            self.disconnect()
            return f"ERROR: {e}"

    def send_sms(self, number: str, message: str) -> bool:
        """Send an SMS message."""
        # Ensure text mode
        if "OK" not in self.send_command("AT+CMGF=1"):
            logger.error("Failed to set SMS text mode")
            return False

        if not self.connect():
            return False

        try:
            self.ser.reset_input_buffer()
            
            # Initiate SMS send
            cmd = f'AT+CMGS="{number}"'
            self.ser.write(f"{cmd}\r".encode("utf-8"))
            logger.debug(f"Sent: {cmd}")
            
            # Wait for prompt '>'
            time.sleep(0.5)
            prompt = self.ser.read(self.ser.in_waiting).decode("utf-8", errors="ignore")
            if ">" not in prompt:
                logger.error(f"Did not receive SMS prompt. Got: {prompt}")
                return False
                
            # Send message body + Ctrl-Z
            self.ser.write(f"{message}\x1A".encode("utf-8"))
            logger.debug(f"Sent SMS content: {message}")
            
            # Wait for response (+CMGS: ... OK)
            response = ""
            start_time = time.time()
            while (time.time() - start_time) < 10:
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        logger.debug(f"Recv: {line}")
                        response += line + "\n"
                        if "OK" in line or "ERROR" in line:
                            break
                else:
                    time.sleep(0.1)
                    
            return "OK" in response and "ERROR" not in response

        except serial.SerialException as e:
            logger.error(f"SMS communication error: {e}")
            self.disconnect()
            return False

    def list_sms(self) -> List[SmsMessage]:
        """List all SMS messages."""
        messages = []
        
        # Ensure text mode
        self.send_command("AT+CMGF=1")
        
        # Read all messages
        res = self.send_command('AT+CMGL="ALL"')
        
        # Parse response
        # Format: +CMGL: index,"status","sender","","timestamp"
        # Content
        lines = res.split("\n")
        current_msg = None
        
        for line in lines:
            line = line.strip()
            if not line or line == "OK":
                continue
                
            match = re.match(r'\+CMGL:\s*(\d+),"([^"]+)","([^"]+)","","([^"]+)"', line)
            if match:
                if current_msg:
                    messages.append(current_msg)
                    
                current_msg = SmsMessage(
                    index=int(match.group(1)),
                    status=match.group(2),
                    sender=match.group(3),
                    timestamp=match.group(4),
                    content=""
                )
            elif current_msg:
                # Append line to content
                if current_msg.content:
                    current_msg.content += "\n"
                current_msg.content += line
                
        if current_msg:
            messages.append(current_msg)
            
        return messages

    def dial(self, number: str) -> bool:
        """Dial a voice call."""
        res = self.send_command(f"ATD{number};", wait_for_response=False)
        return "ERROR" not in res

    def hangup(self) -> bool:
        """Hangup current call."""
        res = self.send_command("ATH")
        return "ERROR" not in res

    def answer(self) -> bool:
        """Answer incoming call."""
        res = self.send_command("ATA")
        return "ERROR" not in res

# Singleton instance
modem = HuaweiModem()