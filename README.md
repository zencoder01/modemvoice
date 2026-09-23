# ModemVoice - Voice-Controlled Huawei Modem Manager
# AssemblyAI Voice Agent Hackathon 2026

## Project Overview
Voice-controlled interface for Huawei USB modems (E303, E3372, etc.) using AssemblyAI's Voice Agent API.
Users can check balance, send SMS, initiate calls, and manage modem settings entirely by voice.

## Architecture
```
User Voice → AssemblyAI STT → LLM Intent Router → FastAPI Backend → Huawei Modem (AT Commands) → AssemblyAI TTS → User
```

## Features
- **Balance Check**: Voice-triggered USSD (*100#, *131#, etc.)
- **SMS Send/Read**: Voice-to-SMS composition and inbox reading
- **Call Control**: Initiate/answer/hangup calls via AT commands
- **Modem Status**: Signal strength, network info, SIM status
- **Network Info**: Operator, signal quality, connection type

## Tech Stack
- **Voice AI**: AssemblyAI Voice Agent API (Universal-3 Pro STT + TTS)
- **Backend**: FastAPI + WebSocket for real-time
- **Modem Interface**: PySerial AT commands on Huawei E303/E3372
- **Frontend**: Simple HTML/JS for demo & webhook testing
- **Deployment**: Docker + docker-compose

## Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- AssemblyAI API key (get from https://www.assemblyai.com/dashboard/signup)
- Huawei E303/E3372 modem connected via USB

### Environment Setup
```bash
cp .env.example .env
# Edit .env with your AssemblyAI API key and modem port
```

### Run with Docker
```bash
docker-compose up --build
```

### Manual Run
```bash
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

## Project Structure
```
modemvoice/
├── backend/
│   ├── main.py              # FastAPI app + AssemblyAI webhook
│   ├── modem.py             # Huawei AT command handler
│   ├── schemas.py           # Pydantic models
│   └── config.py            # Settings management
├── frontend/
│   ├── index.html           # Demo UI
│   └── styles.css
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## API Endpoints
- `POST /webhook/assemblyai` - AssemblyAI webhook for voice agent
- `GET /modem/status` - Get modem status
- `POST /ussd/send` - Send USSD code
- `POST /sms/send` - Send SMS
- `POST /call/dial` - Initiate call
- `POST /call/hangup` - Hangup call
- `GET /sms/list` - List SMS messages

## AT Commands Reference (Huawei E303/E3372)
| Function | Command |
|----------|---------|
| Check Signal | `AT+CSQ` |
| Network Info | `AT+COPS?` |
| SIM Status | `AT+CPIN?` |
| USSD Send | `AT+CUSD=1,"*100#",15` |
| SMS List | `AT+CMGL="ALL"` |
| SMS Send | `AT+CMGS="+1234567890"` |
| Dial Call | `ATD<Number>;` |
| Hangup | `ATH` |
| Answer Call | `ATA` |

## AssemblyAI Voice Agent Configuration
```json
{
  "name": "ModemVoice",
  "first_message": "Hello! I can control your Huawei modem. Ask me to check balance, send SMS, or make a call.",
  "system_prompt": "You are a helpful assistant that controls a Huawei USB modem via voice. You can check balance via USSD, send/read SMS, make/hangup calls, and check modem status. Keep responses concise and confirm actions before executing.",
  "voice": "elevenlabs:nova",
  "language": "en",
  "end_call_message": "Goodbye!",
  "hooks": [
    {"event": "tool_call", "url": "https://your-ngrok-url/webhook/assemblyai"}
  ]
}
```

## Development
```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Format code
black backend/
isort backend/
```

## Deployment
```bash
# Build production image
docker build -t modemvoice .

# Run with docker-compose
docker-compose -f docker-compose.prod.yml up -d
```

## License
MIT