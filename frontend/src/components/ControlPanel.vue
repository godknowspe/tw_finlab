<script setup>
import { usePortfolioStore } from '@/stores/portfolio';
import { Settings, Zap, Octagon, Play } from 'lucide-vue-next';

const portfolioStore = usePortfolioStore();
defineProps({ collapsed: Boolean });

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
    <div class="p-4 border-b border-border-line flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Zap class="w-4 h-4" :class="portfolioStore.agentState?.halted ? 'text-text-red' : 'text-text-green'" />
        <span class="font-bold tracking-wider text-gray-400 text-xs uppercase">Agent Logic</span>
      </div>
      <Settings :size="16" class="text-gray-500 cursor-pointer hover:text-white" />
    </div>

    <div class="p-4 flex-1 overflow-y-auto space-y-6">
      <div>
        <div class="text-[10px] text-gray-500 mb-2 font-mono uppercase tracking-widest">[Account Summary]</div>
        <div class="bg-gray-900/50 rounded-lg p-3 font-mono text-xs text-gray-300 space-y-2 border border-white/5">
          <div class="flex justify-between border-b border-gray-800 pb-2 mb-1">
            <span class="text-gray-400">Total (TWD):</span>
            <span class="text-white font-bold">${{ portfolioStore.summary?.total_equity_twd?.toLocaleString(undefined, {maximumFractionDigits:0}) }}</span>
          </div>
          <div class="flex justify-between text-[10px]">
            <span class="text-gray-500">TW Cash:</span>
            <span>${{ portfolioStore.summary?.cash_twd?.toLocaleString() }}</span>
          </div>
          <div class="flex justify-between text-[10px]">
            <span class="text-gray-500">US Cash:</span>
            <span>$${{ portfolioStore.summary?.cash_usd?.toLocaleString() }}</span>
          </div>
        </div>
      </div>

      <div>
        <div class="text-[10px] text-gray-500 mb-2 font-mono uppercase tracking-widest">[Strategy Params]</div>
        <div class="space-y-3 text-xs">
          <div class="flex justify-between items-center">
            <span class="text-gray-400">TP (%)</span>
            <input type="number" v-model="portfolioStore.settings.take_profit_pct" class="w-16 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-right text-white focus:border-blue-500 outline-none">
          </div>
          <div class="flex justify-between items-center">
            <span class="text-gray-400">SL (%)</span>
            <input type="number" v-model="portfolioStore.settings.stop_loss_pct" class="w-16 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-right text-white focus:border-blue-500 outline-none">
          </div>
        </div>
      </div>
    </div>

    <div class="p-4 border-t border-border-line space-y-2">
      <button @click="sendAction('execute')" :disabled="portfolioStore.agentState?.halted" class="w-full py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-30 text-gray-300 font-bold text-[10px] rounded border border-gray-600 transition">
        ⚡️ FORCE EXECUTE
      </button>
      <button v-if="!portfolioStore.agentState?.halted" @click="sendAction('halt')" class="w-full py-2 bg-red-900/20 hover:bg-red-900/40 text-text-red font-bold text-[10px] rounded border border-text-red/50 transition">
        EMERGENCY HALT
      </button>
      <button v-else @click="sendAction('resume')" class="w-full py-2 bg-green-900/20 hover:bg-green-900/40 text-text-green font-bold text-[10px] rounded border border-text-green/50 transition">
        RESUME TRADING
      </button>
    </div>
  </div>
</template>
