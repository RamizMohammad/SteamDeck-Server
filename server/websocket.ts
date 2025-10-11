import { WebSocketServer, WebSocket } from 'ws';
import { Server } from 'http';
import { getUsersCollection, Program } from './db/mongodb';

interface Connection {
  ws: WebSocket;
  role?: 'sender' | 'receiver';
  code?: string;
  userId?: string;
}

interface ConnectionsByCode {
  [code: string]: {
    senders: Connection[];
    receivers: Connection[];
  };
}

export function setupWebSocketServer(server: Server) {
  const wss = new WebSocketServer({ server, path: '/ws' });
  const connections: Connection[] = [];
  const connectionsByCode: ConnectionsByCode = {};

  function registerConnection(conn: Connection, code: string, role: 'sender' | 'receiver') {
    if (!connectionsByCode[code]) {
      connectionsByCode[code] = { senders: [], receivers: [] };
    }

    if (role === 'sender') {
      connectionsByCode[code].senders.push(conn);
    } else {
      connectionsByCode[code].receivers.push(conn);
    }

    console.log(`📡 ${role} connected with code: ${code}`);
  }

  function unregisterConnection(conn: Connection) {
    if (!conn.code || !conn.role) return;

    const group = connectionsByCode[conn.code];
    if (group) {
      if (conn.role === 'sender') {
        group.senders = group.senders.filter(c => c !== conn);
      } else {
        group.receivers = group.receivers.filter(c => c !== conn);
      }

      if (group.senders.length === 0 && group.receivers.length === 0) {
        delete connectionsByCode[conn.code];
      }
    }

    console.log(`📡 ${conn.role} disconnected from code: ${conn.code}`);
  }

  function forwardToReceivers(code: string, message: any) {
    const group = connectionsByCode[code];
    if (group?.receivers) {
      const msgStr = typeof message === 'string' ? message : JSON.stringify(message);
      group.receivers.forEach(conn => {
        if (conn.ws.readyState === WebSocket.OPEN) {
          conn.ws.send(msgStr);
        }
      });
    }
  }

  function forwardToSenders(code: string, message: any) {
    const group = connectionsByCode[code];
    if (group?.senders) {
      const msgStr = typeof message === 'string' ? message : JSON.stringify(message);
      group.senders.forEach(conn => {
        if (conn.ws.readyState === WebSocket.OPEN) {
          conn.ws.send(msgStr);
        }
      });
    }
  }

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
                  msg: `Program list updated (${programs.length} programs)`,
                  raw: { programCount: programs.length }
                }
              }
            }
          );

          console.log(`✅ Saved ${programs.length} programs for code ${conn.code}`);
        }
      } catch (error) {
        console.error('Error saving programs:', error);
      }

      forwardToSenders(conn.code!, msg);
    } else if (msg.new_code) {
      try {
        const users = await getUsersCollection();
        await users.updateOne(
          { pairingCode: conn.code },
          {
            $set: { pairingCode: msg.new_code },
            $push: {
              activityLog: {
                ts: new Date(),
                type: 'info',
                msg: `Pairing code regenerated: ${msg.new_code}`,
                raw: msg
              }
            }
          }
        );

        console.log(`🔄 Updated pairing code from ${conn.code} to ${msg.new_code}`);
      } catch (error) {
        console.error('Error updating pairing code:', error);
      }

      forwardToSenders(conn.code!, msg);
    } else {
      forwardToSenders(conn.code!, msg);
    }
  }

  wss.on('connection', (ws: WebSocket) => {
    const conn: Connection = { ws };
    connections.push(conn);

    ws.on('message', async (data: Buffer) => {
      try {
        const msg = JSON.parse(data.toString());

        if (msg.role && msg.code) {
          conn.role = msg.role;
          conn.code = msg.code;
          registerConnection(conn, msg.code, msg.role);
          return;
        }

        if (!conn.role || !conn.code) {
          console.warn('⚠️ Received message from unregistered connection');
          return;
        }

        if (conn.role === 'sender') {
          forwardToReceivers(conn.code, msg);
        } else if (conn.role === 'receiver') {
          await handleReceiverMessage(conn, msg);
        }
      } catch (error) {
        console.error('WebSocket message error:', error);
      }
    });

    ws.on('close', () => {
      unregisterConnection(conn);
      const index = connections.indexOf(conn);
      if (index > -1) {
        connections.splice(index, 1);
      }
    });

    ws.on('error', (error) => {
      console.error('WebSocket error:', error);
    });
  });

  console.log('🚀 WebSocket server ready on /ws');
}
