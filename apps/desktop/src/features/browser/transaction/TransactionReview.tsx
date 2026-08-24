import React from 'react';
import { TransactionPrice } from './TransactionOptions';

export interface TransactionReviewData {
  review_id: string;
  transaction_id: string;
  item_title: string;
  provider: string;
  route_or_location?: string | null;
  date_time?: string | null;
  price: TransactionPrice;
  important_restrictions: string[];
  cancellation_refund_conditions: string[];
  is_irreversible: boolean;
  risk_level: string;
  commit_action_description: string;
}

interface Props {
  review: TransactionReviewData;
  onConfirm: () => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export const TransactionReview: React.FC<Props> = ({
  review,
  onConfirm,
  onCancel,
  isLoading = false
}) => {
  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-5 space-y-4 shadow-xl">
      <div className="flex items-start justify-between border-b border-zinc-800/80 pb-3">
        <div>
          <span className="text-[11px] font-bold tracking-wider uppercase text-amber-400">
            Pre-Commit Review Package
          </span>
          <h3 className="text-base font-semibold text-white mt-0.5">{review.item_title}</h3>
          <p className="text-xs text-zinc-400">Provider: {review.provider}</p>
        </div>
        <div className="text-right">
          <span className="text-xs px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 font-medium">
            Risk: {review.risk_level}
          </span>
        </div>
      </div>

      {/* Breakdown Details */}
      <div className="bg-zinc-900/50 rounded-lg p-3 space-y-2 border border-zinc-800/50">
        <div className="flex justify-between text-xs text-zinc-300">
          <span>Base Price:</span>
          <span className="font-mono">{review.price.currency} {review.price.base}</span>
        </div>
        <div className="flex justify-between text-xs text-zinc-300">
          <span>Taxes & Airport Surcharges:</span>
          <span className="font-mono">{review.price.currency} {review.price.tax}</span>
        </div>
        {review.price.fees > 0 && (
          <div className="flex justify-between text-xs text-zinc-300">
            <span>Convenience & Booking Fees:</span>
            <span className="font-mono">{review.price.currency} {review.price.fees}</span>
          </div>
        )}
        <div className="flex justify-between text-sm font-bold text-white border-t border-zinc-800 pt-2">
          <span>Total Authorized Amount:</span>
          <span className="font-mono text-emerald-400">{review.price.currency} {review.price.total}</span>
        </div>
      </div>

      {/* Conditions and Restrictions */}
      <div className="space-y-2 text-xs text-zinc-400">
        <div className="font-semibold text-zinc-300">Key Conditions & Restrictions:</div>
        <ul className="list-disc list-inside space-y-1 text-zinc-400 pl-1">
          {review.important_restrictions.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
          {review.cancellation_refund_conditions.map((c, i) => (
            <li key={`c-${i}`} className="text-amber-300/80">{c}</li>
          ))}
        </ul>
      </div>

      {review.is_irreversible && (
        <div className="p-2.5 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
          <span>⚠️</span>
          <span>This action creates an irreversible financial commitment. Review before confirming.</span>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex items-center justify-end gap-3 pt-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={isLoading}
          className="px-4 py-2 rounded-lg text-xs font-medium text-zinc-300 bg-zinc-800 hover:bg-zinc-700 transition"
        >
          Cancel Booking
        </button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={isLoading}
          className="px-5 py-2 rounded-lg text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 transition flex items-center gap-2 shadow-lg shadow-emerald-900/30"
        >
          {isLoading && <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
          Approve & Authorize Commit
        </button>
      </div>
    </div>
  );
};
