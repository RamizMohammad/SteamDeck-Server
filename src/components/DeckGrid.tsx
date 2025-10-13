import { motion } from 'framer-motion';
import { RefreshCw } from 'lucide-react';
import { DeckButton } from './DeckButton';

interface Program {
  id: string;
  name: string;
  iconUrl: string;
  exec: string;
}

interface DeckGridProps {
  programs: Program[];
  onProgramClick: (programName: string) => void;
  onRefresh: () => void;
  showRefreshCta: boolean;
}

export function DeckGrid({ programs, onProgramClick, onRefresh, showRefreshCta }: DeckGridProps) {
  if (showRefreshCta) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center max-w-md"
        >
          <div className="mb-6">
            <div className="inline-flex p-4 bg-[var(--accent)]/10 rounded-2xl mb-4">
              <RefreshCw className="w-12 h-12 text-[var(--accent)]" />
            </div>
            <h3 className="text-2xl font-bold text-white mb-2">Ready to Connect</h3>
            <p className="text-gray-400">
              Click the button below to fetch programs from your paired receiver
            </p>
          </div>

          <button
            onClick={onRefresh}
            className="px-6 py-3 bg-[var(--accent)] text-white font-semibold rounded-lg hover:brightness-110 transition-all shadow-lg shadow-[var(--accent)]/20 flex items-center gap-2 mx-auto"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh Programs
          </button>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="flex-1 p-8 overflow-auto">
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7 gap-6 max-w-7xl mx-auto">
        {programs.map((program, index) => (
          <motion.div
            key={program.id}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: index * 0.05 }}
            className="flex flex-col items-center gap-3"
          >
            <DeckButton
              name={program.name}
              iconUrl={program.iconUrl}
              onClick={() => onProgramClick(program.name)}
            />
            <span className="text-sm font-medium text-white text-center line-clamp-2 w-full px-1">
              {program.name}
            </span>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
