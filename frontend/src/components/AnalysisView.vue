<script setup>
import { onMounted, ref, computed } from 'vue';
import axios from 'axios';

const analysisData = ref([]);
const isLoading = ref(false);

const sortKeyOpen = ref('');
const sortOrderOpen = ref(1);

const sortKeyClosed = ref('');
const sortOrderClosed = ref(1);

const sortByOpen = (key) => {
  if (sortKeyOpen.value === key) {
    sortOrderOpen.value *= -1;
  } else {
    sortKeyOpen.value = key;
    sortOrderOpen.value = 1;
  }
};

const sortByClosed = (key) => {
  if (sortKeyClosed.value === key) {
    sortOrderClosed.value *= -1;
  } else {
    sortKeyClosed.value = key;
    sortOrderClosed.value = 1;
  }
};

const openPositions = computed(() => {
  let data = analysisData.value.filter(d => d.status === 'OPEN');
  if (sortKeyOpen.value) {
    data.sort((a, b) => {
      let valA = a[sortKeyOpen.value];
      let valB = b[sortKeyOpen.value];
      if (sortKeyOpen.value === 'days') {
        valA = getDaysHeld(a.buy_date);
        valB = getDaysHeld(b.buy_date);
      }
      if (typeof valA === 'string') return valA.localeCompare(valB) * sortOrderOpen.value;
      return (valA > valB ? 1 : -1) * sortOrderOpen.value;
    });
  }
  return data;
});

const closedTrades = computed(() => {
  let data = analysisData.value.filter(d => d.status === 'CLOSED');
  if (sortKeyClosed.value) {
    data.sort((a, b) => {
      let valA = a[sortKeyClosed.value];
      let valB = b[sortKeyClosed.value];
      if (sortKeyClosed.value === 'days') {
        valA = getDaysHeld(a.buy_date, a.sell_date);
        valB = getDaysHeld(b.buy_date, b.sell_date);
      }
      if (typeof valA === 'string') return valA.localeCompare(valB) * sortOrderClosed.value;
      return (valA > valB ? 1 : -1) * sortOrderClosed.value;
    });
  }
  return data;
});


const fetchData = async () => {
  isLoading.value = true;
  try {
    const res = await axios.get('/api/analysis');
    analysisData.value = res.data || [];
  } catch (e) {
    console.error('Failed to fetch analysis data:', e);
  } finally {
    isLoading.value = false;
  }
};

const getDaysHeld = (buyDate, sellDate = null) => {

  const start = new Date(buyDate);
  const end = sellDate ? new Date(sellDate) : new Date();
  return Math.floor((end - start) / (1000 * 60 * 60 * 24));
};

onMounted(() => {
  fetchData();
});

defineExpose({ refresh: fetchData });
</script>

<template>
  <div class="flex-1 w-full overflow-y-auto p-4 space-y-6 custom-scrollbar bg-[#0d1117]">
    <!-- Header -->
    <div class="flex items-center justify-between mb-2">
      <h2 class="text-lg font-bold text-white flex items-center gap-2">
        📊 Performance Analysis
        <span v-if="isLoading" class="text-[10px] text-blue-400 animate-pulse font-normal">Loading data...</span>
      </h2>
      <button @click="fetchData" class="text-[10px] bg-gray-800 hover:bg-gray-700 text-gray-400 px-3 py-1 rounded border border-gray-700 uppercase">Refresh</button>
    </div>

    <!-- Open Positions -->
    <div class="bg-[#161b22] rounded-lg border border-border-line overflow-hidden shadow-lg">
      <div class="px-4 py-3 border-b border-border-line bg-black/20 flex justify-between items-center">
        <h3 class="text-sm font-bold text-gray-300 uppercase tracking-wider">Unrealized Position Analysis</h3>
        <span class="text-[10px] bg-blue-900/30 text-blue-400 px-2 py-0.5 rounded border border-blue-500/30">{{ openPositions.length }} Active</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead>
            <tr class="text-gray-500 border-b border-border-line bg-black/10 select-none">
              <th class="px-4 py-2 font-medium text-center cursor-pointer hover:text-white" @click="sortByOpen('symbol')">SYMBOL <span v-if="sortKeyOpen==='symbol'">{{sortOrderOpen===1?'↑':'↓'}}</span></th>
              <th class="px-2 py-2 font-medium text-left cursor-pointer hover:text-white" @click="sortByOpen('buy_date')">BUY DATE <span v-if="sortKeyOpen==='buy_date'">{{sortOrderOpen===1?'↑':'↓'}}</span></th>
              <th class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortByOpen('days')">DAYS <span v-if="sortKeyOpen==='days'">{{sortOrderOpen===1?'↑':'↓'}}</span></th>
              <th class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortByOpen('shares')">QTY <span v-if="sortKeyOpen==='shares'">{{sortOrderOpen===1?'↑':'↓'}}</span></th>
              <th class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortByOpen('buy_price')">ENTRY <span v-if="sortKeyOpen==='buy_price'">{{sortOrderOpen===1?'↑':'↓'}}</span></th>
              <th class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortByOpen('sell_price')">LAST <span v-if="sortKeyOpen==='sell_price'">{{sortOrderOpen===1?'↑':'↓'}}</span></th>
              <th class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortByOpen('mae_pct')">MAE(%) <span v-if="sortKeyOpen==='mae_pct'">{{sortOrderOpen===1?'↑':'↓'}}</span></th>
              <th class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortByOpen('mfe_pct')">MFE(%) <span v-if="sortKeyOpen==='mfe_pct'">{{sortOrderOpen===1?'↑':'↓'}}</span></th>
              <th class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortByOpen('efficiency_pct')">EFF% <span v-if="sortKeyOpen==='efficiency_pct'">{{sortOrderOpen===1?'↑':'↓'}}</span></th>
              <th class="px-4 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortByOpen('realized')">U-PNL <span v-if="sortKeyOpen==='realized'">{{sortOrderOpen===1?'↑':'↓'}}</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in openPositions" :key="'open_'+idx" class="border-b border-white/5 hover:bg-gray-800/50 transition-colors">
              <td class="px-4 py-3 font-bold text-blue-400 text-center">{{ row.symbol }}</td>
              <td class="px-2 py-3 text-gray-400">{{ row.buy_date }}</td>
              <td class="px-2 py-3 text-right text-gray-400">{{ getDaysHeld(row.buy_date) }}d</td>
              <td class="px-2 py-3 text-right font-mono text-gray-400">{{ row.shares.toLocaleString() }}</td>
              <td class="px-2 py-3 text-right font-mono">{{ row.buy_price.toFixed(2) }}</td>
              <td class="px-2 py-3 text-right font-mono text-white">{{ row.sell_price.toFixed(2) }}</td>
              <td class="px-2 py-3 text-right font-mono" :class="row.mae_pct < -5 ? 'text-red-400 font-bold' : 'text-gray-500'">{{ row.mae_pct.toFixed(2) }}%</td>
              <td class="px-2 py-3 text-right font-mono text-green-500">{{ row.mfe_pct.toFixed(2) }}%</td>
              <td class="px-2 py-3 text-right font-mono text-yellow-400">{{ row.efficiency_pct.toFixed(2) }}%</td>
              <td class="px-4 py-3 text-right font-mono font-bold" :class="row.realized >= 0 ? 'text-text-green' : 'text-text-red'">
                {{ row.realized >= 0 ? '+' : '' }}{{ row.realized.toLocaleString() }}
              </td>
            </tr>
            <tr v-if="openPositions.length === 0">
              <td colspan="10" class="py-12 text-center text-gray-600 italic text-sm">No open positions to analyze</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Closed Trades -->
    <div class="bg-[#161b22] rounded-lg border border-border-line overflow-hidden shadow-lg">
      <div class="px-4 py-3 border-b border-border-line bg-black/20 flex justify-between items-center">
        <h3 class="text-sm font-bold text-gray-400 uppercase tracking-wider">Historical Trade Analysis</h3>
        <span class="text-[10px] bg-gray-800 text-gray-500 px-2 py-0.5 rounded border border-gray-700">{{ closedTrades.length }} Closed</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead>
            <tr class="text-gray-500 border-b border-border-line bg-black/10 select-none">
              <th class="px-4 py-2 font-medium text-center cursor-pointer hover:text-white" @click="sortByClosed('symbol')">SYMBOL <span v-if="sortKeyClosed==='symbol'">{{sortOrderClosed===1?'↑':'↓'}}</span></th>
              <th class="px-2 py-2 font-medium text-left cursor-pointer hover:text-white" @click="sortByClosed('buy_date')">BUY DATE <span v-if="sortKeyClosed==='buy_date'">{{sortOrderClosed===1?'↑':'↓'}}</span></th>
              <th class="px-2 py-2 font-medium text-left cursor-pointer hover:text-white" @click="sortByClosed('sell_date')">SELL DATE <span v-if="sortKeyClosed==='sell_date'">{{sortOrderClosed===1?'↑':'↓'}}</span></th>
              <th class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortByClosed('days')">DAYS <span v-if="sortKeyClosed==='days'">{{sortOrderClosed===1?'↑':'↓'}}</span></th>
              <th class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortByClosed('buy_price')">ENTRY <span v-if="sortKeyClosed==='buy_price'">{{sortOrderClosed===1?'↑':'↓'}}</span></th>
              <th class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortByClosed('sell_price')">EXIT <span v-if="sortKeyClosed==='sell_price'">{{sortOrderClosed===1?'↑':'↓'}}</span></th>
              <th class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortByClosed('mae_pct')">MAE% <span v-if="sortKeyClosed==='mae_pct'">{{sortOrderClosed===1?'↑':'↓'}}</span></th>
              <th class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortByClosed('mfe_pct')">MFE% <span v-if="sortKeyClosed==='mfe_pct'">{{sortOrderClosed===1?'↑':'↓'}}</span></th>
              <th class="px-2 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortByClosed('efficiency_pct')">EFF% <span v-if="sortKeyClosed==='efficiency_pct'">{{sortOrderClosed===1?'↑':'↓'}}</span></th>
              <th class="px-4 py-2 font-medium text-right cursor-pointer hover:text-white" @click="sortByClosed('realized')">R-PNL <span v-if="sortKeyClosed==='realized'">{{sortOrderClosed===1?'↑':'↓'}}</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in closedTrades" :key="'close_'+idx" class="border-b border-white/5 hover:bg-gray-800/50 transition-colors opacity-80 text-center">
              <td class="px-4 py-3 font-bold text-gray-300">{{ row.symbol }}</td>
              <td class="px-2 py-3 text-gray-500 text-left">{{ row.buy_date }}</td>
              <td class="px-2 py-3 text-gray-500 text-left">{{ row.sell_date }}</td>
              <td class="px-2 py-3 text-right text-gray-500">{{ getDaysHeld(row.buy_date, row.sell_date) }}d</td>
              <td class="px-2 py-3 text-right font-mono text-gray-500">{{ row.buy_price.toFixed(2) }}</td>
              <td class="px-2 py-3 text-right font-mono text-gray-300">{{ row.sell_price.toFixed(2) }}</td>
              <td class="px-2 py-3 text-right font-mono text-gray-600">{{ row.mae_pct.toFixed(2) }}%</td>
              <td class="px-2 py-3 text-right font-mono text-gray-600">{{ row.mfe_pct.toFixed(2) }}%</td>
              <td class="px-2 py-3 text-right font-mono text-gray-600">{{ row.efficiency_pct.toFixed(2) }}%</td>
              <td class="px-4 py-3 text-right font-mono font-bold" :class="row.realized >= 0 ? 'text-text-green/70' : 'text-text-red/70'">
                {{ row.realized >= 0 ? '+' : '' }}{{ row.realized.toLocaleString() }}
              </td>
            </tr>
            <tr v-if="closedTrades.length === 0">
              <td colspan="10" class="py-12 text-center text-gray-600 italic text-sm">No historical trades found</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
