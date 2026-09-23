// ModemVoice Frontend Application

const API_BASE = 'http://localhost:8000';

// State
let modemConnected = false;

// DOM Elements
const elements = {
    // Status bar
    modemStatus: document.getElementById('modem-status'),
    signalStrength: document.getElementById('signal-strength'),
    operator: document.getElementById('operator'),
    networkType: document.getElementById('network-type'),
    
    // Details
    detailSignal: document.getElementById('detail-signal'),
    detailOperator: document.getElementById('detail-operator'),
    detailNetwork: document.getElementById('detail-network'),
    detailSim: document.getElementById('detail-sim'),
    detailPort: document.getElementById('detail-port'),
    
    // USSD
    ussdCode: document.getElementById('ussd-code'),
    ussdOutput: document.getElementById('ussd-output'),
    
    // SMS
    smsNumber: document.getElementById('sms-number'),
    smsMessage: document.getElementById('sms-message'),
    smsOutput: document.getElementById('sms-output'),
    smsList: document.getElementById('sms-list'),
    tabSend: document.getElementById('tab-send'),
    tabInbox: document.getElementById('tab-inbox'),
    
    // Call
    callNumber: document.getElementById('call-number'),
    callOutput: document.getElementById('call-output'),
    
    // Voice
    voiceIndicator: document.getElementById('voice-indicator'),
    voiceStatus: document.getElementById('voice-status'),
    webhookUrl: document.getElementById('webhook-url'),
    
    // Buttons
    refreshBtn: document.getElementById('refresh-btn'),
};

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    // Set webhook URL
    document.getElementById('webhook-url').textContent = `${window.location.origin}/webhook/assemblyai`;
    
    // Event listeners
    elements.refreshBtn.addEventListener('click', loadModemStatus);
    
    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => switchTab(e.target.dataset.tab));
    });
    
    // Quick USSD buttons
    document.querySelectorAll('.quick-ussd .btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.getElementById('ussd-code').value = btn.textContent;
            sendUssd();
        });
    });
    
    // Load initial status
    await loadModemStatus();
    
    // Auto-refresh status every 30 seconds
    setInterval(loadModemStatus, 30000);
});

// Utility functions
function setOutput(element, text, type = 'info') {
    element.textContent = text;
    element.className = `output ${type}`;
    element.style.display = 'block';
}

function showTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
    
    document.querySelector(`.tab-btn[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById(`tab-${tabName}`).classList.add('active');
}

function quickUssd(code) {
    document.getElementById('ussd-code').value = code;
    sendUssd();
}

function switchTab(tabName) {
    showTab(tabName);
}

// API Functions
async function apiRequest(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: { 'Content-Type': 'application/json' },
            ...options
        });
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }
        
        return response.json();
    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        throw error;
    }
}

async function loadModemStatus() {
    try {
        const data = await apiRequest('/modem/status');
        
        // Update connection status
        const connected = data.signal_strength && data.signal_strength !== '--';
        modemConnected = connected;
        
        // Update status bar
        updateStatusElement(elements.modemStatus, connected ? 'Connected' : 'Disconnected', connected ? 'connected' : 'disconnected');
        updateStatusElement(elements.signalStrength, data.signal_strength || '--');
        updateStatusElement(elements.operator, data.operator || '--');
        updateStatusElement(elements.networkType, data.network_type || '--');
        
        // Update detail view
        elements.detailSignal.textContent = data.signal_strength || '--';
        elements.detailOperator.textContent = data.operator || '--';
        elements.detailNetwork.textContent = data.network_type || '--';
        elements.detailSim.textContent = data.sim_status || '--';
        elements.detailPort.textContent = document.getElementById('modem-port')?.textContent || 'COM3';
        
        // Update voice indicator
        const voiceIndicator = document.getElementById('voice-indicator');
        const voiceStatus = document.getElementById('voice-status');
        if (voiceIndicator && voiceStatus) {
            const connected = modemConnected;
            voiceIndicator.classList.toggle('active', connected);
            voiceStatus.textContent = connected ? 'Voice agent ready' : 'Waiting for modem...';
        }
        
    } catch (error) {
        console.error('Failed to load modem status:', error);
        updateStatusElement(elements.modemStatus, 'Error', 'disconnected');
    }
}

function updateStatusElement(element, text, className) {
    if (!element) return;
    element.textContent = text;
    element.className = `status-value ${className}`;
}

async function sendUssd() {
    const code = document.getElementById('ussd-code').value.trim();
    const output = document.getElementById('ussd-output');
    
    if (!code) {
        setOutput(output, 'Please enter a USSD code', 'error');
        return;
    }
    
    setOutput(output, 'Sending USSD...', 'info');
    
    try {
        const data = await apiRequest('/ussd/send', {
            method: 'POST',
            body: JSON.stringify({ code })
        });
        
        setOutput(output, data.response, data.status === 'success' ? 'success' : 'error');
    } catch (error) {
        setOutput(output, `Error: ${error.message}`, 'error');
    }
}

async function sendSms() {
    const number = document.getElementById('sms-number').value.trim();
    const message = document.getElementById('sms-message').value.trim();
    const output = document.getElementById('sms-output');
    
    if (!number || !message) {
        setOutput(output, 'Please enter both number and message', 'error');
        return;
    }
    
    setOutput(output, 'Sending SMS...', 'info');
    
    try {
        const data = await apiRequest('/sms/send', {
            method: 'POST',
            body: JSON.stringify({ number, message })
        });
        
        setOutput(output, data.message, 'success');
        document.getElementById('sms-message').value = '';
    } catch (error) {
        setOutput(output, `Error: ${error.message}`, 'error');
    }
}

async function loadSms() {
    const smsList = document.getElementById('sms-list');
    smsList.innerHTML = '<div style="text-align: center; color: #8b949e; padding: 20px;">Loading messages...</div>';
    
    try {
        const data = await apiRequest('/sms/list');
        
        if (!data.messages || data.messages.length === 0) {
            smsList.innerHTML = '<div style="text-align: center; color: #8b949e; padding: 20px;">No messages found</div>';
            return;
        }
        
        smsList.innerHTML = data.messages.map(msg => `
            <div class="sms-item">
                <div class="sms-header">
                    <span class="sms-sender">${escapeHtml(msg.sender)}</span>
                    <span class="sms-timestamp">${escapeHtml(msg.timestamp)}</span>
                </div>
                <div class="sms-content">${escapeHtml(msg.content)}</div>
            </div>
        `).join('');
    } catch (error) {
        smsList.innerHTML = `<div style="color: #f85149; padding: 20px; text-align: center;">Error loading messages: ${error.message}</div>`;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function dialCall() {
    const number = document.getElementById('call-number').value.trim();
    const output = document.getElementById('call-output');
    
    if (!number) {
        setOutput(output, 'Please enter a phone number', 'error');
        return;
    }
    
    setOutput(output, 'Dialing...', 'info');
    
    try {
        const data = await apiRequest('/call/dial', {
            method: 'POST',
            body: JSON.stringify({ number })
        });
        
        setOutput(output, data.message, 'success');
    } catch (error) {
        setOutput(output, `Error: ${error.message}`, 'error');
    }
}

async function hangupCall() {
    const output = document.getElementById('call-output');
    setOutput(output, 'Hanging up...', 'info');
    
    try {
        const data = await apiRequest('/call/hangup', { method: 'POST' });
        setOutput(output, data.message, 'success');
    } catch (error) {
        setOutput(output, `Error: ${error.message}`, 'error');
    }
}

// Poll for voice agent status
setInterval(async () => {
    try {
        const response = await fetch(`${API_BASE}/health`);
        const data = await response.json();
        const indicator = document.getElementById('voice-indicator');
        const statusText = document.getElementById('voice-status');
        
        if (indicator && statusText) {
            indicator.classList.toggle('active', data.modem_connected);
            statusText.textContent = data.modem_connected ? 'Voice agent ready' : 'Waiting for modem...';
        }
    } catch (e) {
        // Silently fail
    }
}, 5000);

// Expose functions globally for onclick handlers
window.sendUssd = sendUssd;
window.quickUssd = quickUssd;
window.sendSms = sendSms;
window.loadSms = loadSms;
window.dialCall = dialCall;
window.hangupCall = hangupCall;
window.showTab = showTab;
window.switchTab = switchTab;