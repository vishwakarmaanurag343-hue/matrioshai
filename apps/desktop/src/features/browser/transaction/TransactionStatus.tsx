import React from 'react';

export type TransactionState =
  | 'DISCOVERING'
  | 'COMPARING'
  | 'SELECTED'
  | 'PREPARING'
  | 'READY_FOR_REVIEW'
  | 'AWAITING_CONFIRMATION'
  | 'CONFIRMED'
  | 'COMMITTING'
  | 'COMMITTED'
  | 'VERIFYING'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'FAILED'
  | 'EXPIRED'
  | 'BLOCKED'
  | 'UNKNOWN_OUTCOME';

interface Props {
  status: TransactionState;
}

const statusColors: Record<TransactionState, { bg: string; text: string; label: string }> = {
  DISCOVERING: { bg: 'bg-blue-500/10 border-blue-500/30', text: 'text-blue-400', label: 'Discovering Options' },
  COMPARING: { bg: 'bg-indigo-500/10 border-indigo-500/30', text: 'text-indigo-400', label: 'Comparing Options' },
  SELECTED: { bg: 'bg-purple-500/10 border-purple-500/30', text: 'text-purple-400', label: 'Option Selected' },
  PREPARING: { bg: 'bg-amber-500/10 border-amber-500/30', text: 'text-amber-400', label: 'Preparing Booking' },
  READY_FOR_REVIEW: { bg: 'bg-cyan-500/10 border-cyan-500/30', text: 'text-cyan-400', label: 'Ready for Review' },
  AWAITING_CONFIRMATION: { bg: 'bg-yellow-500/10 border-yellow-500/30', text: 'text-yellow-400', label: 'Awaiting User Confirmation' },
  CONFIRMED: { bg: 'bg-emerald-500/10 border-emerald-500/30', text: 'text-emerald-400', label: 'User Confirmed' },
  COMMITTING: { bg: 'bg-rose-500/10 border-rose-500/30', text: 'text-rose-400', label: 'Committing Payment' },
  COMMITTED: { bg: 'bg-orange-500/10 border-orange-500/30', text: 'text-orange-400', label: 'Payment Committed' },
  VERIFYING: { bg: 'bg-sky-500/10 border-sky-500/30', text: 'text-sky-400', label: 'Verifying Receipt' },
  COMPLETED: { bg: 'bg-green-500/10 border-green-500/30', text: 'text-green-400', label: 'Booking Confirmed' },
  CANCELLED: { bg: 'bg-zinc-500/10 border-zinc-500/30', text: 'text-zinc-400', label: 'Cancelled' },
  FAILED: { bg: 'bg-red-500/10 border-red-500/30', text: 'text-red-400', label: 'Failed' },
  EXPIRED: { bg: 'bg-stone-500/10 border-stone-500/30', text: 'text-stone-400', label: 'Expired' },
  BLOCKED: { bg: 'bg-red-500/20 border-red-500/50', text: 'text-red-300', label: 'Policy Blocked' },
  UNKNOWN_OUTCOME: { bg: 'bg-orange-500/20 border-orange-500/50', text: 'text-orange-300', label: 'Outcome Unknown — Verifying' },
};

export const TransactionStatusBadge: React.FC<Props> = ({ status }) => {
  const config = statusColors[status] || { bg: 'bg-zinc-800 border-zinc-700', text: 'text-zinc-300', label: status };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${config.bg} ${config.text}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
      {config.label}
    </span>
  );
};
