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

// ======================================
// CORS Configuration (Production Ready)
// ======================================
const allowedOrigins = [
  'https://connection.linkium.space',
  'https://linkium.space',
  'http://localhost:5173',
];

const corsOptions: cors.CorsOptions = {
  origin: (origin, callback) => {
    // Allow non-browser requests (Postman, curl, mobile apps)
    if (!origin) return callback(null, true);

    if (allowedOrigins.includes(origin)) {
      return callback(null, true);
    }

    console.error('Blocked by CORS:', origin);
    return callback(new Error('Not allowed by CORS'));
  },
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: true,
};

// Apply CORS middleware
app.use(cors(corsOptions));

// ======================================
// FIX: Express v5 compatible preflight
// (DO NOT use '*' — it crashes path-to-regexp)
// ======================================
app.options(/.*/, cors(corsOptions));

// Parse JSON
app.use(express.json());

// ======================================
// Health Check (before other routes)
// ======================================
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    service: 'Linkium API',
    websocket: 'wss://api.seerver.linkium.space/ws',
  });
});

// ======================================
// Routes
// ======================================
app.use('/api', authRoutes);
app.use('/api', pairingRoutes);
app.use('/api', programsRoutes);
app.use('/api', activityRoutes);

// ======================================
// HTTP + WebSocket Server
// ======================================
const server = createServer(app);
setupWebSocketServer(server);

// ======================================
// Start Server
// ======================================
async function start() {
  try {
    await connectToMongoDB();

    server.listen(PORT, () => {
      console.log('=================================');
      console.log(`🚀 Server running on port ${PORT}`);
      console.log(`🌐 API: https://user.side.api.linkium.space`);
      console.log(`📡 WebSocket: wss://api.seerver.linkium.space/ws`);
      console.log('=================================');
    });
  } catch (err) {
    console.error('Startup error:', err);
    process.exit(1);
  }
}

// ======================================
// Graceful Shutdown
// ======================================
async function shutdown() {
  console.log('\n🛑 Shutting down...');
  await closeMongoConnection();
  server.close(() => process.exit(0));
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

start();