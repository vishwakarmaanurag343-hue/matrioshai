import React from 'react';
import { TransactionReviewData } from './TransactionReview';

interface Props {
  isOpen: boolean;
  review: TransactionReviewData;
  onConfirm: () => void;
  onReject: () => void;
  isSubmitting?: boolean;
}

export const ConfirmationDialog: React.FC<Props> = ({
  isOpen,
  review,
  onConfirm,
  onReject,
  isSubmitting = false
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-fade-in">
      <div className="w-full max-w-lg bg-zinc-950 border border-zinc-800 rounded-2xl p-6 shadow-2xl space-y-5 animate-scale-in">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 text-lg">
            💳
          </div>
          <div>
            <h3 className="text-base font-bold text-white">Confirm Real-World Transaction</h3>
            <p className="text-xs text-zinc-400">Explicit user confirmation is strictly required</p>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-3">
          <div className="flex justify-between items-center text-sm font-semibold text-white border-b border-zinc-800 pb-2">
            <span>{review.item_title}</span>
            <span className="text-emerald-400 font-mono text-base">
              {review.price.currency} {review.price.total}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs text-zinc-400">
            <div>
              <span className="text-zinc-500 block">Merchant / Provider:</span>
              <span className="text-zinc-200 font-medium">{review.provider}</span>
            </div>
            <div>
              <span className="text-zinc-500 block">Risk Classification:</span>
              <span className="text-rose-400 font-medium">{review.risk_level}</span>
            </div>
          </div>
        </div>

        <p className="text-xs text-zinc-400 leading-relaxed">
          By clicking <strong className="text-white">Confirm Booking</strong>, you authorize MATRIOSHAI to trigger the final payment/booking commit action on the live merchant website.
        </p>

        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onReject}
            disabled={isSubmitting}
            className="px-4 py-2 rounded-xl text-xs font-semibold text-zinc-400 hover:text-white bg-zinc-900 hover:bg-zinc-800 transition"
          >
            Cancel / Reject
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isSubmitting}
            className="px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 transition flex items-center gap-2 shadow-lg shadow-emerald-950/50"
          >
            {isSubmitting && <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
            Confirm Booking & Authorize
          </button>
        </div>
      </div>
    </div>
  );
};
