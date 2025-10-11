import { useState } from 'react';
import { motion } from 'framer-motion';
import { X, Upload, Plus } from 'lucide-react';
import { addProgram } from '../lib/api';

interface AddAppModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

export function AddAppModal({ onClose, onSuccess }: AddAppModalProps) {
  const [name, setName] = useState('');
  const [exec, setExec] = useState('');
  const [iconUrl, setIconUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await addProgram({
        name,
        iconUrl,
        exec,
        meta: { source: 'user' },
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to add program');
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
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-[var(--accent)]/10 rounded-lg">
              <Plus className="w-5 h-5 text-[var(--accent)]" />
            </div>
            <h2 className="text-2xl font-bold text-white">Add Custom App</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-white/5 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-300 mb-2">
              App Name
            </label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-4 py-3 bg-[#0b0f14] border border-white/10 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
              placeholder="Spotify"
              required
            />
          </div>

          <div>
            <label htmlFor="exec" className="block text-sm font-medium text-gray-300 mb-2">
              Executable Path or Command
            </label>
            <input
              id="exec"
              type="text"
              value={exec}
              onChange={(e) => setExec(e.target.value)}
              className="w-full px-4 py-3 bg-[#0b0f14] border border-white/10 rounded-lg text-white font-mono text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
              placeholder="spotify://"
              required
            />
          </div>

          <div>
            <label htmlFor="iconUrl" className="block text-sm font-medium text-gray-300 mb-2">
              Icon URL (optional)
            </label>
            <input
              id="iconUrl"
              type="url"
              value={iconUrl}
              onChange={(e) => setIconUrl(e.target.value)}
              className="w-full px-4 py-3 bg-[#0b0f14] border border-white/10 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
              placeholder="https://example.com/icon.png"
            />
          </div>

          {iconUrl && (
            <div className="flex justify-center">
              <div className="p-3 bg-[#0b0f14] rounded-lg border border-white/10">
                <img
                  src={iconUrl}
                  alt="Icon preview"
                  className="w-16 h-16 object-contain"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                  }}
                />
              </div>
            </div>
          )}

          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg p-3"
            >
              {error}
            </motion.div>
          )}

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-3 bg-white/5 text-gray-300 font-semibold rounded-lg hover:bg-white/10 transition-all"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-3 bg-[var(--accent)] text-white font-semibold rounded-lg hover:brightness-110 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-[var(--accent)]/20"
            >
              {loading ? 'Adding...' : 'Add App'}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}
