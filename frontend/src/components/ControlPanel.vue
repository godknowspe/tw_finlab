<script setup>
import { usePortfolioStore } from '@/stores/portfolio';
import { Settings, Zap } from 'lucide-vue-next';
const portfolioStore = usePortfolioStore();
defineProps({ collapsed: Boolean });
</script>
<template>
  <div class="bg-panel-bg border-l border-border-line flex flex-col transition-all duration-300 shrink-0" :class="collapsed ? 'w-0 overflow-hidden border-none' : 'w-72'">
    <div class="p-4 border-b border-border-line flex items-center justify-between">
      <div class="flex items-center gap-2"><Zap class="w-4 h-4 text-text-green"/><span class="text-xs uppercase text-gray-400 font-bold">Agent</span></div>
      <Settings :size="16" class="text-gray-500 cursor-pointer"/>
    </div>
    <div class="p-4 flex-1 overflow-y-auto">
      <div class="text-xs text-gray-500 mb-2 font-mono uppercase">[Summary]</div>
      <div class="bg-gray-900 rounded p-3 font-mono text-xs text-gray-300">
        Total: ${{ portfolioStore.summary?.equiv_total_equity_twd?.toLocaleString() }}
      </div>
    </div>
  </div>
</template>
