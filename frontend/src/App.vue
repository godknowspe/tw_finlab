<script setup>
import { onMounted, ref } from 'vue';
import MarketSidebar from './components/MarketSidebar.vue';
import TradingViewChart from './components/TradingViewChart.vue';
import ControlPanel from './components/ControlPanel.vue';
import { useMarketStore } from './stores/market';
import { usePortfolioStore } from './stores/portfolio';
import { Layout } from 'lucide-vue-next';

const marketStore = useMarketStore();
const portfolioStore = usePortfolioStore();

const chartMode = ref('symbol');
const showRightPanel = ref(true);

onMounted(() => {
  marketStore.fetchWatchlist();
  portfolioStore.fetchPortfolio();
  marketStore.connectWebSocket();
});
</script>

<template>
  <div class="flex w-screen h-screen bg-[#0d1117] text-[#c9d1d9] overflow-hidden font-sans">
    <!-- Left Sidebar -->
    <MarketSidebar class="flex-shrink-0" />

    <!-- Main Content -->
    <div class="flex-1 flex flex-col min-w-0 border-r border-border-line">
      <!-- Top Bar -->
      <div class="h-12 border-b border-border-line flex items-center justify-between px-4 bg-[#161b22]/50 shrink-0">
        <div class="flex items-center gap-4">
          <div class="flex bg-gray-900 rounded p-1 border border-gray-700 shadow-inner">
            <button @click="chartMode = 'symbol'" :class="chartMode === 'symbol' ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'" class="px-3 py-0.5 text-[10px] rounded font-bold transition-colors uppercase">Symbol</button>
            <button @click="chartMode = 'equity'" :class="chartMode === 'equity' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-gray-300'" class="px-3 py-0.5 text-[10px] rounded font-bold transition-colors uppercase">Equity</button>
          </div>
          <span class="font-bold text-sm text-white tracking-tight uppercase">{{ chartMode === 'symbol' ? (marketStore.currentSymbol || 'Select Symbol') : 'Portfolio Equity' }}</span>
        </div>

        <button @click="showRightPanel = !showRightPanel" class="text-gray-500 hover:text-white px-3 py-1.5 rounded bg-gray-800/50 border border-gray-700 text-[10px] transition-all flex items-center gap-2 hover:bg-gray-800">
          <Layout :size="14" />
          {{ showRightPanel ? 'HIDE CONTROLS' : 'SHOW CONTROLS' }}
        </button>
      </div>

      <!-- Chart Area -->
      <div class="flex-1 relative bg-black/20">
        <TradingViewChart :mode="chartMode" :symbol="marketStore.currentSymbol" />
      </div>
    </div>

    <!-- Right Sidebar -->
    <ControlPanel :collapsed="!showRightPanel" class="flex-shrink-0" />
  </div>
</template>

<style>
@font-face {
  font-family: 'Inter';
  src: url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
}

.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #30363d;
  border-radius: 10px;
}
</style>
