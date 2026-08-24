import React from 'react';
import { TransactionStatusBadge, TransactionState } from './TransactionStatus';
import { TransactionOption } from './TransactionOptions';

export interface TransactionData {
  transaction_id: string;
  workflow_id?: string | null;
  type: string;
  merchant: string;
  provider: string;
  product_or_service: string;
  status: TransactionState;
  currency: string;
  amount: number;
  taxes: number;
  fees: number;
  total: number;
  selected_option?: TransactionOption | null;
  options: TransactionOption[];
  risk_level: string;
  created_at: string;
  updated_at: string;
}

interface Props {
  transaction: TransactionData;
  onOpenReview?: () => void;
  onCancel?: () => void;
}

export const TransactionCard: React.FC<Props> = ({
  transaction,
  onOpenReview,
  onCancel
}) => {
  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 space-y-3 shadow-lg hover:border-zinc-700 transition">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-white tracking-wide">{transaction.product_or_service}</span>
          <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-300">
            {transaction.type}
          </span>
        </div>
        <TransactionStatusBadge status={transaction.status} />
      </div>

      <div className="flex items-center justify-between text-xs text-zinc-400">
        <span>Provider: <strong className="text-zinc-200 font-normal">{transaction.provider}</strong></span>
        <span>Risk: <strong className="text-rose-400 font-normal">{transaction.risk_level}</strong></span>
      </div>

      {transaction.total > 0 && (
        <div className="flex justify-between items-baseline border-t border-zinc-850 pt-2 text-xs">
          <span className="text-zinc-400">Estimated Total:</span>
          <span className="font-mono text-sm font-bold text-white">
            {transaction.currency} {transaction.total}
          </span>
        </div>
      )}

      {(transaction.status === 'READY_FOR_REVIEW' || transaction.status === 'SELECTED') && (
        <div className="flex items-center justify-end gap-2 pt-1">
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="px-3 py-1 rounded text-xs text-zinc-400 hover:text-zinc-200 bg-zinc-900 hover:bg-zinc-800"
            >
              Cancel
            </button>
          )}
          {onOpenReview && (
            <button
              type="button"
              onClick={onOpenReview}
              className="px-3.5 py-1 rounded text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 transition"
            >
              Review Booking
            </button>
          )}
        </div>
      )}
    </div>
  );
};
