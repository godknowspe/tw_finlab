<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue';
import { useMarketStore } from '@/stores/market';
import { usePortfolioStore } from '@/stores/portfolio';
import Sortable from 'sortablejs';
import axios from 'axios';
import { Plus, Edit2, X, TrendingUp, Briefcase, History } from 'lucide-vue-next';

const marketStore = useMarketStore();
const portfolioStore = usePortfolioStore();

const activeTab = ref('watchlist');
const sortableTW = ref(null);
const sortableUS = ref(null);

const saveOrder = async () => {
  const getOrder = (refEl) => {
    if (!refEl.value) return [];
    return Array.from(refEl.value.children).map(el => el.getAttribute('data-id')).filter(Boolean);
  };
  const symbols = [...getOrder(sortableTW), ...getOrder(sortableUS)];
  try {
    await axios.put('/api/watchlist/reorder', { symbols });
  } catch (e) {
    console.error("Reorder failed", e);
  }
};

const initSortable = () => {
  if (sortableTW.value && !sortableTW.value._sortable) {
    sortableTW.value._sortable = new Sortable(sortableTW.value, {
      animation: 150,
      delay: 200,
      delayOnTouchOnly: true,
      onEnd: saveOrder
    });
  }
  if (sortableUS.value && !sortableUS.value._sortable) {
    sortableUS.value._sortable = new Sortable(sortableUS.value, {
      animation: 150,
      delay: 200,
      delayOnTouchOnly: true,
      onEnd: saveOrder
    });
  }
};

watch([() => marketStore.watchlistTW, () => marketStore.watchlistUS], async () => {
  await nextTick();
  initSortable();
}, { deep: true });

onMounted(() => {
  initSortable();
});

const selectSymbol = (symbol) => {
  marketStore.setCurrentSymbol(symbol);
};
</script>

<template>
  <div class="w-72 bg-panel-bg border-r border-border-line flex flex-col h-full shrink-0">
    <div class="p-4 border-b border-border-line flex justify-between items-center bg-black/20">
      <button @click="activeTab = 'watchlist'" :class="activeTab === 'watchlist' ? 'text-white' : 'text-gray-500'" class="font-bold tracking-wider text-[10px] hover:text-white transition-colors flex items-center gap-1">
        <TrendingUp :size="12" /> WATCHLIST
      </button>
      <button @click="activeTab = 'positions'" :class="activeTab === 'positions' ? 'text-white' : 'text-gray-500'" class="font-bold tracking-wider text-[10px] hover:text-white transition-colors flex items-center gap-1">
        <Briefcase :size="12" /> POSITIONS
      </button>
      <button @click="activeTab = 'trades'" :class="activeTab === 'trades' ? 'text-white' : 'text-gray-500'" class="font-bold tracking-wider text-[10px] hover:text-white transition-colors flex items-center gap-1">
        <History :size="12" /> TRADES
      </button>
    </div>

    <!-- Watchlist Tab -->
    <div v-if="activeTab === 'watchlist'" class="flex-1 flex flex-col min-h-0">
      <div class="flex justify-between px-4 py-2 text-[10px] text-gray-500 border-b border-border-line items-center bg-[#0d1117]">
        <span>SYM / NAME</span>
        <div class="flex items-center gap-4">
          <span>LAST</span>
          <span>CHG%</span>
          <Plus :size="12" class="text-blue-400 cursor-pointer" />
        </div>
      </div>
      <div class="flex-1 overflow-y-auto">
        <div v-if="marketStore.watchlistTW.length > 0" class="text-[9px] text-gray-600 font-bold px-4 py-1 bg-black/10">TW MARKET</div>
        <div ref="sortableTW">
          <div v-for="item in marketStore.watchlistTW" :key="item.symbol" :data-id="item.symbol"
               class="flex justify-between items-center px-4 py-3 border-b border-border-line hover:bg-gray-800 cursor-pointer"
               :class="[marketStore.currentSymbol === item.symbol ? 'bg-gray-800' : '', item.flashClass]"
               @click="selectSymbol(item.symbol)">
            <div class="min-w-0 flex-1">
              <div class="font-bold text-white text-sm truncate">{{ item.symbol }}</div>
              <div class="text-[10px] text-gray-500 truncate">{{ item.name }}</div>
            </div>
            <div class="text-right ml-2 shrink-0">
              <div class="font-mono text-white text-sm">{{ item.last?.toFixed(2) }}</div>
              <div class="text-[10px] font-mono" :class="item.chg_pct?.startsWith('+') ? 'text-text-green' : 'text-text-red'">
                {{ item.chg_pct }}
              </div>
            </div>
          </div>
        </div>

        <div v-if="marketStore.watchlistUS.length > 0" class="text-[9px] text-gray-600 font-bold px-4 py-1 mt-2 bg-black/10">US MARKET</div>
        <div ref="sortableUS">
          <div v-for="item in marketStore.watchlistUS" :key="item.symbol" :data-id="item.symbol"
               class="flex justify-between items-center px-4 py-3 border-b border-border-line hover:bg-gray-800 cursor-pointer"
               :class="[marketStore.currentSymbol === item.symbol ? 'bg-gray-800' : '', item.flashClass]"
               @click="selectSymbol(item.symbol)">
            <div class="min-w-0 flex-1">
              <div class="font-bold text-white text-sm truncate">{{ item.symbol }}</div>
              <div class="text-[10px] text-gray-500 truncate">{{ item.name }}</div>
            </div>
            <div class="text-right ml-2 shrink-0">
              <div class="font-mono text-white text-sm">{{ item.last?.toFixed(2) }}</div>
              <div class="text-[10px] font-mono" :class="item.chg_pct?.startsWith('+') ? 'text-text-green' : 'text-text-red'">
                {{ item.chg_pct }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Positions Tab -->
    <div v-if="activeTab === 'positions'" class="flex-1 flex flex-col min-h-0">
      <div class="flex justify-between px-4 py-2 text-[10px] text-gray-500 border-b border-border-line items-center bg-[#0d1117]">
        <span>SYM / QTY</span>
        <span>UNREALIZED</span>
      </div>
      <div class="flex-1 overflow-y-auto">
        <div v-for="pos in portfolioStore.positions" :key="pos.symbol" 
             class="flex justify-between items-center px-4 py-3 border-b border-border-line hover:bg-gray-800 cursor-pointer"
             :class="marketStore.currentSymbol === pos.symbol ? 'bg-gray-800' : ''"
             @click="selectSymbol(pos.symbol)">
          <div>
            <div class="font-bold text-white text-sm flex items-center gap-2">
              <span class="text-[9px] px-1 rounded bg-gray-700 text-gray-400">{{ pos.currency === 'USD' ? '🇺🇸' : '🇹🇼' }}</span>
              {{ pos.symbol }}
            </div>
            <div class="text-[10px] text-blue-400 font-mono">
              {{ pos.shares.toLocaleString() }} @ {{ pos.avg_cost.toFixed(2) }}
            </div>
          </div>
          <div class="text-right">
            <div class="text-sm font-mono font-bold" :class="pos.unrealized >= 0 ? 'text-text-green' : 'text-text-red'">
              {{ pos.unrealized > 0 ? '+' : '' }}{{ pos.unrealized.toLocaleString() }}
            </div>
            <div class="text-[10px] font-mono opacity-60" :class="pos.unrealized >= 0 ? 'text-text-green' : 'text-text-red'">
               {{ ((pos.unrealized / (Math.max(1, pos.shares * pos.avg_cost))) * 100).toFixed(2) }}%
            </div>
          </div>
        </div>
        <div v-if="!portfolioStore.positions || portfolioStore.positions.length === 0" class="p-4 text-center text-gray-500 text-xs">
          No open positions.
        </div>
      </div>
    </div>

    <!-- Trades Tab -->
    <div v-if="activeTab === 'trades'" class="flex-1 flex flex-col min-h-0">
      <div class="flex justify-between px-4 py-2 text-[10px] text-gray-500 border-b border-border-line items-center bg-[#0d1117]">
        <span>ACTION/SYM</span>
        <span>PRICE</span>
      </div>
      <div class="flex-1 overflow-y-auto">
        <div v-for="trade in portfolioStore.trades" :key="trade.id" 
             class="flex justify-between items-center px-4 py-3 border-b border-border-line hover:bg-gray-800 cursor-pointer group">
          <div>
            <div class="font-bold text-white text-sm">
              <span :class="trade.action === 'BUY' ? 'text-red-400' : 'text-green-400'">{{ trade.action }}</span> {{ trade.symbol }}
            </div>
            <div class="text-[9px] text-gray-600 font-mono">{{ trade.timestamp.substring(5, 16).replace('T', ' ') }}</div>
          </div>
          <div class="text-right">
            <div class="text-xs text-white font-mono">{{ trade.shares }}</div>
            <div class="text-[10px] text-gray-500 font-mono">@{{ trade.price.toFixed(2) }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
