<script setup>
import { onMounted, ref } from 'vue';
import MarketSidebar from './components/MarketSidebar.vue';
import TradingViewChart from './components/TradingViewChart.vue';
import ControlPanel from './components/ControlPanel.vue';
import { useMarketStore } from './stores/market';
import { usePortfolioStore } from './stores/portfolio';

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
  <div class="flex w-full h-full bg-[#0d1117] overflow-hidden">
    <!-- Left Sidebar -->
    <MarketSidebar />

    <!-- Main Content -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- Top Bar -->
      <div class="h-12 border-b border-border-line flex items-center justify-between px-4 shrink-0">
        <div class="flex items-center gap-4">
          <div class="flex bg-gray-900 rounded p-1 border border-gray-700">
            <button @click="chartMode = 'symbol'" :class="chartMode === 'symbol' ? 'bg-gray-700 text-white' : 'text-gray-500'" class="px-3 py-0.5 text-xs rounded font-bold">SYMBOL</button>
            <button @click="chartMode = 'equity'" :class="chartMode === 'equity' ? 'bg-blue-600 text-white' : 'text-gray-500'" class="px-3 py-0.5 text-xs rounded font-bold">EQUITY</button>
          </div>
          <span class="font-bold text-lg text-white">{{ chartMode === 'symbol' ? marketStore.currentSymbol : 'TOTAL EQUITY' }}</span>
        </div>

        <button @click="showRightPanel = !showRightPanel" class="text-gray-500 hover:text-white px-2 py-1 rounded bg-gray-800 border border-gray-700 text-xs transition-colors flex items-center gap-1">
          {{ showRightPanel ? 'Hide Console' : 'Show Console' }}
        </button>
      </div>

      <!-- Chart Area -->
      <div class="flex-1 relative">
        <TradingViewChart :mode="chartMode" :symbol="marketStore.currentSymbol" />
      </div>
    </div>

    <!-- Right Sidebar -->
    <ControlPanel :collapsed="!showRightPanel" />
  </div>
</template>
