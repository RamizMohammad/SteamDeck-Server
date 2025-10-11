import { motion } from 'framer-motion';
import { useEffect, useRef } from 'react';
import { Terminal } from 'lucide-react';

export interface ActivityEntry {
  ts: Date;
  type: 'info' | 'error' | 'warn';
  msg: string;
}

interface ActivityLogProps {
  entries: ActivityEntry[];
}

const emojiMap = {
  info: '✅',
  error: '❌',
  warn: '⚠️',
};

export function ActivityLog({ entries }: ActivityLogProps) {
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
    <div className="bg-[#0f1519] border-t border-white/10">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center gap-2 px-6 py-3 border-b border-white/5">
          <Terminal className="w-4 h-4 text-[var(--accent)]" />
          <h3 className="text-sm font-semibold text-gray-300">Activity Log</h3>
        </div>

        <div
          ref={logRef}
          className="h-40 overflow-y-auto px-6 py-3 font-mono text-xs scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent"
        >
          {entries.length === 0 ? (
            <div className="text-gray-500 italic">No activity yet...</div>
          ) : (
            entries.map((entry, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                className="py-1 hover:bg-white/5 px-2 -mx-2 rounded transition-colors"
              >
                <span className="text-gray-500">[{formatTime(entry.ts)}]</span>{' '}
                <span className="mr-1">{emojiMap[entry.type]}</span>
                <span className={`
                  ${entry.type === 'error' ? 'text-red-400' : ''}
                  ${entry.type === 'warn' ? 'text-yellow-400' : ''}
                  ${entry.type === 'info' ? 'text-gray-300' : ''}
                `}>
                  {entry.msg}
                </span>
              </motion.div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
