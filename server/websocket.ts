import { Server } from 'http';
import { WebSocket, WebSocketServer } from 'ws';
import { getUsersCollection, Program } from './db/mongodb';

interface Connection {
  ws: WebSocket;
  role?: 'sender' | 'receiver';
  code?: string;
  isAlive?: boolean;
}

interface ConnectionsByCode {
  [code: string]: {
    senders: Connection[];
    receivers: Connection[];
  };
}

export function setupWebSocketServer(server: Server) {
  const wss = new WebSocketServer({
    server,
    path: '/ws'
  });

  const connectionsByCode: ConnectionsByCode = {};

  // =========================
  // Heartbeat (important for production)
  // =========================
  const interval = setInterval(() => {
    wss.clients.forEach((ws: WebSocket) => {
      const conn = (ws as any)._conn as Connection;
      if (!conn) return;

      if (conn.isAlive === false) {
        console.log('💀 Terminating dead connection');
        return ws.terminate();
      }

      conn.isAlive = false;
      ws.ping();
    });
  }, 30000);

  wss.on('close', () => clearInterval(interval));

  // =========================
  // Helpers
  // =========================
  function registerConnection(conn: Connection, code: string, role: 'sender' | 'receiver') {
    if (!connectionsByCode[code]) {
      connectionsByCode[code] = { senders: [], receivers: [] };
    }

    if (role === 'sender') {
      connectionsByCode[code].senders.push(conn);
    } else {
      connectionsByCode[code].receivers.push(conn);
    }

    console.log(`📡 ${role} connected | code: ${code}`);
  }

  function unregisterConnection(conn: Connection) {
    if (!conn.code || !conn.role) return;

    const group = connectionsByCode[conn.code];
    if (!group) return;

    if (conn.role === 'sender') {
      group.senders = group.senders.filter(c => c !== conn);
    } else {
      group.receivers = group.receivers.filter(c => c !== conn);
    }

    if (group.senders.length === 0 && group.receivers.length === 0) {
      delete connectionsByCode[conn.code];
    }

    console.log(`❌ ${conn.role} disconnected | code: ${conn.code}`);
  }

  function sendToGroup(group: Connection[], message: any) {
    const msg = typeof message === 'string' ? message : JSON.stringify(message);

    group.forEach(conn => {
      if (conn.ws.readyState === WebSocket.OPEN) {
        conn.ws.send(msg);
      }
    });
  }

  function forwardToReceivers(code: string, msg: any) {
    const group = connectionsByCode[code];
    if (group) sendToGroup(group.receivers, msg);
  }

  function forwardToSenders(code: string, msg: any) {
    const group = connectionsByCode[code];
    if (group) sendToGroup(group.senders, msg);
  }

  // =========================
  // Receiver special logic
  // =========================
  async function handleReceiverMessage(conn: Connection, msg: any) {
    if (msg.programs && Array.isArray(msg.programs)) {
      try {
        const users = await getUsersCollection();
        const user = await users.findOne({ pairingCode: conn.code });

        if (user) {
          const programs: Program[] = msg.programs.map((p: any) => ({
            id: p.id || p.name,
            name: p.name,
            iconUrl: p.iconUrl || p.icon || '',
            exec: p.exec || '',
            meta: p.meta || { source: 'receiver' },
            addedAt: new Date()
          }));

          await users.updateOne(
            { pairingCode: conn.code },
            {
              $set: {
                programs,
                programsFetched: true
              },
              $push: {
                activityLog: {
                  ts: new Date(),
                  type: 'info',
                  msg: `Program list updated (${programs.length})`,
                  raw: { count: programs.length }
                }
              }
            }
          );

          console.log(`✅ Programs saved for code ${conn.code}`);
        }
      } catch (err) {
        console.error('DB error:', err);
      }

      forwardToSenders(conn.code!, msg);
      return;
    }

    if (msg.new_code) {
      try {
        const users = await getUsersCollection();
        await users.updateOne(
          { pairingCode: conn.code },
          { $set: { pairingCode: msg.new_code } }
        );

        console.log(`🔄 Code updated ${conn.code} → ${msg.new_code}`);
      } catch (err) {
        console.error('Code update error:', err);
      }

      forwardToSenders(conn.code!, msg);
      return;
    }

    forwardToSenders(conn.code!, msg);
  }

  // =========================
  // Connection handler
  // =========================
  wss.on('connection', (ws: WebSocket) => {
    const conn: Connection = { ws, isAlive: true };
    (ws as any)._conn = conn;

    ws.on('pong', () => {
      conn.isAlive = true;
    });

    ws.on('message', async (data: Buffer) => {
      try {
        const msg = JSON.parse(data.toString());

        // Registration message
        if (msg.role && msg.code) {
          conn.role = msg.role;
          conn.code = msg.code;
          registerConnection(conn, msg.code, msg.role);
          return;
        }

        if (!conn.role || !conn.code) {
          console.warn('⚠️ Unregistered connection message');
          return;
        }

        if (conn.role === 'sender') {
          forwardToReceivers(conn.code, msg);
        } else {
          await handleReceiverMessage(conn, msg);
        }
      } catch (err) {
        console.error('WS message error:', err);
      }
    });

    ws.on('close', () => unregisterConnection(conn));
    ws.on('error', err => console.error('WS error:', err));
  });

  console.log('🚀 WebSocket ready at /ws');
}