<script setup>
import { onMounted, ref, computed } from 'vue';
import axios from 'axios';

const trips = ref([]);
const totals = ref({});
const windowDays = ref(60);
const isLoading = ref(false);

const fetchData = async () => {
  isLoading.value = true;
  try {
    const res = await axios.get('/api/round-trips');
    trips.value = res.data.trips || [];
    totals.value = res.data.totals || {};
    windowDays.value = res.data.window || windowDays.value;
  } catch (e) {
    console.error('Failed to fetch round trips:', e);
  } finally {
    isLoading.value = false;
  }
};

const money = (v, cur) => (v === null || v === undefined ? '—'
  : (v > 0 ? '+' : '') + v.toLocaleString(undefined, { maximumFractionDigits: cur === 'USD' ? 2 : 0, minimumFractionDigits: cur === 'USD' ? 2 : 0 }));
const tone = (v) => (v === null || v === undefined ? 'text-gray-500' : v >= 0 ? 'text-text-green' : 'text-text-red');
const statusLabel = { closed: '已完成', open: '進行中', reduction: '減碼' };
const statusTone = { closed: 'text-gray-300', open: 'text-blue-400', reduction: 'text-gray-500' };
const currencies = computed(() => Object.entries(totals.value));

onMounted(fetchData);
defineExpose({ refresh: fetchData });
</script>

<template>
  <div class="space-y-4">
    <div class="text-[11px] text-gray-500 leading-relaxed bg-[#161b22] border border-border-line rounded-lg px-4 py-3">
      一輪從<b class="text-gray-300">賣出</b>開始，之後的賣出都算同一輪，直到<b class="text-gray-300">買回同樣股數</b>為止（多買的部分算新買入）。
      賣出後 {{ windowDays }} 個交易日內沒買回，算<b class="text-gray-300">減碼</b>，不算來回交易。
      「比持有」= 賣出所得 − 買回成本 − 手續費與交易稅；沒填手續費的台股交易以 0.1425% 與證交稅估算。進行中的一輪以最新收盤價估算。
    </div>

    <div class="grid grid-cols-2 gap-3" v-if="currencies.length">
      <div v-for="[cur, t] in currencies" :key="cur" class="bg-[#161b22] border border-border-line rounded-lg px-4 py-3 font-mono text-xs">
        <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">{{ cur === 'USD' ? '美股' : '台股' }} · 已完成 {{ t.closed }} 輪</div>
        <div class="flex justify-between items-baseline">
          <span class="text-lg font-bold" :class="tone(t.vs_hold)">{{ money(t.vs_hold, cur) }}</span>
          <span class="text-gray-400">勝 {{ t.won }}/{{ t.closed }}</span>
        </div>
        <div class="text-[10px] text-gray-600 mt-1">比一直持有多賺（已扣手續費與稅 {{ money(-t.fees, cur) }}）</div>
      </div>
    </div>

    <div class="bg-[#161b22] rounded-lg border border-border-line overflow-hidden">
      <div class="px-4 py-2.5 border-b border-border-line bg-black/20 flex items-center">
        <span class="text-sm font-bold text-gray-300 uppercase tracking-wider mr-auto">Round Trips</span>
        <span v-if="isLoading" class="text-[10px] text-blue-400 animate-pulse">Loading...</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs whitespace-nowrap">
          <thead>
            <tr class="text-gray-500 border-b border-border-line bg-black/10">
              <th class="px-4 py-2 font-medium">SYMBOL</th>
              <th class="px-2 py-2 font-medium">狀態</th>
              <th class="px-2 py-2 font-medium">期間</th>
              <th class="px-2 py-2 font-medium text-right">賣出股數</th>
              <th class="px-2 py-2 font-medium text-right">賣出均價</th>
              <th class="px-2 py-2 font-medium text-right">買回均價</th>
              <th class="px-2 py-2 font-medium text-right">手續費+稅</th>
              <th class="px-2 py-2 font-medium text-right">比持有</th>
              <th class="px-4 py-2 font-medium text-right">%</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in trips" :key="i" class="border-b border-white/5 hover:bg-gray-800/50" :class="r.status === 'reduction' ? 'opacity-60' : ''">
              <td class="px-4 py-2 font-bold text-blue-400">{{ r.symbol }}</td>
              <td class="px-2 py-2" :class="statusTone[r.status]">{{ statusLabel[r.status] }}</td>
              <td class="px-2 py-2 text-gray-400">{{ r.start }} → {{ r.end || (r.status === 'open' ? '…' : '—') }}</td>
              <td class="px-2 py-2 text-right font-mono text-gray-400">
                {{ r.shares_sold.toLocaleString() }}<span v-if="r.shares_rebought && r.shares_rebought < r.shares_sold" class="text-gray-600"> (買回 {{ r.shares_rebought }})</span>
              </td>
              <td class="px-2 py-2 text-right font-mono">{{ r.avg_sell.toFixed(2) }}</td>
              <td class="px-2 py-2 text-right font-mono">
                {{ r.avg_buy ? r.avg_buy.toFixed(2) : '—' }}<span v-if="r.status === 'open' && r.marked_at" class="text-gray-600" :title="'未買回的股數以 ' + r.marked_at + ' 估算'"> ~{{ r.marked_at.toFixed(2) }}</span>
              </td>
              <td class="px-2 py-2 text-right font-mono text-gray-500">{{ r.fees ? money(-r.fees, r.currency) : '—' }}</td>
              <td class="px-2 py-2 text-right font-mono font-bold" :class="tone(r.vs_hold)">{{ money(r.vs_hold, r.currency) }}</td>
              <td class="px-4 py-2 text-right font-mono" :class="tone(r.vs_hold_pct)">{{ r.vs_hold_pct === null || r.vs_hold_pct === undefined ? '—' : (r.vs_hold_pct > 0 ? '+' : '') + r.vs_hold_pct.toFixed(2) + '%' }}</td>
            </tr>
            <tr v-if="!trips.length && !isLoading"><td colspan="9" class="py-10 text-center text-gray-600 italic">還沒有賣出紀錄</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
