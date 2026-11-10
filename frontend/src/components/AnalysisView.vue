<script setup>
import { onMounted, ref, computed } from 'vue';
import axios from 'axios';

const buys = ref([]);
const horizons = ref([5, 20, 60]);
const windowDays = ref(20);
const isLoading = ref(false);
const statusFilter = ref('ALL');
const symbolFilter = ref('');
const sortKey = ref('buy_date');
const sortOrder = ref(-1);

const sortBy = (key) => {
  if (sortKey.value === key) sortOrder.value *= -1;
  else { sortKey.value = key; sortOrder.value = -1; }
};
const arrow = (key) => (sortKey.value === key ? (sortOrder.value === 1 ? '↑' : '↓') : '');

const rows = computed(() => {
  let data = buys.value.filter(r =>
    (statusFilter.value === 'ALL' || r.status === statusFilter.value) &&
    (!symbolFilter.value || r.symbol === symbolFilter.value));
  const k = sortKey.value;
  // Missing values (window not elapsed yet) always sort last.
  return [...data].sort((a, b) => {
    const va = a[k], vb = b[k];
    if (va === null || va === undefined) return 1;
    if (vb === null || vb === undefined) return -1;
    if (typeof va === 'string') return va.localeCompare(vb) * sortOrder.value;
    return (va > vb ? 1 : va < vb ? -1 : 0) * sortOrder.value;
  });
});

const symbols = computed(() => [...new Set(buys.value.map(r => r.symbol))].sort());

// Per-symbol totals: the realized + unrealized of its buys equals the Positions page.
const summary = computed(() => symbols.value.map(sym => {
  const rs = buys.value.filter(r => r.symbol === sym);
  const cost = rs.reduce((s, r) => s + r.shares * r.buy_price, 0);
  const total = rs.reduce((s, r) => s + r.total_pnl, 0);
  const scored = rs.filter(r => r.ret_20d !== null);
  return {
    symbol: sym,
    currency: rs[0].currency,
    buys: rs.length,
    winners: rs.filter(r => r.total_pnl > 0).length,
    realized: rs.reduce((s, r) => s + r.realized, 0),
    unrealized: rs.reduce((s, r) => s + r.unrealized, 0),
    total,
    return_pct: cost ? total / cost * 100 : 0,
    avg_ret_20d: scored.length ? scored.reduce((s, r) => s + r.ret_20d, 0) / scored.length : null,
  };
}));

const fetchData = async () => {
  isLoading.value = true;
  try {
    const res = await axios.get('/api/analysis');
    buys.value = res.data.buys || [];
    horizons.value = res.data.horizons || horizons.value;
    windowDays.value = res.data.window || windowDays.value;
  } catch (e) {
    console.error('Failed to fetch analysis data:', e);
  } finally {
    isLoading.value = false;
  }
};

const pct = (v) => (v === null || v === undefined ? '—' : (v > 0 ? '+' : '') + v.toFixed(2) + '%');
const money = (v, cur) => {
  const digits = cur === 'USD' ? 2 : 0;
  return (v > 0 ? '+' : '') + v.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
};
const tone = (v) => (v === null || v === undefined ? 'text-gray-600' : v >= 0 ? 'text-text-green' : 'text-text-red');
const qty = (v) => (Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 1 }));

onMounted(fetchData);
defineExpose({ refresh: fetchData });
</script>

<template>
  <div class="flex-1 w-full overflow-y-auto p-4 space-y-5 custom-scrollbar bg-[#0d1117]">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-bold text-white flex items-center gap-2">
        📊 Performance Analysis
        <span v-if="isLoading" class="text-[10px] text-blue-400 animate-pulse font-normal">Loading data...</span>
      </h2>
      <button @click="fetchData" class="text-[10px] bg-gray-800 hover:bg-gray-700 text-gray-400 px-3 py-1 rounded border border-gray-700 uppercase">Refresh</button>
    </div>

    <div class="text-[11px] text-gray-500 leading-relaxed bg-[#161b22] border border-border-line rounded-lg px-4 py-3">
      每一筆<b class="text-gray-300">買入</b>分開評價。
      <b class="text-gray-300">時機</b>：買進後第 {{ horizons.join(' / ') }} 個交易日的報酬，以及前 {{ windowDays }} 日內的最大回撤（MAE）與最大漲幅（MFE），不受之後加碼或賣出影響。
      <b class="text-gray-300">結果</b>：每次賣出依當時各筆買入的剩餘股數按比例分攤（與持倉頁的平均成本相同），
      所以同一檔所有買入的損益加總等於持倉頁的已實現＋未實現。剩餘股數因此可能出現小數。
    </div>

    <!-- Per-symbol summary -->
    <div class="bg-[#161b22] rounded-lg border border-border-line overflow-hidden">
      <table class="w-full text-left text-xs">
        <thead>
          <tr class="text-gray-500 border-b border-border-line bg-black/10">
            <th class="px-4 py-2 font-medium">SYMBOL</th>
            <th class="px-2 py-2 font-medium text-right">BUYS</th>
            <th class="px-2 py-2 font-medium text-right">WIN</th>
            <th class="px-2 py-2 font-medium text-right">AVG {{ windowDays }}D</th>
            <th class="px-2 py-2 font-medium text-right">REALIZED</th>
            <th class="px-2 py-2 font-medium text-right">UNREALIZED</th>
            <th class="px-2 py-2 font-medium text-right">TOTAL</th>
            <th class="px-4 py-2 font-medium text-right">RETURN</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in summary" :key="s.symbol" @click="symbolFilter = symbolFilter === s.symbol ? '' : s.symbol"
              class="border-b border-white/5 hover:bg-gray-800/50 cursor-pointer" :class="symbolFilter === s.symbol ? 'bg-blue-900/20' : ''">
            <td class="px-4 py-2 font-bold text-blue-400">{{ s.symbol }}</td>
            <td class="px-2 py-2 text-right text-gray-400">{{ s.buys }}</td>
            <td class="px-2 py-2 text-right text-gray-400">{{ s.winners }}/{{ s.buys }}</td>
            <td class="px-2 py-2 text-right font-mono" :class="tone(s.avg_ret_20d)">{{ pct(s.avg_ret_20d) }}</td>
            <td class="px-2 py-2 text-right font-mono" :class="tone(s.realized)">{{ money(s.realized, s.currency) }}</td>
            <td class="px-2 py-2 text-right font-mono" :class="tone(s.unrealized)">{{ money(s.unrealized, s.currency) }}</td>
            <td class="px-2 py-2 text-right font-mono font-bold" :class="tone(s.total)">{{ money(s.total, s.currency) }}</td>
            <td class="px-4 py-2 text-right font-mono" :class="tone(s.return_pct)">{{ pct(s.return_pct) }}</td>
          </tr>
          <tr v-if="summary.length === 0">
            <td colspan="8" class="py-10 text-center text-gray-600 italic">No buys to analyze</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Per-buy table -->
    <div class="bg-[#161b22] rounded-lg border border-border-line overflow-hidden">
      <div class="px-4 py-2.5 border-b border-border-line bg-black/20 flex items-center gap-3 text-[10px]">
        <span class="text-sm font-bold text-gray-300 uppercase tracking-wider mr-auto">
          Buys <span v-if="symbolFilter" class="text-blue-400 normal-case">· {{ symbolFilter }}</span>
        </span>
        <button v-for="f in ['ALL', 'OPEN', 'CLOSED']" :key="f" @click="statusFilter = f"
                :class="statusFilter === f ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'"
                class="px-2 py-0.5 rounded uppercase">{{ f }}</button>
        <button v-if="symbolFilter" @click="symbolFilter = ''" class="text-gray-500 hover:text-white">clear ✕</button>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs whitespace-nowrap">
          <thead>
            <tr class="text-gray-600 text-[9px] uppercase tracking-wider bg-black/20">
              <th colspan="5"></th>
              <th :colspan="horizons.length + 2" class="px-2 pt-2 text-center border-l border-white/5">Timing</th>
              <th colspan="5" class="px-2 pt-2 text-center border-l border-white/5">Outcome</th>
            </tr>
            <tr class="text-gray-500 border-b border-border-line bg-black/10 select-none">
              <th class="px-4 py-2 font-medium cursor-pointer hover:text-white" @click="sortBy('symbol')">SYMBOL {{ arrow('symbol') }}</th>
              <th class="px-2 py-2 font-medium cursor-pointer hover:text-white" @click="sortBy('buy_date')">BUY DATE {{ arrow('buy_date') }}</th>
              <th class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortBy('shares')">QTY {{ arrow('shares') }}</th>
              <th class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortBy('buy_price')">PRICE {{ arrow('buy_price') }}</th>
              <th class="px-2 py-2 font-medium text-right" title="Position average cost before → after this buy">AVG COST</th>
              <th v-for="n in horizons" :key="n" class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white"
                  :class="n === horizons[0] ? 'border-l border-white/5' : ''" @click="sortBy('ret_' + n + 'd')">{{ n }}D {{ arrow('ret_' + n + 'd') }}</th>
              <th class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortBy('mae_pct')">MAE {{ arrow('mae_pct') }}</th>
              <th class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortBy('mfe_pct')">MFE {{ arrow('mfe_pct') }}</th>
              <th class="px-2 py-2 font-medium text-right border-l border-white/5 cursor-pointer hover:text-white" @click="sortBy('remaining')">LEFT {{ arrow('remaining') }}</th>
              <th class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortBy('realized')">REALIZED {{ arrow('realized') }}</th>
              <th class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortBy('unrealized')">UNREAL. {{ arrow('unrealized') }}</th>
              <th class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortBy('total_pnl')">TOTAL {{ arrow('total_pnl') }}</th>
              <th class="px-4 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortBy('return_pct')">RETURN {{ arrow('return_pct') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in rows" :key="r.uid" class="border-b border-white/5 hover:bg-gray-800/50" :class="r.status === 'CLOSED' ? 'opacity-70' : ''">
              <td class="px-4 py-2 font-bold" :class="r.status === 'OPEN' ? 'text-blue-400' : 'text-gray-400'">{{ r.symbol }}</td>
              <td class="px-2 py-2 text-gray-400">{{ r.buy_date }}</td>
              <td class="px-2 py-2 text-right font-mono text-gray-400">{{ qty(r.shares) }}</td>
              <td class="px-2 py-2 text-right font-mono">{{ r.buy_price.toFixed(2) }}</td>
              <td class="px-2 py-2 text-right font-mono text-[10px]"
                  :class="r.avg_cost_before === null ? 'text-gray-500' : r.avg_cost_after < r.avg_cost_before ? 'text-text-green' : 'text-text-red'">
                <template v-if="r.avg_cost_before !== null">{{ r.avg_cost_before.toFixed(2) }} → </template>{{ r.avg_cost_after.toFixed(2) }}
              </td>
              <td v-for="n in horizons" :key="n" class="px-2 py-2 text-right font-mono" :class="[tone(r['ret_' + n + 'd']), n === horizons[0] ? 'border-l border-white/5' : '']">
                {{ pct(r['ret_' + n + 'd']) }}
              </td>
              <td class="px-2 py-2 text-right font-mono" :class="r.mae_pct !== null && r.mae_pct < -5 ? 'text-red-400' : 'text-gray-500'"
                  :title="r.days_observed < windowDays ? `only ${r.days_observed} of ${windowDays} days so far` : ''">
                {{ pct(r.mae_pct) }}<span v-if="r.mae_pct !== null && r.days_observed < windowDays" class="text-gray-600">*</span>
              </td>
              <td class="px-2 py-2 text-right font-mono text-gray-500">{{ pct(r.mfe_pct) }}</td>
              <td class="px-2 py-2 text-right font-mono text-gray-400 border-l border-white/5">{{ r.remaining ? qty(r.remaining) : '—' }}</td>
              <td class="px-2 py-2 text-right font-mono" :class="tone(r.realized)">{{ r.realized ? money(r.realized, r.currency) : '—' }}</td>
              <td class="px-2 py-2 text-right font-mono" :class="tone(r.unrealized)">
                {{ r.remaining ? money(r.unrealized, r.currency) : '—' }}<span v-if="r.price_estimated" class="text-yellow-500" title="no price yet">?</span>
              </td>
              <td class="px-2 py-2 text-right font-mono font-bold" :class="tone(r.total_pnl)">{{ money(r.total_pnl, r.currency) }}</td>
              <td class="px-4 py-2 text-right font-mono" :class="tone(r.return_pct)">{{ pct(r.return_pct) }}</td>
            </tr>
            <tr v-if="rows.length === 0">
              <td :colspan="horizons.length + 12" class="py-10 text-center text-gray-600 italic">No buys match the filter</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="px-4 py-2 text-[10px] text-gray-600 border-t border-white/5">
        * window not fully elapsed yet. AVG COST: green = this buy lowered the position's average cost.
      </div>
    </div>
  </div>
</template>
