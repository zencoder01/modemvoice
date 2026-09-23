from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# Modem Schemas
class ModemStatus(BaseModel):
    signal_strength: Optional[str] = None
    operator: Optional[str] = None
    sim_status: Optional[str] = None
    network_type: Optional[str] = None


class UssdRequest(BaseModel):
    code: str = Field(..., description="USSD code to send (e.g. *100#)")


class UssdResponse(BaseModel):
    response: str
    status: str


class SmsRequest(BaseModel):
    number: str = Field(..., description="Phone number to send SMS to")
    message: str = Field(..., description="SMS message content")


class SmsMessage(BaseModel):
    index: int
    status: str
    sender: str
    timestamp: str
    content: str


class CallRequest(BaseModel):
    number: str = Field(..., description="Phone number to dial")


class CallResponse(BaseModel):
    status: str
    message: str


# AssemblyAI Webhook Schemas
class ToolCallFunction(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: str = "function"
    function: ToolCallFunction


class AssemblyAiWebhookPayload(BaseModel):
    session_id: str
    type: str
    tool_calls: Optional[List[ToolCall]] = None
    status: Optional[str] = None
    error: Optional[str] = None


class AssemblyAiToolResponse(BaseModel):
    tool_call_id: str
    content: str


class AssemblyAiWebhookResponse(BaseModel):
    tool_responses: List[AssemblyAiToolResponse]