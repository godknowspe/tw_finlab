<script setup>
import { ref, onMounted, nextTick, watch } from 'vue';
import { useMarketStore } from '@/stores/market';
import { usePortfolioStore } from '@/stores/portfolio';
import Sortable from 'sortablejs';
import { Plus, X, TrendingUp, Briefcase, History, RefreshCw, Trash2 } from 'lucide-vue-next';

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



const showWatchlistModal = ref(false);
const newSymbol = ref({ symbol: '', market: 'TW' });

const submitWatchlist = async () => {
  if (!newSymbol.value.symbol) return alert("請輸入股票代號");
  try {
    await marketStore.addToWatchlist(newSymbol.value.symbol.toUpperCase(), newSymbol.value.market);
    showWatchlistModal.value = false;
    newSymbol.value.symbol = '';
  } catch (e) {
    alert("新增失敗");
  }
};

const deleteWatchlist = async (symbol) => {
  if (confirm(`確定要從自選股刪除 ${symbol} 嗎？`)) {
    await marketStore.removeFromWatchlist(symbol);
  }
};

const showAddModal = ref(false);
const newTrade = ref({
  symbol: '',
  action: 'BUY',
  shares: 1000,
  price: 0,
  currency: 'TWD',
  timestamp: new Date().toISOString().slice(0, 16)
});

const submitTrade = async () => {
  if (!newTrade.value.symbol || newTrade.value.shares <= 0 || newTrade.value.price <= 0) {
    return alert("請填寫完整的交易資訊");
  }
  try {
    await portfolioStore.addTrade(newTrade.value);
    showAddModal.value = false;
    newTrade.value = {
      symbol: '', action: 'BUY', shares: 1000, price: 0, currency: 'TWD', timestamp: new Date().toISOString().slice(0, 16)
    };
  } catch (e) {
    alert("新增失敗");
  }
};

const sortableTW = ref(null);
const sortableUS = ref(null);


const deleteTrade = async (id) => {
  if (confirm("確定要刪除這筆交易紀錄嗎？")) {
    await portfolioStore.deleteTrade(id);
  }
};

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
          <span>LAST / CHG%</span>
          <Plus @click="showWatchlistModal = true" :size="12" class="text-gray-500 hover:text-white cursor-pointer ml-1" title="Add to Watchlist" />
        </div>
      </div>
      <div class="flex-1 overflow-y-auto custom-scrollbar pb-10">
        <div v-if="marketStore.watchlistTW.length" class="text-[9px] text-gray-600 font-bold px-4 py-1.5 bg-black/10 uppercase tracking-widest">TW Market</div>
        <div ref="sortableTW">
          <div v-for="item in marketStore.watchlistTW" :key="item.symbol" 
               @click="marketStore.setCurrentSymbol(item.symbol)"
                              :class="[marketStore.currentSymbol === item.symbol ? 'bg-blue-900/20 border-l-2 border-blue-500' : 'border-l-2 border-transparent', item.flashClass]"
               class="flex justify-between items-center px-4 py-3 border-b border-white/5 hover:bg-gray-800/50 cursor-pointer transition-colors">
            <div class="flex-1 min-w-0">
               <div class="font-bold text-white text-sm">{{ item.symbol }}</div>
               <div class="text-[10px] text-gray-500 truncate">{{ item.name }}</div>
            </div>
            <div class="flex items-center gap-3 shrink-0">
              <div class="text-right">
                 <div class="font-mono text-sm text-white">{{ item.last?.toFixed(2) }}</div>
                 <div class="text-[10px] font-mono" :class="item.chg_pct?.startsWith('+') ? 'text-text-green' : 'text-text-red'">{{ item.chg_pct }}</div>
              </div>
              <button @click.stop="deleteWatchlist(item.symbol)" class="text-gray-600 hover:text-red-400 transition-colors cursor-pointer" title="Remove">
                <Trash2 :size="12" />
              </button>
            </div>
          </div>
        </div>

        <div v-if="marketStore.watchlistUS.length" class="text-[9px] text-gray-600 font-bold px-4 py-1.5 bg-black/10 uppercase tracking-widest mt-4">US Market</div>
        <div ref="sortableUS">
          <div v-for="item in marketStore.watchlistUS" :key="item.symbol" 
               @click="marketStore.setCurrentSymbol(item.symbol)"
                              :class="[marketStore.currentSymbol === item.symbol ? 'bg-blue-900/20 border-l-2 border-blue-500' : 'border-l-2 border-transparent', item.flashClass]"
               class="flex justify-between items-center px-4 py-3 border-b border-white/5 hover:bg-gray-800/50 cursor-pointer transition-colors">
            <div class="flex-1 min-w-0">
               <div class="font-bold text-white text-sm">{{ item.symbol }}</div>
               <div class="text-[10px] text-gray-500 truncate">{{ item.name }}</div>
            </div>
            <div class="flex items-center gap-3 shrink-0">
              <div class="text-right">
                 <div class="font-mono text-sm text-white">{{ item.last?.toFixed(2) }}</div>
                 <div class="text-[10px] font-mono" :class="item.chg_pct?.startsWith('+') ? 'text-text-green' : 'text-text-red'">{{ item.chg_pct }}</div>
              </div>
              <button @click.stop="deleteWatchlist(item.symbol)" class="text-gray-600 hover:text-red-400 transition-colors cursor-pointer" title="Remove">
                <Trash2 :size="12" />
              </button>
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
      <div class="flex-1 overflow-y-auto custom-scrollbar pb-10">
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
          <Plus @click="showAddModal = true" :size="12" class="text-gray-500 hover:text-white cursor-pointer" />
        </div>
      </div>
      <div class="flex-1 overflow-y-auto custom-scrollbar pb-10">
        <div v-for="trade in portfolioStore.trades" :key="trade.id" 
             class="flex justify-between items-center px-4 py-3 border-b border-white/5 hover:bg-gray-800/50">
          <div>
            <div class="font-bold text-white text-xs">
              <span :class="trade.action === 'BUY' ? 'text-red-400' : 'text-green-400'">{{ trade.action }}</span> {{ trade.symbol }}
            </div>
            <div class="text-[9px] text-gray-600 font-mono">{{ trade.timestamp.substring(5, 16).replace('T', ' ') }}</div>
          </div>
          <div class="flex items-center gap-3">
            <div class="text-right">
              <div class="text-xs text-white font-mono">{{ trade.shares }}股</div>
              <div class="text-[10px] text-gray-500 font-mono">@{{ trade.price.toFixed(2) }}</div>
            </div>
            <button @click.stop="deleteTrade(trade.id)" class="text-gray-600 hover:text-red-400 transition-colors cursor-pointer" title="Delete Trade">
              <Trash2 :size="14" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>

    
    <!-- Add Watchlist Modal -->
    <div v-if="showWatchlistModal" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center">
      <div class="bg-gray-900 border border-gray-700 p-5 rounded-lg w-80 shadow-2xl flex flex-col gap-4">
        <div class="flex justify-between items-center border-b border-gray-800 pb-2">
          <h3 class="text-white font-bold text-sm">新增自選股</h3>
          <X @click="showWatchlistModal = false" class="text-gray-500 hover:text-white cursor-pointer" :size="16" />
        </div>
        
        <div class="flex flex-col gap-3 text-xs text-gray-300">
          <div class="flex flex-col gap-1">
            <label>股票代號 (Symbol)</label>
            <input v-model="newSymbol.symbol" @keyup.enter="submitWatchlist" type="text" class="bg-black border border-gray-700 rounded px-2 py-1.5 outline-none focus:border-blue-500 uppercase" placeholder="e.g. 2330 或 AAPL">
          </div>
          
          <div class="flex flex-col gap-1">
            <label>市場 (Market)</label>
            <select v-model="newSymbol.market" class="bg-black border border-gray-700 rounded px-2 py-1.5 outline-none focus:border-blue-500">
              <option value="TW">台股 (TW Market)</option>
              <option value="US">美股 (US Market)</option>
            </select>
          </div>
        </div>

        <div class="mt-2 flex justify-end gap-2">
          <button @click="showWatchlistModal = false" class="px-4 py-1.5 rounded text-gray-400 hover:text-white transition-colors">取消</button>
          <button @click="submitWatchlist" class="bg-blue-600 hover:bg-blue-500 text-white font-bold px-4 py-1.5 rounded transition-colors">新增</button>
        </div>
      </div>
    </div>

    <!-- Add Trade Modal -->
    <div v-if="showAddModal" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center">
      <div class="bg-gray-900 border border-gray-700 p-5 rounded-lg w-80 shadow-2xl flex flex-col gap-4">
        <div class="flex justify-between items-center border-b border-gray-800 pb-2">
          <h3 class="text-white font-bold text-sm">新增手動交易紀錄</h3>
          <X @click="showAddModal = false" class="text-gray-500 hover:text-white cursor-pointer" :size="16" />
        </div>
        
        <div class="flex flex-col gap-3 text-xs text-gray-300">
          <div class="flex flex-col gap-1">
            <label>股票代號 (Symbol)</label>
            <input v-model="newTrade.symbol" type="text" class="bg-black border border-gray-700 rounded px-2 py-1.5 outline-none focus:border-blue-500 uppercase" placeholder="e.g. 2330.TW or AAPL">
          </div>
          
          <div class="flex gap-2">
            <div class="flex flex-col gap-1 flex-1">
              <label>買/賣 (Action)</label>
              <select v-model="newTrade.action" class="bg-black border border-gray-700 rounded px-2 py-1.5 outline-none focus:border-blue-500">
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
              </select>
            </div>
            <div class="flex flex-col gap-1 flex-1">
              <label>幣別 (Currency)</label>
              <select v-model="newTrade.currency" class="bg-black border border-gray-700 rounded px-2 py-1.5 outline-none focus:border-blue-500">
                <option value="TWD">TWD</option>
                <option value="USD">USD</option>
              </select>
            </div>
          </div>

          <div class="flex gap-2">
            <div class="flex flex-col gap-1 flex-1">
              <label>股數 (Shares)</label>
              <input v-model.number="newTrade.shares" type="number" min="1" class="bg-black border border-gray-700 rounded px-2 py-1.5 outline-none focus:border-blue-500">
            </div>
            <div class="flex flex-col gap-1 flex-1">
              <label>成交價 (Price)</label>
              <input v-model.number="newTrade.price" type="number" step="0.01" min="0.01" class="bg-black border border-gray-700 rounded px-2 py-1.5 outline-none focus:border-blue-500">
            </div>
          </div>

          <div class="flex flex-col gap-1">
            <label>時間 (Time)</label>
            <input v-model="newTrade.timestamp" type="datetime-local" class="bg-black border border-gray-700 rounded px-2 py-1.5 outline-none focus:border-blue-500">
          </div>
        </div>

        <div class="mt-2 flex justify-end gap-2">
          <button @click="showAddModal = false" class="px-4 py-1.5 rounded text-gray-400 hover:text-white transition-colors">取消</button>
          <button @click="submitTrade" class="bg-blue-600 hover:bg-blue-500 text-white font-bold px-4 py-1.5 rounded transition-colors">新增紀錄</button>
        </div>
      </div>
    </div>

</template>

<style scoped>
.flash-green {
  animation: flashGreen 0.5s ease-out;
}
@keyframes flashGreen {
  0% { background-color: rgba(63, 185, 80, 0.5); }
  100% { background-color: transparent; }
}
</style>
