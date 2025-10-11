import cors from 'cors';
import dotenv from 'dotenv';
import express from 'express';
import { createServer } from 'http';
import fetch from 'node-fetch'; // <— Add this import
import { closeMongoConnection, connectToMongoDB } from './db/mongodb';
import activityRoutes from './routes/activity';
import authRoutes from './routes/auth';
import pairingRoutes from './routes/pairing';
import programsRoutes from './routes/programs';
import { setupWebSocketServer } from './websocket';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3001;

app.use(cors());
app.use(express.json());

app.use('/api', authRoutes);
app.use('/api', pairingRoutes);
app.use('/api', programsRoutes);
app.use('/api', activityRoutes);

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', message: 'Stream Deck API is running' });
});

const server = createServer(app);

setupWebSocketServer(server);

async function start() {
  try {
    await connectToMongoDB();

    server.listen(PORT, () => {
      console.log(`🚀 Server running on port ${PORT}`);
      console.log(`📡 WebSocket available at ws://localhost:${PORT}/ws`);
      console.log(`🌐 Frontend URL: https://steamdeck.onrender.com`);
      keepAlive(); // <— Start keep-alive loop after server is up
    });
  } catch (error) {
    console.error('Failed to start server:', error);
    process.exit(1);
  }
}

// 🩵 KEEP ALIVE FUNCTION
function keepAlive() {
  const SELF_URL = process.env.SELF_URL || 'https://steamdeck-server.onrender.com'; // 🔁 Replace or use env
  setInterval(async () => {
    try {
      const res = await fetch(`${SELF_URL}/api/health`);
      console.log(`[KEEP-ALIVE] Pinged ${SELF_URL}/api/health at ${new Date().toISOString()} - Status: ${res.status}`);
    } catch (err) {
      console.error(`[KEEP-ALIVE ERROR] ${err.message}`);
    }
  }, 4.5 * 60 * 1000); // every 4.5 minutes
}

process.on('SIGINT', async () => {
  console.log('\n🛑 Shutting down gracefully...');
  await closeMongoConnection();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.log('\n🛑 Shutting down gracefully...');
  await closeMongoConnection();
  process.exit(0);
});

start();
