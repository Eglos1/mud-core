"""
Telnet protocol handler — ANSI color, line editing, IAC negotiation.
"""
import asyncio, struct

IAC  = bytes([255])
DONT = bytes([254])
DO   = bytes([253])
WONT = bytes([252])
WILL = bytes([251])
SB   = bytes([250])
SE   = bytes([240])
ECHO = bytes([1])
SGA  = bytes([3])
MTTS = bytes([24])
LINEMODE = bytes([34])
NAWS = bytes([31])
CHARSET = bytes([42])
ENVIRON = bytes([39])
NEW_ENVIRON = bytes([39])

MTTS_REQUEST = IAC + DO + MTTS
MTTS_SEND = IAC + SB + MTTS + bytes([1]) + IAC + SE

class TelnetHandler:
    """Wraps a reader/writer pair with telnet negotiation and line input."""
    
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.buf = bytearray()
        self.line_queue = asyncio.Queue()
        self.ansi_enabled = True
        self.term_type = "UNKNOWN"
        self.term_width = 80
        self.term_height = 24
        self._negotiate()
    
    def _negotiate(self):
        """Send initial telnet negotiations."""
        self.writer.write(IAC + DO + NAWS)    # Window size
        self.writer.write(IAC + DO + MTTS)    # Terminal type
        self.writer.write(IAC + DO + LINEMODE) 
        self.writer.write(IAC + DONT + ECHO)  # We handle echoing
        self.writer.write(IAC + WILL + ECHO)  
        self.writer.write(IAC + WILL + SGA)
    
    def send(self, text, ansi=True):
        """Send text to the client."""
        if not ansi or not self.ansi_enabled:
            # Strip ANSI codes
            import re
            text = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
        try:
            self.writer.write(text.encode('utf-8', errors='replace'))
        except:
            self.writer.write(text.encode('latin-1', errors='replace'))
    
    def sendline(self, text="", ansi=True):
        """Send text + newline."""
        self.send(text + "\r\n", ansi)
    
    def send_ansi(self, code, text):
        """Send text wrapped in ANSI code."""
        self.send(f"\x1b[{code}m{text}\x1b[0m")
    
    def colourize(self, text, colour):
        """Wrap text in an ANSI colour."""
        codes = {
            "red": "31", "green": "32", "yellow": "33", "blue": "34",
            "magenta": "35", "cyan": "36", "white": "37", "bold": "1",
            "dark": "2", "underline": "4", "blink": "5",
            "bg_red": "41", "bg_green": "42", "bg_blue": "44",
            "orange": "38;5;214", "pink": "38;5;205", "grey": "38;5;244"
        }
        c = codes.get(colour, "37")
        return f"\x1b[{c}m{text}\x1b[0m" if self.ansi_enabled else text
    
    def prompt(self, text="> "):
        """Send a prompt."""
        if self.ansi_enabled:
            self.send(f"\r\n\x1b[32m{text}\x1b[0m ")
        else:
            self.send(f"\r\n{text} ")
    
    async def read_line(self):
        """Read one line of input from the telnet stream."""
        while True:
            if not self.line_queue.empty():
                return await self.line_queue.get()
            
            try:
                data = await asyncio.wait_for(self.reader.read(1024), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            except (ConnectionResetError, ConnectionError):
                return None
            
            if not data:
                return None
            
            self._process_data(data)
    
    def _process_data(self, data):
        """Process raw bytes, handling IAC sequences and building lines."""
        i = 0
        while i < len(data):
            # IAC sequence
            if data[i] == 255 and i + 2 < len(data):
                cmd = data[i+1]
                if cmd == 250:  # SB
                    end = data.find(bytes([255, 240]), i+2)
                    if end >= 0:
                        self._handle_sb(data[i:end+2])
                        i = end + 2
                    else:
                        i += 1
                elif cmd in (251, 252, 253, 254):  # WILL/WONT/DO/DONT
                    self._handle_command(cmd, data[i+2] if i+2 < len(data) else None)
                    i += 3
                else:
                    i += 2
                continue
            
            # Normal character
            c = data[i]
            if c == 13:  # CR
                pass  # skip
            elif c == 10:  # LF = newline
                line = bytes(self.buf).decode('utf-8', errors='replace').strip()
                self.buf.clear()
                if line:
                    self.line_queue.put_nowait(line)
            elif c in (8, 127):  # Backspace
                if self.buf:
                    self.buf.pop()
            else:
                self.buf.append(c)
            i += 1
    
    def _handle_command(self, cmd, opt):
        """Handle IAC WILL/WONT/DO/DONT."""
        if cmd == 251:  # WILL
            if opt == 1:  # ECHO
                pass
            elif opt == 3:  # SGA
                pass
        elif cmd == 252:  # WONT
            pass
        elif cmd == 253:  # DO
            if opt in (1, 3):  # ECHO, SGA
                self.writer.write(IAC + WILL + bytes([opt]))
            elif opt == 24:
                self.writer.write(MTTS_SEND)
            elif opt == 31:
                pass  # NAWS
            else:
                self.writer.write(IAC + WONT + bytes([opt]))
        elif cmd == 254:  # DONT
            self.writer.write(IAC + WONT + bytes([opt]))
    
    def _handle_sb(self, data):
        """Handle subnegotiation."""
        if len(data) < 5:
            return
        opt = data[2]
        payload = data[3:-2]
        if opt == 24:  # MTTS
            if payload and payload[0] == 0:
                try:
                    self.term_type = payload[1:].decode('latin-1', errors='replace')
                except:
                    pass
        elif opt == 31:  # NAWS
            if len(payload) >= 4:
                self.term_width = (payload[0] << 8) | payload[1]
                self.term_height = (payload[2] << 8) | payload[3]
    
    def close(self):
        """Close the connection."""
        try:
            self.writer.close()
        except:
            pass
