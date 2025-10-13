import { useState, useEffect } from 'react';
import { AuthModal } from './components/AuthModal';
import { PairingPanel } from './components/PairingPanel';
import { StatusBar } from './components/StatusBar';
import { DeckGrid } from './components/DeckGrid';
import { ActivityEntry } from './components/ActivityLog';
import { Sidebar } from './components/Sidebar';
import { wsClient } from './lib/websocket';
import { getMe, getPrograms } from './lib/api';

interface User {
  _id: string;
  email: string;
  pairingCode?: string;
  programsFetched: boolean;
  programs: Program[];
}

interface Program {
  id: string;
  name: string;
  iconUrl: string;
  exec: string;
}

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showPairingPanel, setShowPairingPanel] = useState(false);
  const [showSidebar, setShowSidebar] = useState(false);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [activityLog, setActivityLog] = useState<ActivityEntry[]>([]);
  const [isConnected, setIsConnected] = useState(false);

  const addLog = (type: 'info' | 'error' | 'warn', msg: string) => {
    setActivityLog((prev) => [...prev, { ts: new Date(), type, msg }]);
  };

  useEffect(() => {
    const token = localStorage.getItem('authToken');
    if (!token) {
      setShowAuthModal(true);
    } else {
      loadUser();
    }
  }, []);

  const loadUser = async () => {
    try {
      const userData = await getMe();
      setUser(userData);

      if (!userData.pairingCode) {
        setShowPairingPanel(true);
      } else {
        // Load cached programs from MongoDB immediately
        loadCachedPrograms();

        // Connect to WebSocket and request fresh programs in background
        connectWebSocket(userData.pairingCode);
      }
    } catch (error) {
      console.error('Failed to load user:', error);
      setShowAuthModal(true);
    }
  };

  const loadCachedPrograms = async () => {
    try {
      const { programs: cachedPrograms } = await getPrograms();
      if (cachedPrograms && cachedPrograms.length > 0) {
        setPrograms(cachedPrograms);
        addLog('info', `Loaded ${cachedPrograms.length} cached programs from database`);
      }
    } catch (error) {
      console.error('Failed to load cached programs:', error);
    }
  };

  const connectWebSocket = (code: string) => {
    wsClient.connect(code);

    let hasRequestedPrograms = false;

    wsClient.onMessage((msg) => {
      if (msg.programs) {
        setPrograms(msg.programs);
        addLog('info', `Program list updated from receiver (${msg.programs.length} programs)`);
      } else if (msg.new_code) {
        if (user) {
          setUser({ ...user, pairingCode: msg.new_code });
        }
        addLog('info', `Receiver code regenerated: ${msg.new_code}`);
      } else if (msg.error) {
        addLog('error', msg.error);
      } else if (msg.status && msg.message) {
        addLog('info', msg.message);
      }
    });

    const checkConnection = setInterval(() => {
      const connected = wsClient.isConnected();
      setIsConnected(connected);

      // Auto-request fresh programs when connection is established (only once)
      if (connected && !hasRequestedPrograms) {
        hasRequestedPrograms = true;
        setTimeout(() => {
          wsClient.refreshPrograms();
          addLog('info', 'Requesting fresh program list from receiver');
        }, 500);
      }
    }, 1000);

    return () => {
      clearInterval(checkConnection);
    };
  };

  const handleAuthSuccess = (userData: User) => {
    setUser(userData);
    setShowAuthModal(false);
    addLog('info', 'Logged in successfully');

    if (!userData.pairingCode) {
      setShowPairingPanel(true);
    } else {
      connectWebSocket(userData.pairingCode);
    }
  };

  const handlePairingSuccess = (code: string) => {
    if (user) {
      setUser({ ...user, pairingCode: code });
    }
    setShowPairingPanel(false);
    addLog('info', `Paired with receiver: ${code}`);
    connectWebSocket(code);
  };

  const handleRefreshPrograms = () => {
    wsClient.refreshPrograms();
    addLog('info', 'Requested program list from receiver');
  };

  const handleOpenProgram = (programName: string) => {
    wsClient.openProgram(programName);
    addLog('info', `Sent request to open ${programName}`);
  };


  if (showAuthModal) {
    return <AuthModal onSuccess={handleAuthSuccess} />;
  }

  if (showPairingPanel) {
    return (
      <PairingPanel
        onPaired={handlePairingSuccess}
        existingCode={user?.pairingCode}
      />
    );
  }

  const showRefreshCta = !user?.programsFetched && programs.length === 0;

  return (
    <div className="h-screen flex flex-col">
      <Sidebar
        isOpen={showSidebar}
        onClose={() => setShowSidebar(false)}
        entries={activityLog}
      />

      <StatusBar
        pairingCode={user?.pairingCode}
        isConnected={isConnected}
        onRefresh={handleRefreshPrograms}
        onEditPairingCode={() => setShowPairingPanel(true)}
        onToggleSidebar={() => setShowSidebar(!showSidebar)}
      />

      <DeckGrid
        programs={programs}
        onProgramClick={handleOpenProgram}
        onRefresh={handleRefreshPrograms}
        showRefreshCta={showRefreshCta}
      />
    </div>
  );
}

export default App;
