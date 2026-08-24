import React from 'react';

export interface TransactionReceiptData {
  receipt_id: string;
  transaction_id: string;
  provider: string;
  reference_number: string;
  amount: number;
  currency: string;
  booking_date: string;
  status: string;
  evidence_summary: string;
  created_at: string;
}

interface Props {
  receipt: TransactionReceiptData;
}

export const TransactionReceiptCard: React.FC<Props> = ({ receipt }) => {
  return (
    <div className="bg-zinc-950 border border-emerald-500/30 rounded-2xl p-6 shadow-2xl space-y-5">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-xl">
            ✓
          </div>
          <div>
            <h3 className="text-base font-bold text-white">Booking Confirmed & Verified</h3>
            <p className="text-xs text-zinc-400">Verified through Phase 9 Evidence Engine</p>
          </div>
        </div>
        <span className="text-xs px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-bold uppercase tracking-wider">
          {receipt.status}
        </span>
      </div>

      <div className="bg-zinc-900/60 rounded-xl p-4 space-y-3 border border-zinc-800/80">
        <div className="flex justify-between items-center text-sm">
          <span className="text-zinc-400 text-xs">Booking Reference / PNR:</span>
          <span className="font-mono text-base font-bold text-white bg-zinc-800 px-2.5 py-1 rounded border border-zinc-700">
            {receipt.reference_number}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-3 pt-2 text-xs border-t border-zinc-800/60">
          <div>
            <span className="text-zinc-500 block">Provider:</span>
            <span className="text-zinc-200 font-medium">{receipt.provider}</span>
          </div>
          <div>
            <span className="text-zinc-500 block">Total Amount Charged:</span>
            <span className="text-emerald-400 font-mono font-bold">{receipt.currency} {receipt.amount}</span>
          </div>
          <div>
            <span className="text-zinc-500 block">Transaction ID:</span>
            <span className="text-zinc-400 font-mono text-[10px]">{receipt.transaction_id}</span>
          </div>
          <div>
            <span className="text-zinc-500 block">Booking Date:</span>
            <span className="text-zinc-400 font-mono text-[10px]">
              {new Date(receipt.booking_date).toLocaleDateString()}
            </span>
          </div>
        </div>
      </div>

      <div className="text-[11px] text-zinc-400 bg-zinc-900/30 rounded-lg p-3 border border-zinc-800/40">
        <strong className="text-zinc-300">Verification Evidence:</strong> {receipt.evidence_summary}
      </div>
    </div>
  );
};
