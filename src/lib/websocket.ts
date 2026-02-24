const WS_URL = import.meta.env.VITE_WS_URL || 'wss://user.side.api.linkium.space';

type MessageHandler = (message: any) => void;

class WebSocketClient {
  private ws: WebSocket | null = null;
  private messageHandlers: MessageHandler[] = [];
  private reconnectTimer: NodeJS.Timeout | null = null;
  private pairingCode: string | null = null;

  connect(pairingCode: string) {
    this.pairingCode = pairingCode;
    this.ws = new WebSocket(`${WS_URL}/ws`);

    this.ws.addEventListener('open', () => {
      console.log('✅ WebSocket connected');
      this.send({ role: 'sender', code: pairingCode });
    });

    this.ws.addEventListener('message', (event) => {
      try {
        const message = JSON.parse(event.data);
        this.messageHandlers.forEach(handler => handler(message));
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    });

    this.ws.addEventListener('close', () => {
      console.log('🔴 WebSocket disconnected');
      this.attemptReconnect();
    });

    this.ws.addEventListener('error', (error) => {
      console.error('WebSocket error:', error);
    });
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  private attemptReconnect() {
    if (this.reconnectTimer) return;

    this.reconnectTimer = setTimeout(() => {
      if (this.pairingCode) {
        console.log('🔄 Attempting to reconnect...');
        this.connect(this.pairingCode);
      }
      this.reconnectTimer = null;
    }, 3000);
  }

  send(message: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected');
    }
  }

  onMessage(handler: MessageHandler) {
    this.messageHandlers.push(handler);
  }

  removeMessageHandler(handler: MessageHandler) {
    this.messageHandlers = this.messageHandlers.filter(h => h !== handler);
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  refreshPrograms() {
    this.send({ command: 'get_programs' });
  }

  openProgram(programName: string) {
    this.send({ command: 'open', program: programName });
  }

  regenerateCode() {
    this.send({ command: 'regenerate_code' });
  }

  addProgramToReceiver(program: { name: string; exec: string; icon: string }) {
    this.send({ command: 'add_program', program });
  }
}

export const wsClient = new WebSocketClient();
