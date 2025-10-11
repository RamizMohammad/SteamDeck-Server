# Stream Deck Web Application

A sleek, dark-themed web-based Stream Deck interface that connects to a receiver application to launch programs remotely.

## Features

- **Authentication**: Email/password login with automatic account creation
- **WebSocket Communication**: Real-time bidirectional communication with receiver
- **Dynamic Program Grid**: 3×5 responsive grid with glossy, animated buttons
- **Activity Logging**: Terminal-style activity log for all events
- **Custom Programs**: Add custom apps with icons and executable paths
- **Theme Support**: Multiple neon accent themes (blue, purple, green, orange)
- **Pairing System**: Secure code-based pairing with receiver applications

## Architecture

### Backend (Node.js + Express + MongoDB)

- **MongoDB Database**: Stores users, programs, pairing codes, and activity logs
- **REST API**: Authentication, pairing, program management endpoints
- **WebSocket Server**: Real-time message forwarding between sender (web) and receiver clients

### Frontend (React + TypeScript + Tailwind)

- Modern React with hooks and TypeScript
- Framer Motion animations for press effects and transitions
- Tailwind CSS with custom CSS variables for theming
- WebSocket client for real-time communication

## Setup

### Prerequisites

- Node.js 18+
- MongoDB instance (MongoDB Atlas or local)

### Installation

1. Install dependencies:
```bash
npm install
```

2. Configure environment variables in `.env`:
```
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/streamdeck
JWT_SECRET=your-super-secret-jwt-key-change-this-in-production
PORT=3001
VITE_API_URL=http://localhost:3001
VITE_WS_URL=ws://localhost:3001
```

3. Start the backend server:
```bash
npm run server
```

4. Start the frontend dev server (in a separate terminal):
```bash
npm run dev
```

## First-Time User Flow

1. **Authentication**: User is prompted to enter email and password
   - If email doesn't exist, account is created automatically
   - If email exists, password is verified

2. **Pairing**: User must enter pairing code from receiver application
   - Code is saved to user's MongoDB document

3. **Initial Connection**: User lands on main deck page
   - If no programs are saved, a "Refresh Programs" CTA is displayed
   - User must click "Refresh Programs" to fetch from receiver

4. **Program Fetch**: WebSocket sends `get_programs` command
   - Receiver responds with program list
   - Server saves programs to MongoDB
   - UI updates with button grid

5. **Program Launch**: Click any button to send `open` command
   - Receiver executes the program
   - Activity log shows success/error

## WebSocket Protocol

### Connection
```json
{"role":"sender","code":"ABCD1234"}
```

### Commands (Sender → Receiver)
```json
{"command":"get_programs"}
{"command":"open","program":"Spotify"}
{"command":"regenerate_code"}
{"command":"add_program","program":{"name":"...","exec":"...","icon":"..."}}
```

### Responses (Receiver → Sender)
```json
{"programs":[{"id":"p1","name":"Spotify","iconUrl":"...","exec":"spotify://"}]}
{"new_code":"XZ91-4WQ2"}
{"status":"ok","message":"Opened Spotify successfully"}
{"error":"Program not found"}
```

## MongoDB Schema

### Users Collection
```javascript
{
  "_id": ObjectId(),
  "email": "user@example.com",
  "passwordHash": "<bcrypt-hash>",
  "pairingCode": "ABCD1234",
  "programsFetched": true,
  "programs": [
    {
      "id": "uuid",
      "name": "Spotify",
      "iconUrl": "https://...",
      "exec": "spotify://",
      "meta": {"source": "receiver"},
      "addedAt": ISODate()
    }
  ],
  "activityLog": [
    {
      "ts": ISODate(),
      "type": "info",
      "msg": "Logged in successfully",
      "raw": {}
    }
  ],
  "createdAt": ISODate()
}
```

## API Endpoints

### Authentication
- `POST /api/auth` - Login or create account
- `GET /api/me` - Get current user

### Pairing
- `POST /api/pairing` - Set pairing code

### Programs
- `GET /api/programs` - Get user's programs
- `POST /api/programs` - Add custom program

### Activity
- `GET /api/activity` - Get activity log
- `POST /api/activity` - Add activity entry

## Design Details

- **Colors**: Dark background (#0b0f14) with glossy cards (#0f1519)
- **Animations**: Press effect with scale + glow ripple (framer-motion)
- **Typography**: Segoe UI, bold weights for buttons
- **Buttons**: 14px border-radius, glossy gradient overlay, glowing edges
- **Themes**: CSS variables for easy accent color switching

## Security

- Passwords hashed with bcrypt (10 rounds)
- JWT tokens for authentication (30 day expiry)
- Authorization header required for protected endpoints
- Input validation on all API routes

## Production Deployment

1. Set secure `JWT_SECRET` in production environment
2. Use MongoDB Atlas with proper connection string
3. Update `VITE_API_URL` and `VITE_WS_URL` to production domain
4. Build frontend: `npm run build`
5. Serve static files from `dist/` folder
6. Run server with process manager (PM2, systemd)

## License

MIT
