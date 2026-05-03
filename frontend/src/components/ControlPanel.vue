<script setup>
import { usePortfolioStore } from '@/stores/portfolio';
import { useMarketStore } from '@/stores/market';
import { Settings, Zap, Play, BarChart2, CheckCircle2, Circle } from 'lucide-vue-next';

const portfolioStore = usePortfolioStore();
const marketStore = useMarketStore();
defineProps({ collapsed: Boolean });

const strategies = ['RSI', 'SMA_Cross', 'MACD', 'BollingerBands'];
const indicators = [
  { id: 'SMA5', label: 'SMA 5' },
  { id: 'SMA10', label: 'SMA 10' },
  { id: 'SMA20', label: 'SMA 20' },
  { id: 'BB', label: 'Bollinger Bands' },
  { id: 'MACD', label: 'MACD' },
  { id: 'RSI', label: 'RSI' }
];

const sendAction = async (action) => {
  try {
    await fetch('/api/actions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action })
    });
    portfolioStore.fetchPortfolio();
  } catch (e) { console.error(e); }
};
</script>

<template>
  <div class="bg-panel-bg border-l border-border-line flex flex-col transition-all duration-300 shrink-0" :class="collapsed ? 'w-0 overflow-hidden border-none' : 'w-72'">
    <!-- Section 1: Agent Status -->
    <div class="p-4 border-b border-border-line flex items-center justify-between bg-black/20">
      <div class="flex items-center gap-2">
        <Zap class="w-4 h-4" :class="portfolioStore.agentState?.halted ? 'text-text-red' : 'text-text-green'" />
        <span class="font-bold tracking-wider text-gray-400 text-[10px] uppercase">Agent System Status</span>
      </div>
      <Settings :size="14" class="text-gray-500 cursor-pointer hover:text-white" />
    </div>

    <div class="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-6">
      <!-- Account Summary -->
      <div>
        <div class="text-[10px] text-gray-500 mb-3 font-mono uppercase tracking-widest flex items-center gap-2">
          <BarChart2 :size="12" /> Total Asset Value
        </div>
        <div class="bg-gray-900/50 rounded-lg p-3 font-mono text-xs text-gray-300 space-y-2 border border-white/5 shadow-inner">
          <div class="flex justify-between border-b border-gray-800 pb-2 mb-1">
            <span class="text-gray-400">Net Equity (TWD):</span>
            <span class="text-white font-bold">${{ portfolioStore.summary?.total_equity_twd?.toLocaleString(undefined, {maximumFractionDigits:0}) }}</span>
          </div>
          <div class="flex justify-between text-[10px]">
            <span class="text-gray-500">TWD Cash:</span>
            <span>${{ portfolioStore.summary?.cash_twd?.toLocaleString() }}</span>
          </div>
          <div class="flex justify-between text-[10px]">
            <span class="text-gray-500">USD Cash:</span>
            <span>${{ portfolioStore.summary?.cash_usd?.toLocaleString() }}</span>
          </div>
        </div>
      </div>

      <!-- Technical Indicators -->
      <div>
        <div class="text-[10px] text-gray-500 mb-3 font-mono uppercase tracking-widest">Technical Indicators</div>
        <div class="grid grid-cols-2 gap-2">
          <button v-for="ind in indicators" :key="ind.id" 
                  @click="marketStore.toggleIndicator(ind.id)"
                  :class="marketStore.selectedIndicators.includes(ind.id) ? 'bg-blue-600/20 text-blue-400 border-blue-500/50' : 'bg-gray-800/40 text-gray-500 border-gray-700'"
                  class="flex items-center gap-2 px-2 py-1.5 rounded border text-[10px] transition-all hover:border-gray-500">
            <CheckCircle2 v-if="marketStore.selectedIndicators.includes(ind.id)" :size="10" />
            <Circle v-else :size="10" />
            {{ ind.label }}
          </button>
        </div>
      </div>

      <!-- Backtest Configuration -->
      <div class="pt-2 border-t border-gray-800/50">
        <div class="text-[10px] text-gray-500 mb-3 font-mono uppercase tracking-widest flex justify-between items-center">
          <span>Strategy Backtest</span>
          <span v-if="marketStore.isBacktesting" class="text-blue-400 animate-pulse">Running...</span>
        </div>
        <div class="space-y-3">
          <div class="flex flex-col gap-1.5">
            <span class="text-[9px] text-gray-600 uppercase font-bold">Select Logic</span>
            <select v-model="marketStore.selectedStrategy" class="bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-white outline-none focus:border-blue-500 w-full appearance-none">
              <option v-for="s in strategies" :key="s" :value="s">{{ s }} Strategy</option>
            </select>
          </div>
          <button @click="marketStore.runBacktest" 
                  :disabled="marketStore.isBacktesting || !marketStore.currentSymbol"
                  class="w-full py-2 rounded border border-green-500/50 bg-green-900/10 hover:bg-green-900/30 text-text-green font-bold text-[10px] transition-all flex items-center justify-center gap-2 disabled:opacity-30">
            <Play :size="12" /> EXECUTE BACKTEST
          </button>
          
          <!-- Backtest Result Summary -->
          <div v-if="marketStore.backtestResults" class="bg-black/40 rounded border border-gray-800 p-2 space-y-1.5 animate-in fade-in slide-in-from-top-1">
             <div class="flex justify-between text-[10px]">
               <span class="text-gray-500">Total Return:</span>
               <span :class="marketStore.backtestResults.total_return_pct >= 0 ? 'text-text-green' : 'text-text-red'" class="font-bold font-mono">{{ marketStore.backtestResults.total_return_pct }}%</span>
             </div>
             <div class="flex justify-between text-[10px]">
               <span class="text-gray-500">Max Drawdown:</span>
               <span class="text-text-red font-mono">{{ marketStore.backtestResults.max_drawdown_pct }}%</span>
             </div>
             <div class="flex items-center gap-2 mt-2">
                <input type="checkbox" v-model="marketStore.backtestEnabled" id="show-bt" class="scale-75">
                <label for="show-bt" class="text-[9px] text-gray-400 cursor-pointer uppercase">Overlay on Chart</label>
             </div>
          </div>
        </div>
      </div>

      <!-- Risk Control -->
      <div class="pt-2 border-t border-gray-800/50">
        <div class="text-[10px] text-gray-500 mb-3 font-mono uppercase tracking-widest">Risk Management</div>
        <div class="space-y-3 text-xs">
          <div class="flex justify-between items-center">
            <span class="text-gray-400">Take Profit (%)</span>
            <input type="number" v-model="portfolioStore.settings.take_profit_pct" class="w-16 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-right text-white focus:border-blue-500 outline-none">
          </div>
          <div class="flex justify-between items-center">
            <span class="text-gray-400">Stop Loss (%)</span>
            <input type="number" v-model="portfolioStore.settings.stop_loss_pct" class="w-16 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-right text-white focus:border-blue-500 outline-none">
          </div>
        </div>
      </div>
    </div>

    <!-- Actions -->
    <div class="p-4 border-t border-border-line space-y-2 bg-black/10">
      <button @click="sendAction('execute')" :disabled="portfolioStore.agentState?.halted" class="w-full py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-30 text-gray-300 font-bold text-[10px] rounded border border-gray-600 transition tracking-widest">
        ⚡️ FORCE AGENT RUN
      </button>
      <button v-if="!portfolioStore.agentState?.halted" @click="sendAction('halt')" class="w-full py-2 bg-red-900/20 hover:bg-red-900/40 text-text-red font-bold text-[10px] rounded border border-text-red/50 transition tracking-widest uppercase">
        Emergency Halt
      </button>
      <button v-else @click="sendAction('resume')" class="w-full py-2 bg-green-900/20 hover:bg-green-900/40 text-text-green font-bold text-[10px] rounded border border-text-green/50 transition tracking-widest uppercase">
        Resume Trading
      </button>
    </div>
  </div>
</template>
