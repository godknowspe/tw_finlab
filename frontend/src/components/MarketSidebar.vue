<script setup>
import { ref, onMounted, nextTick, watch } from 'vue';
import { useMarketStore } from '@/stores/market';
import { usePortfolioStore } from '@/stores/portfolio';
import Sortable from 'sortablejs';
import { Plus, X, TrendingUp, Briefcase, History, RefreshCw } from 'lucide-vue-next';

const marketStore = useMarketStore();
const portfolioStore = usePortfolioStore();

const activeTab = ref('watchlist');
const isSyncing = ref(false);

const syncTrades = async () => {
  if (isSyncing.value) return;
  isSyncing.value = true;
  try {
    const res = await portfolioStore.syncTrades();
    alert(res.message);
  } catch (e) {
    alert("Sync failed: " + (e.response?.data?.message || e.message));
  } finally {
    isSyncing.value = false;
  }
};

const sortableTW = ref(null);
const sortableUS = ref(null);

const initSortable = () => {
  const options = { animation: 150, delay: 200, delayOnTouchOnly: true };
  if (sortableTW.value && !sortableTW.value._sortable) sortableTW.value._sortable = new Sortable(sortableTW.value, options);
  if (sortableUS.value && !sortableUS.value._sortable) sortableUS.value._sortable = new Sortable(sortableUS.value, options);
};

onMounted(() => initSortable());
watch(() => activeTab.value, () => { if(activeTab.value === 'watchlist') nextTick(initSortable); });
</script>

<template>
  <div class="w-72 bg-[#161b22] border-r border-border-line flex flex-col h-full shadow-xl z-20">
    <div class="p-3 border-b border-border-line grid grid-cols-3 gap-1 bg-black/20">
      <button v-for="tab in ['watchlist', 'positions', 'trades']" :key="tab" @click="activeTab = tab" 
              :class="activeTab === tab ? 'bg-gray-800 text-white shadow-sm' : 'text-gray-500 hover:text-gray-400'"
              class="py-1.5 text-[10px] font-bold rounded uppercase transition-all tracking-tighter">
        {{ tab }}
      </button>
    </div>

    <!-- Watchlist -->
    <div v-if="activeTab === 'watchlist'" class="flex-1 flex flex-col min-h-0">
      <div class="flex justify-between px-4 py-2 text-[10px] text-gray-500 border-b border-border-line items-center bg-[#0d1117] sticky top-0 z-10">
        <span>SYMBOL</span>
        <div class="flex items-center gap-4 mr-2">
          <span>LAST</span>
          <span>CHG%</span>
        </div>
      </div>
      <div class="flex-1 overflow-y-auto custom-scrollbar">
        <div v-if="marketStore.watchlistTW.length" class="text-[9px] text-gray-600 font-bold px-4 py-1.5 bg-black/10 uppercase tracking-widest">TW Market</div>
        <div ref="sortableTW">
          <div v-for="item in marketStore.watchlistTW" :key="item.symbol" 
               @click="marketStore.setCurrentSymbol(item.symbol)"
               :class="marketStore.currentSymbol === item.symbol ? 'bg-blue-900/20 border-l-2 border-blue-500' : 'border-l-2 border-transparent'"
               class="flex justify-between items-center px-4 py-3 border-b border-white/5 hover:bg-gray-800/50 cursor-pointer transition-colors">
            <div class="flex-1 min-w-0">
               <div class="font-bold text-white text-sm">{{ item.symbol }}</div>
               <div class="text-[10px] text-gray-500 truncate">{{ item.name }}</div>
            </div>
            <div class="text-right shrink-0">
               <div class="font-mono text-sm text-white">{{ item.last?.toFixed(2) }}</div>
               <div class="text-[10px] font-mono" :class="item.chg_pct?.startsWith('+') ? 'text-text-green' : 'text-text-red'">{{ item.chg_pct }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Positions -->
    <div v-if="activeTab === 'positions'" class="flex-1 flex flex-col min-h-0">
       <div class="flex justify-between px-4 py-2 text-[10px] text-gray-500 border-b border-border-line items-center bg-[#0d1117]">
        <span>SYMBOL / QTY</span>
        <span>UNREALIZED</span>
      </div>
      <div class="flex-1 overflow-y-auto">
        <div v-for="pos in portfolioStore.positions" :key="pos.symbol" 
             class="flex justify-between items-center px-4 py-3 border-b border-white/5 hover:bg-gray-800/50 cursor-pointer"
             :class="marketStore.currentSymbol === pos.symbol ? 'bg-blue-900/20' : ''"
             @click="marketStore.setCurrentSymbol(pos.symbol)">
          <div>
            <div class="font-bold text-white text-sm flex items-center gap-2">
              <span class="text-[9px] px-1 rounded bg-gray-700 text-gray-400">{{ pos.currency === 'USD' ? '🇺🇸' : '🇹🇼' }}</span>
              {{ pos.symbol }}
            </div>
            <div class="text-[10px] text-blue-400 font-mono">{{ pos.shares.toLocaleString() }} @ {{ pos.avg_cost.toFixed(2) }}</div>
          </div>
          <div class="text-right">
            <div class="text-sm font-mono font-bold" :class="pos.unrealized >= 0 ? 'text-text-green' : 'text-text-red'">
              {{ pos.unrealized > 0 ? '+' : '' }}{{ pos.unrealized.toLocaleString() }}
            </div>
            <div class="text-[9px] font-mono opacity-50" :class="pos.unrealized >= 0 ? 'text-text-green' : 'text-text-red'">
               {{ ((pos.unrealized / (Math.max(1, pos.shares * pos.avg_cost))) * 100).toFixed(2) }}%
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Trades -->
    <div v-if="activeTab === 'trades'" class="flex-1 flex flex-col min-h-0">
      <div class="flex justify-between px-4 py-2 text-[10px] text-gray-500 border-b border-border-line items-center bg-[#0d1117]">
        <span>ACTION / SYM</span>
        <div class="flex items-center gap-2">
          <RefreshCw :size="12" class="text-blue-400 cursor-pointer" :class="isSyncing ? 'animate-spin' : ''" @click="syncTrades" />
          <Plus :size="12" class="text-gray-500 hover:text-white cursor-pointer" />
        </div>
      </div>
      <div class="flex-1 overflow-y-auto">
        <div v-for="trade in portfolioStore.trades" :key="trade.id" 
             class="flex justify-between items-center px-4 py-3 border-b border-white/5 hover:bg-gray-800/50">
          <div>
            <div class="font-bold text-white text-xs">
              <span :class="trade.action === 'BUY' ? 'text-red-400' : 'text-green-400'">{{ trade.action }}</span> {{ trade.symbol }}
            </div>
            <div class="text-[9px] text-gray-600 font-mono">{{ trade.timestamp.substring(5, 16).replace('T', ' ') }}</div>
          </div>
          <div class="text-right">
            <div class="text-xs text-white font-mono">{{ trade.shares }}股</div>
            <div class="text-[10px] text-gray-500 font-mono">@{{ trade.price.toFixed(2) }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
