import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { createServer } from 'http';
import { connectToMongoDB, closeMongoConnection } from './db/mongodb';
import { setupWebSocketServer } from './websocket';
import authRoutes from './routes/auth';
import pairingRoutes from './routes/pairing';
import programsRoutes from './routes/programs';
import activityRoutes from './routes/activity';

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
    });
  } catch (error) {
    console.error('Failed to start server:', error);
    process.exit(1);
  }
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
