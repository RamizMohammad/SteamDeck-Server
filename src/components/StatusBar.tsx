import { RefreshCw, Cable, Terminal } from 'lucide-react';
import { motion } from 'framer-motion';

interface StatusBarProps {
  pairingCode?: string;
  isConnected: boolean;
  onRefresh: () => void;
  onEditPairingCode: () => void;
  onToggleSidebar: () => void;
}

export function StatusBar({
  pairingCode,
  isConnected,
  onRefresh,
  onEditPairingCode,
  onToggleSidebar,
}: StatusBarProps) {
  return (
    <div className="bg-[#0f1519] border-b border-white/10 px-3 sm:px-6 py-3 sm:py-4">
      <div className="flex items-center justify-between gap-2 max-w-7xl mx-auto">
        <div className="flex items-center gap-2 sm:gap-4 flex-1 min-w-0">
          <button
            onClick={onToggleSidebar}
            className="p-2 hover:bg-white/5 rounded-lg transition-colors group flex-shrink-0"
            title="Activity Log"
          >
            <Terminal className="w-5 h-5 text-gray-400 group-hover:text-[var(--accent)] transition-colors" />
          </button>

          <h1 className="text-lg sm:text-xl font-bold text-white whitespace-nowrap">Stream Deck</h1>

          {pairingCode && (
            <button
              onClick={onEditPairingCode}
              className="flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-1.5 bg-[#0b0f14] border border-white/10 rounded-lg hover:border-[var(--accent)]/30 transition-colors flex-shrink-0"
            >
              <Cable className="w-3.5 sm:w-4 h-3.5 sm:h-4 text-[var(--accent)]" />
              <span className="text-xs sm:text-sm font-mono text-gray-300">{pairingCode}</span>
            </button>
          )}

          <div className="flex items-center gap-1.5 sm:gap-2 flex-shrink-0">
            <motion.div
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
              className={`w-2 h-2 rounded-full ${
                isConnected ? 'bg-green-500' : 'bg-red-500'
              }`}
            />
            <span className="text-xs sm:text-sm text-gray-400 hidden md:inline">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1.5 sm:gap-2 flex-shrink-0">
          <button
            onClick={onRefresh}
            className="p-2 hover:bg-white/5 rounded-lg transition-colors group"
            title="Refresh Programs"
          >
            <RefreshCw className="w-5 h-5 text-gray-400 group-hover:text-[var(--accent)] transition-colors" />
          </button>
        </div>
      </div>
    </div>
  );
}
