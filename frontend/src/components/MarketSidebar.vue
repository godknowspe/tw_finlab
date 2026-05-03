<script setup>
import { ref } from 'vue';
import { useMarketStore } from '@/stores/market';
import { TrendingUp, Briefcase } from 'lucide-vue-next';

const marketStore = useMarketStore();
const activeTab = ref('watchlist');
</script>
<template>
  <div class="w-64 bg-panel-bg border-r border-border-line flex flex-col h-full shrink-0">
    <div class="p-4 border-b border-border-line flex justify-between">
      <button @click="activeTab = 'watchlist'" :class="activeTab === 'watchlist' ? 'text-white' : 'text-gray-500'" class="text-xs font-bold flex items-center gap-1"><TrendingUp :size="14"/> WATCHLIST</button>
      <button @click="activeTab = 'positions'" :class="activeTab === 'positions' ? 'text-white' : 'text-gray-500'" class="text-xs font-bold flex items-center gap-1"><Briefcase :size="14"/> POSITIONS</button>
    </div>
    <div class="flex-1 overflow-y-auto">
      <div v-for="item in marketStore.watchlist" :key="item.symbol" @click="marketStore.setCurrentSymbol(item.symbol)" class="p-3 border-b border-border-line cursor-pointer hover:bg-gray-800">
        {{ item.symbol }}
      </div>
    </div>
  </div>
</template>
