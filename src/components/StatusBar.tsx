import { Settings, RefreshCw, Cable } from 'lucide-react';
import { motion } from 'framer-motion';

interface StatusBarProps {
  pairingCode?: string;
  isConnected: boolean;
  onRefresh: () => void;
  onRegenerateCode: () => void;
  onEditPairingCode: () => void;
}

export function StatusBar({
  pairingCode,
  isConnected,
  onRefresh,
  onRegenerateCode,
  onEditPairingCode,
}: StatusBarProps) {
  return (
    <div className="bg-[#0f1519] border-b border-white/10 px-6 py-4">
      <div className="flex items-center justify-between max-w-6xl mx-auto">
        <div className="flex items-center gap-6">
          <h1 className="text-xl font-bold text-white">Stream Deck</h1>

          {pairingCode && (
            <button
              onClick={onEditPairingCode}
              className="flex items-center gap-2 px-3 py-1.5 bg-[#0b0f14] border border-white/10 rounded-lg hover:border-[var(--accent)]/30 transition-colors"
            >
              <Cable className="w-4 h-4 text-[var(--accent)]" />
              <span className="text-sm font-mono text-gray-300">{pairingCode}</span>
            </button>
          )}

          <div className="flex items-center gap-2">
            <motion.div
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
              className={`w-2 h-2 rounded-full ${
                isConnected ? 'bg-green-500' : 'bg-red-500'
              }`}
            />
            <span className="text-sm text-gray-400">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onRefresh}
            className="p-2 hover:bg-white/5 rounded-lg transition-colors group"
            title="Refresh Programs"
          >
            <RefreshCw className="w-5 h-5 text-gray-400 group-hover:text-[var(--accent)] transition-colors" />
          </button>

          <button
            onClick={onRegenerateCode}
            className="px-3 py-1.5 bg-orange-500/10 border border-orange-500/20 text-orange-400 text-sm font-medium rounded-lg hover:bg-orange-500/20 transition-all shadow-lg shadow-orange-500/10"
            title="Regenerate Receiver Code"
          >
            Regenerate Code
          </button>

          <button
            className="p-2 hover:bg-white/5 rounded-lg transition-colors group"
            title="Settings"
          >
            <Settings className="w-5 h-5 text-gray-400 group-hover:text-white transition-colors" />
          </button>
        </div>
      </div>
    </div>
  );
}
