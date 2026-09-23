import json
import logging
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.modem import modem
from backend.schemas import (
    AssemblyAiWebhookPayload,
    AssemblyAiWebhookResponse,
    AssemblyAiToolResponse,
    CallRequest,
    SmsRequest,
    UssdRequest,
    UssdResponse,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="ModemVoice API")

# Add CORS middleware
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "*"],  # Update for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    logger.info("Starting ModemVoice API")
    # Initialize modem connection
    if not modem.connect():
        logger.warning(f"Could not connect to modem on port {modem.port}. Ensure it is connected and drivers are installed.")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down ModemVoice API")
    modem.disconnect()


@app.get("/health")
def health_check():
    return {"status": "ok", "modem_connected": modem.ser is not None and modem.ser.is_open}


@app.get("/modem/status")
def get_status():
    try:
        status = modem.get_status()
        return status
    except Exception as e:
        logger.error(f"Error getting modem status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ussd/send", response_model=UssdResponse)
def send_ussd(req: UssdRequest):
    try:
        response = modem.send_ussd(req.code)
        return UssdResponse(
            response=response,
            status="success" if "ERROR" not in response else "error"
        )
    except Exception as e:
        logger.error(f"Error sending USSD: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sms/send")
def send_sms(req: SmsRequest):
    try:
        success = modem.send_sms(req.number, req.message)
        if success:
            return {"status": "success", "message": "SMS sent successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send SMS")
    except Exception as e:
        logger.error(f"Error sending SMS: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sms/list")
def list_sms():
    try:
        messages = modem.list_sms()
        return {"messages": messages}
    except Exception as e:
        logger.error(f"Error listing SMS: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/call/dial")
def dial(req: CallRequest):
    try:
        success = modem.dial(req.number)
        if success:
            return {"status": "success", "message": f"Dialing {req.number}..."}
        else:
            raise HTTPException(status_code=500, detail="Failed to initiate call")
    except Exception as e:
        logger.error(f"Error dialing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/call/hangup")
def hangup():
    try:
        success = modem.hangup()
        if success:
            return {"status": "success", "message": "Call disconnected"}
        else:
            raise HTTPException(status_code=500, detail="Failed to hang up")
    except Exception as e:
        logger.error(f"Error hanging up: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/call/answer")
def answer():
    try:
        success = modem.answer()
        if success:
            return {"status": "success", "message": "Call answered"}
        else:
            raise HTTPException(status_code=500, detail="Failed to answer call")
    except Exception as e:
        logger.error(f"Error answering: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- AssemblyAI Voice Agent Webhook ---

@app.post("/webhook/assemblyai", response_model=AssemblyAiWebhookResponse)
async def assemblyai_webhook(request: Request):
    """
    Webhook endpoint for AssemblyAI Voice Agent tool calls.
    Handles intents from the LLM and maps them to modem functions.
    """
    try:
        # Parse payload
        payload_data = await request.json()
        payload = AssemblyAiWebhookPayload(**payload_data)
        
        logger.info(f"Received webhook for session {payload.session_id}, type: {payload.type}")
        
        tool_responses = []
        
        if payload.type == "tool_calls" and payload.tool_calls:
            for tool_call in payload.tool_calls:
                func_name = tool_call.function.name
                
                try:
                    # Parse arguments string back to dict
                    args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                    logger.info(f"Tool call: {func_name}, args: {args}")
                    
                    content = "Action completed."
                    
                    # Route to appropriate modem function
                    if func_name == "check_modem_status":
                        status = modem.get_status()
                        content = f"Signal strength is {status.signal_strength}. Network: {status.operator} ({status.network_type}). SIM status: {status.sim_status}."
                        
                    elif func_name == "send_ussd":
                        code = args.get("code")
                        if code:
                            resp = modem.send_ussd(code)
                            content = f"The USSD response is: {resp}"
                        else:
                            content = "Missing USSD code."
                            
                    elif func_name == "send_sms":
                        number = args.get("number")
                        message = args.get("message")
                        if number and message:
                            success = modem.send_sms(number, message)
                            content = "SMS sent successfully." if success else "Failed to send SMS."
                        else:
                            content = "Missing phone number or message."
                            
                    elif func_name == "read_latest_sms":
                        messages = modem.list_sms()
                        if messages:
                            latest = messages[-1]
                            content = f"Latest message from {latest.sender}: {latest.content}"
                        else:
                            content = "You have no messages."
                            
                    elif func_name == "dial_number":
                        number = args.get("number")
                        if number:
                            success = modem.dial(number)
                            content = f"Dialing {number}." if success else "Failed to make call."
                        else:
                            content = "Missing phone number to dial."
                            
                    elif func_name == "hang_up":
                        success = modem.hangup()
                        content = "Call disconnected." if success else "Failed to hang up."
                    
                    else:
                        content = f"Unknown tool: {func_name}"
                        logger.warning(f"Unknown tool called: {func_name}")
                        
                    # Add response
                    tool_responses.append(
                        AssemblyAiToolResponse(
                            tool_call_id=tool_call.id,
                            content=content
                        )
                    )
                    
                except Exception as tool_e:
                    logger.error(f"Error executing tool {func_name}: {tool_e}")
                    tool_responses.append(
                        AssemblyAiToolResponse(
                            tool_call_id=tool_call.id,
                            content=f"Sorry, I encountered an error: {str(tool_e)}"
                        )
                    )
                    
        return AssemblyAiWebhookResponse(tool_responses=tool_responses)
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        # Even on error, we must return empty responses for all tool calls to not hang the agent
        return AssemblyAiWebhookResponse(tool_responses=[])