import React from 'react';

export interface TransactionPrice {
  base: number;
  tax: number;
  fees: number;
  discount: number;
  total: number;
  currency: string;
  confidence: string;
}

export interface TransactionOption {
  option_id: string;
  provider: string;
  title: string;
  price: TransactionPrice;
  availability: string;
  attributes: Record<string, unknown>;
  constraints_satisfied: boolean;
  preference_score: number;
  confidence: string;
}

interface Props {
  options: TransactionOption[];
  selectedOptionId?: string | null;
  onSelectOption: (optionId: string) => void;
}

export const TransactionOptions: React.FC<Props> = ({
  options,
  selectedOptionId,
  onSelectOption
}) => {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-zinc-200">Comparison Options</h4>
        <span className="text-xs text-zinc-400">{options.length} options evaluated</span>
      </div>

      <div className="grid gap-2 max-h-72 overflow-y-auto pr-1">
        {options.map((opt) => {
          const isSelected = opt.option_id === selectedOptionId;
          return (
            <div
              key={opt.option_id}
              onClick={() => onSelectOption(opt.option_id)}
              className={`p-3 rounded-lg border transition-all cursor-pointer flex items-center justify-between ${
                isSelected
                  ? 'bg-blue-600/10 border-blue-500/50 shadow-sm'
                  : 'bg-zinc-900/50 border-zinc-800 hover:border-zinc-700'
              }`}
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-white">{opt.title}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 font-mono">
                    {opt.provider}
                  </span>
                  {opt.preference_score > 0 && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-mono">
                      Match: {opt.preference_score}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 text-xs text-zinc-400">
                  <span>Base: {opt.price.currency} {opt.price.base}</span>
                  {opt.price.fees > 0 && <span>+ Fees: {opt.price.currency} {opt.price.fees}</span>}
                  <span className="capitalize text-zinc-300">Status: {opt.availability.toLowerCase()}</span>
                </div>
              </div>

              <div className="text-right">
                <div className="text-sm font-bold text-zinc-100">
                  {opt.price.currency} {opt.price.total}
                </div>
                <div className="text-[10px] text-zinc-400 font-mono">Total Price</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
