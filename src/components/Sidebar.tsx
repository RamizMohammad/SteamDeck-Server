import { motion, AnimatePresence } from 'framer-motion';
import { X, Terminal } from 'lucide-react';
import { ActivityEntry } from './ActivityLog';
import { useEffect, useRef } from 'react';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  entries: ActivityEntry[];
}

const emojiMap = {
  info: '✅',
  error: '❌',
  warn: '⚠️',
};

export function Sidebar({ isOpen, onClose, entries }: SidebarProps) {
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [entries]);

  const formatTime = (date: Date) => {
    const d = new Date(date);
    return d.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
          />

          <motion.div
            initial={{ x: -320 }}
            animate={{ x: 0 }}
            exit={{ x: -320 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed left-0 top-0 h-full w-80 bg-[#0b0f14] border-r border-white/10 shadow-2xl z-50 flex flex-col"
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
              <div className="flex items-center gap-3">
                <Terminal className="w-5 h-5 text-[var(--accent)]" />
                <h2 className="text-lg font-bold text-white">Activity Log</h2>
              </div>
              <button
                onClick={onClose}
                className="p-1.5 hover:bg-white/5 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>

            <div
              ref={logRef}
              className="flex-1 overflow-y-auto px-6 py-4 font-mono text-xs scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent"
            >
              {entries.length === 0 ? (
                <div className="text-gray-500 italic text-center mt-8">No activity yet...</div>
              ) : (
                entries.map((entry, index) => (
                  <motion.div
                    key={index}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="mb-3 p-2 hover:bg-white/5 rounded-lg transition-colors"
                  >
                    <div className="text-gray-500 text-[10px] mb-1">
                      [{formatTime(entry.ts)}]
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-base">{emojiMap[entry.type]}</span>
                      <span className={`
                        flex-1 leading-relaxed
                        ${entry.type === 'error' ? 'text-red-400' : ''}
                        ${entry.type === 'warn' ? 'text-yellow-400' : ''}
                        ${entry.type === 'info' ? 'text-gray-300' : ''}
                      `}>
                        {entry.msg}
                      </span>
                    </div>
                  </motion.div>
                ))
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
