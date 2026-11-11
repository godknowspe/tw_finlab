<script setup>
import { ref, computed } from 'vue';
import { useMarketStore } from '@/stores/market';
import { usePortfolioStore, apiError } from '@/stores/portfolio';
import { Plus, X, TrendingUp, Briefcase, History, RefreshCw, Trash2 } from 'lucide-vue-next';

const marketStore = useMarketStore();
const portfolioStore = usePortfolioStore();

const activeTab = ref('watchlist');

// Holdings value in TWD, using the same USD/TWD rate as Net Equity, so the weights sum to 100%.
const fx = computed(() => portfolioStore.summary?.usd_twd_rate || 32.5);
const holdingsTwd = computed(() => (portfolioStore.summary?.market_value_twd || 0) + (portfolioStore.summary?.market_value_usd || 0) * fx.value);
const weight = (pos) => {
  const twd = pos.currency === 'USD' ? pos.market_value * fx.value : pos.market_value;
  return holdingsTwd.value ? twd / holdingsTwd.value * 100 : 0;
};
// TW first, then US (as on the Watchlist); largest holding first within each group.
const positionGroups = computed(() => [['TW', 'TWD'], ['US', 'USD']]
  .map(([market, currency]) => {
    const positions = portfolioStore.positions.filter(p => p.currency === currency)
      .sort((a, b) => b.market_value - a.market_value);
    const value = positions.reduce((sum, p) => sum + p.market_value, 0);
    const twd = currency === 'USD' ? value * fx.value : value;
    return { market, currency, positions, value, weight: holdingsTwd.value ? twd / holdingsTwd.value * 100 : 0 };
  })
  .filter(g => g.positions.length));
const fmtMoney = (v, cur) => v.toLocaleString(undefined, { maximumFractionDigits: cur === 'USD' ? 2 : 0, minimumFractionDigits: cur === 'USD' ? 2 : 0 });
const signed = (v, cur) => (v > 0 ? '+' : '') + fmtMoney(v, cur);
const isSyncing = ref(false);

const syncTrades = async () => {
  if (isSyncing.value) return;
  isSyncing.value = true;
  try {
    const res = await portfolioStore.syncTrades();
    alert(res.message);
  } catch (e) {
    alert("Sync failed: " + apiError(e));
  } finally {
    isSyncing.value = false;
  }
};



const showWatchlistModal = ref(false);
const newSymbol = ref({ symbol: '' });

const submitWatchlist = async () => {
  if (!newSymbol.value.symbol) return alert("請輸入股票代號");
  try {
    await marketStore.addToWatchlist(newSymbol.value.symbol.trim().toUpperCase());
    showWatchlistModal.value = false;
    newSymbol.value.symbol = '';
  } catch (e) {
    alert("新增失敗: " + apiError(e));
  }
};

const deleteWatchlist = async (symbol) => {
  if (confirm(`確定要從自選股刪除 ${symbol} 嗎？`)) {
    await marketStore.removeFromWatchlist(symbol);
  }
};

// datetime-local wants local wall-clock time; toISOString() would give UTC (8 hours behind in Taipei).
const localNow = () => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};
const blankTrade = () => ({ symbol: '', action: 'BUY', shares: 1000, price: 0, fee: 0, tax: 0, timestamp: localNow() });

const showAddModal = ref(false);
const newTrade = ref(blankTrade());
const openAddModal = () => { newTrade.value = blankTrade(); showAddModal.value = true; };

const submitTrade = async () => {
  if (!newTrade.value.symbol || newTrade.value.shares <= 0 || newTrade.value.price <= 0) {
    return alert("請填寫完整的交易資訊");
  }
  try {
    await portfolioStore.addTrade({ ...newTrade.value, symbol: newTrade.value.symbol.trim().toUpperCase() });
    showAddModal.value = false;
  } catch (e) {
    alert("新增失敗: " + apiError(e));
  }
};

const deleteTrade = async (id) => {
  if (!confirm("確定要刪除這筆交易紀錄嗎？")) return;
  try {
    await portfolioStore.deleteTrade(id);
  } catch (e) {
    alert("刪除失敗: " + apiError(e));
  }
};
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
        <div>
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
                 <div class="font-mono text-sm text-white">{{ item.last?.toFixed(2) ?? '--' }}</div>
                 <div class="text-[10px] font-mono" :class="item.chg_pct?.startsWith('+') ? 'text-text-green' : 'text-text-red'">{{ item.chg_pct }}</div>
              </div>
              <button @click.stop="deleteWatchlist(item.symbol)" class="text-gray-600 hover:text-red-400 transition-colors cursor-pointer" title="Remove">
                <Trash2 :size="12" />
              </button>
            </div>
          </div>
        </div>

        <div v-if="marketStore.watchlistUS.length" class="text-[9px] text-gray-600 font-bold px-4 py-1.5 bg-black/10 uppercase tracking-widest mt-4">US Market</div>
        <div>
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
                 <div class="font-mono text-sm text-white">{{ item.last?.toFixed(2) ?? '--' }}</div>
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
      <div class="px-4 py-2.5 border-b border-border-line bg-black/20 font-mono text-[10px] space-y-1">
        <div class="flex justify-between">
          <span class="text-gray-500 uppercase tracking-wider">Holdings Value</span>
          <span class="text-white font-bold text-xs">NT${{ fmtMoney(holdingsTwd, 'TWD') }}</span>
        </div>
        <div class="flex justify-between text-gray-500">
          <span>USD/TWD</span>
          <span :class="portfolioStore.summary?.usd_twd_live ? '' : 'text-yellow-500'"
                :title="portfolioStore.summary?.usd_twd_live ? '即時匯率（yfinance TWD=X）' : '抓不到即時匯率，使用設定值'">
            {{ fx.toFixed(3) }}{{ portfolioStore.summary?.usd_twd_live ? '' : '（設定值）' }}
          </span>
        </div>
      </div>
      <div class="flex justify-between px-4 py-2 text-[10px] text-gray-500 border-b border-border-line items-center bg-[#0d1117]">
        <span>SYMBOL / QTY</span>
        <span title="市值與占總持股比例（美股以 USD/TWD 換算成台幣再算比例）">VALUE / WEIGHT</span>
      </div>
      <div class="flex-1 overflow-y-auto custom-scrollbar pb-10">
        <template v-for="(group, gi) in positionGroups" :key="group.market">
          <div class="flex justify-between text-[9px] text-gray-600 font-bold px-4 py-1.5 bg-black/10 uppercase tracking-widest font-mono"
               :class="gi > 0 ? 'mt-4' : ''">
            <span>{{ group.market }} Market</span>
            <span class="normal-case tracking-normal">
              {{ group.currency === 'USD' ? 'US$' : 'NT$' }}{{ fmtMoney(group.value, group.currency) }} · {{ group.weight.toFixed(1) }}%
            </span>
          </div>
          <div v-for="pos in group.positions" :key="pos.symbol"
               class="flex justify-between items-center px-4 py-3 border-b border-white/5 hover:bg-gray-800/50 cursor-pointer"
               :class="marketStore.currentSymbol === pos.symbol ? 'bg-blue-900/20 border-l-2 border-blue-500' : 'border-l-2 border-transparent'"
               @click="marketStore.setCurrentSymbol(pos.symbol)">
            <div>
              <div class="font-bold text-white text-sm">{{ pos.symbol }}</div>
              <div class="text-[10px] text-blue-400 font-mono" title="股數 @ 平均成本（移動平均）">{{ pos.shares.toLocaleString() }} @ {{ pos.avg_cost.toFixed(2) }}</div>
              <div class="text-[10px] font-mono" :class="pos.break_even <= pos.avg_cost ? 'text-text-green/80' : 'text-text-red/80'"
                   title="損益兩平價：(買入總額 − 賣出總額) ÷ 剩餘股數。已實現的獲利會壓低它，虧損會拉高它；全部以這個價格賣出時，這檔的歷史總損益為 0">
                兩平 {{ pos.break_even.toFixed(2) }}
              </div>
            </div>
            <div class="text-right">
              <div class="text-sm font-mono font-bold text-white" :title="`市值 = ${pos.shares.toLocaleString()} × ${pos.last_price}`">
                {{ fmtMoney(pos.market_value, pos.currency) }}<span v-if="pos.price_estimated" class="text-yellow-500" title="沒有報價，以成本估算">?</span>
              </div>
              <div class="text-[10px] font-mono text-gray-500">{{ weight(pos).toFixed(1) }}%</div>
              <div class="text-[10px] font-mono" :class="pos.unrealized >= 0 ? 'text-text-green' : 'text-text-red'">
                {{ signed(pos.unrealized, pos.currency) }} ({{ pos.unrealized_pct >= 0 ? '+' : '' }}{{ pos.unrealized_pct.toFixed(2) }}%)
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- Trades -->
    <div v-if="activeTab === 'trades'" class="flex-1 flex flex-col min-h-0">
      <div class="flex justify-between px-4 py-2 text-[10px] text-gray-500 border-b border-border-line items-center bg-[#0d1117]">
        <span>ACTION / SYM</span>
        <div class="flex items-center gap-2">
          <RefreshCw :size="12" class="text-blue-400 cursor-pointer" :class="isSyncing ? 'animate-spin' : ''" @click="syncTrades" />
          <Plus @click="openAddModal" :size="12" class="text-gray-500 hover:text-white cursor-pointer" />
        </div>
      </div>
      <div class="flex-1 overflow-y-auto custom-scrollbar pb-10">
        <div v-for="trade in portfolioStore.trades" :key="trade.uid" 
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
            <button @click.stop="deleteTrade(trade.uid)" class="text-gray-600 hover:text-red-400 transition-colors cursor-pointer" title="Delete Trade">
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
          
          <div class="text-[10px] text-gray-500">市場由代號判斷：數字代號為台股，其餘為美股。</div>
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
            <input v-model="newTrade.symbol" type="text" class="bg-black border border-gray-700 rounded px-2 py-1.5 outline-none focus:border-blue-500 uppercase" placeholder="e.g. 2330 or AAPL">
          </div>
          
          <div class="flex gap-2">
            <div class="flex flex-col gap-1 flex-1">
              <label>買/賣 (Action)</label>
              <select v-model="newTrade.action" class="bg-black border border-gray-700 rounded px-2 py-1.5 outline-none focus:border-blue-500">
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
              </select>
            </div>
            <div class="flex flex-col gap-1 flex-1 justify-end text-[10px] text-gray-500 pb-1.5">
              幣別依代號：台股 TWD／美股 USD
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

          <div class="flex gap-2">
            <div class="flex flex-col gap-1 flex-1">
              <label>手續費 (Fee)</label>
              <input v-model.number="newTrade.fee" type="number" step="1" min="0" class="bg-black border border-gray-700 rounded px-2 py-1.5 outline-none focus:border-blue-500">
            </div>
            <div class="flex flex-col gap-1 flex-1">
              <label>交易稅 (Tax)</label>
              <input v-model.number="newTrade.tax" type="number" step="1" min="0" class="bg-black border border-gray-700 rounded px-2 py-1.5 outline-none focus:border-blue-500">
            </div>
          </div>

          <div class="flex flex-col gap-1">
            <label>時間 (Time，交易所當地時間)</label>
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
