import cors from 'cors';
import dotenv from 'dotenv';
import express from 'express';
import { createServer } from 'http';
import { closeMongoConnection, connectToMongoDB } from './db/mongodb';
import activityRoutes from './routes/activity';
import authRoutes from './routes/auth';
import pairingRoutes from './routes/pairing';
import programsRoutes from './routes/programs';
import { setupWebSocketServer } from './websocket';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 8002;

app.use(cors());
app.use(express.json());

// =========================
// Routes
// =========================
app.use('/api', authRoutes);
app.use('/api', pairingRoutes);
app.use('/api', programsRoutes);
app.use('/api', activityRoutes);

app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    service: 'Linkium API',
    websocket: 'wss://api.seerver.linkium.space/ws'
  });
});

// =========================
// HTTP + WebSocket Server
// =========================
const server = createServer(app);
setupWebSocketServer(server);

// =========================
// Start
// =========================
async function start() {
  try {
    await connectToMongoDB();

    server.listen(PORT, () => {
      console.log('=================================');
      console.log(`🚀 Server running on port ${PORT}`);
      console.log(`🌐 API: https://api.seerver.linkium.space`);
      console.log(`📡 WebSocket: wss://api.seerver.linkium.space/ws`);
      console.log('=================================');
    });
  } catch (err) {
    console.error('Startup error:', err);
    process.exit(1);
  }
}

// =========================
// Graceful Shutdown
// =========================
async function shutdown() {
  console.log('\n🛑 Shutting down...');
  await closeMongoConnection();
  server.close(() => process.exit(0));
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

start();