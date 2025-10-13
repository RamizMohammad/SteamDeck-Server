import { useState } from 'react';
import { motion } from 'framer-motion';
import { Cable, RefreshCw } from 'lucide-react';
import { setPairingCode } from '../lib/api';

interface PairingPanelProps {
  onPaired: (code: string) => void;
  existingCode?: string;
}

export function PairingPanel({ onPaired, existingCode }: PairingPanelProps) {
  const [code, setCode] = useState(existingCode || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await setPairingCode(code);
      onPaired(code);
    } catch (err: any) {
      setError(err.message || 'Failed to set pairing code');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-[#0f1519] border border-white/10 rounded-2xl p-8 w-full max-w-md shadow-2xl"
      >
        <div className="flex items-center gap-3 mb-6">
          <div className="p-3 bg-[var(--accent)]/10 rounded-lg">
            <Cable className="w-6 h-6 text-[var(--accent)]" />
          </div>
          <h2 className="text-2xl font-bold text-white">Receiver Pairing</h2>
        </div>

        <p className="text-gray-400 mb-6">
          Enter the pairing code from your Stream Deck receiver application to connect.
        </p>

        <form onSubmit={handleConnect} className="space-y-4">
          <div>
            <label htmlFor="code" className="block text-sm font-medium text-gray-300 mb-2">
              Pairing Code
            </label>
            <input
              id="code"
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              className="w-full px-4 py-3 bg-[#0b0f14] border border-white/10 rounded-lg text-white text-center text-lg font-mono tracking-widest focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
              placeholder="ABCD1234"
              required
              maxLength={10}
            />
          </div>

          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg p-3"
            >
              {error}
            </motion.div>
          )}

          <button
            type="submit"
            disabled={loading || !code}
            className="w-full py-3 bg-[var(--accent)] text-white font-semibold rounded-lg hover:brightness-110 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-[var(--accent)]/20 flex items-center justify-center gap-2"
          >
            <Cable className="w-4 h-4" />
            {loading ? 'Connecting...' : 'Connect Receiver'}
          </button>
        </form>
      </motion.div>
    </div>
  );
}
