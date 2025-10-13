import { motion } from 'framer-motion';
import { useState } from 'react';

interface DeckButtonProps {
  name: string;
  iconUrl?: string;
  onClick: () => void;
}

export function DeckButton({ name, iconUrl, onClick }: DeckButtonProps) {
  const [isPressed, setIsPressed] = useState(false);

  const handleClick = () => {
    setIsPressed(true);
    onClick();
    setTimeout(() => setIsPressed(false), 300);
  };

  return (
    <motion.button
      onClick={handleClick}
      whileTap={{ scale: 0.985, y: 2 }}
      className={`
        relative aspect-square rounded-[14px] bg-[#0f1519] border border-white/10
        overflow-hidden group cursor-pointer transition-all duration-120
        ${isPressed ? 'shadow-lg shadow-[var(--accent)]/25' : 'shadow-md'}
      `}
      style={{
        boxShadow: isPressed
          ? '0 6px 20px rgba(var(--accent-rgb), 0.25), 0 0 12px rgba(var(--accent-rgb), 0.22), inset 0 1px 0 rgba(255, 255, 255, 0.03)'
          : '0 4px 12px rgba(0, 0, 0, 0.3), 0 0 8px rgba(var(--accent-rgb), 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.03)',
      }}
    >
      <div className="absolute inset-0 bg-gradient-to-b from-white/6 to-transparent pointer-events-none" />

      {isPressed && (
        <motion.div
          initial={{ scale: 0, opacity: 0.6 }}
          animate={{ scale: 2, opacity: 0 }}
          transition={{ duration: 0.4 }}
          className="absolute inset-0 rounded-full bg-[var(--accent)]"
        />
      )}

      <div className="relative z-10 flex items-center justify-center h-full p-4">
        {iconUrl ? (
          <img src={iconUrl} alt={name} className="w-full h-full object-contain" />
        ) : (
          <div className="w-3/4 h-3/4 rounded-lg bg-[var(--accent)]/20 flex items-center justify-center">
            <span className="text-4xl font-bold text-[var(--accent)]">
              {name.charAt(0).toUpperCase()}
            </span>
          </div>
        )}
      </div>

      <div
        className={`
          absolute inset-0 rounded-[14px] border-2 transition-all duration-120
          ${isPressed ? 'border-[var(--accent)]/60' : 'border-[var(--accent)]/0'}
        `}
      />
    </motion.button>
  );
}
