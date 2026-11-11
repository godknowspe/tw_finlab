<script setup>
import { onMounted, onUnmounted, ref, nextTick } from 'vue';
import { createChart } from 'lightweight-charts';
import axios from 'axios';

const form = ref({ symbol: '0050', trigger_pct: 10, add_pct: 10, monthly: 12000, reserve: 2000, years: 10 });
const result = ref(null);
const error = ref('');
const isLoading = ref(false);
const chartEl = ref(null);
let chart = null;
let series = [];
let resizeObserver = null;

const LINES = [
  { key: 'invest_now', label: '每月全部立即投入', color: '#f2c94c' },
  { key: 'dip', label: '下跌加碼', color: '#56ccf2' },
  { key: 'idle_cash', label: '保留現金不動', color: '#6b7280' },
];

const run = async () => {
  isLoading.value = true;
  error.value = '';
  try {
    const { symbol, ...params } = form.value;
    if (!params.add_pct) params.add_pct = 0;
    const res = await axios.get(`/api/dip-backtest/${encodeURIComponent(symbol.trim().toUpperCase())}`, { params });
    result.value = res.data;
    await nextTick();
    draw();
  } catch (e) {
    error.value = e.response?.data?.detail || e.message;
    result.value = null;
  } finally {
    isLoading.value = false;
  }
};

const draw = () => {
  if (!chartEl.value || !result.value) return;
  if (!chart) {
    chart = createChart(chartEl.value, {
      width: chartEl.value.clientWidth, height: chartEl.value.clientHeight,
      layout: { background: { type: 'solid', color: '#0d1117' }, textColor: '#c9d1d9', fontSize: 11 },
      grid: { vertLines: { color: '#21262d' }, horzLines: { color: '#21262d' } },
      rightPriceScale: { borderColor: '#30363d', scaleMargins: { top: 0.1, bottom: 0 } }, timeScale: { borderColor: '#30363d' },
    });
    resizeObserver = new ResizeObserver(([e]) => chart && chart.resize(e.contentRect.width, e.contentRect.height));
    resizeObserver.observe(chartEl.value);
  }
  series.forEach(s => chart.removeSeries(s));
  series = LINES.map(l => {
    const s = chart.addLineSeries({ color: l.color, lineWidth: l.key === 'dip' ? 2 : 1, title: l.label, priceLineVisible: false,
                                    priceFormat: { type: 'price', precision: 0, minMove: 1 },
                                    autoscaleInfoProvider: (base) => { const r = base(); if (r) r.priceRange.minValue = 0; return r; } });
    s.setData(result.value.strategies[l.key].curve);
    return s;
  });
  const adds = result.value.strategies.dip.adds;
  series[1].setMarkers(adds.map(a => ({ time: a.date, position: 'belowBar', color: '#56ccf2', shape: 'arrowUp', text: '' })));
  chart.timeScale().fitContent();
};

const money = (v) => v.toLocaleString(undefined, { maximumFractionDigits: 0 });
const pct = (v) => (v > 0 ? '+' : '') + v.toFixed(2) + '%';

onMounted(run);
onUnmounted(() => { resizeObserver?.disconnect(); chart?.remove(); chart = null; });
</script>

<template>
  <div class="space-y-4">
    <div class="text-[11px] text-gray-500 leading-relaxed bg-[#161b22] border border-border-line rounded-lg px-4 py-3">
      用含息調整後的歷史價格回測。三種做法每月投入的錢完全相同，只差在<b class="text-gray-300">什麼時候投入</b>：
      「立即投入」每月全部買進；「下跌加碼」每月先買（投入 − 保留），保留的部分存成現金，價格從最近高點（或上次加碼價）
      再跌一個門檻就加碼；「保留現金不動」保留的錢一直不用。
      <b class="text-gray-300">過去的最佳參數不代表未來</b>：把資料切成前後兩段，最佳參數就會不同。
    </div>

    <div class="bg-[#161b22] border border-border-line rounded-lg px-4 py-3 flex flex-wrap items-end gap-3 text-xs">
      <label class="flex flex-col gap-1"><span class="text-[10px] text-gray-500">代號</span>
        <input v-model="form.symbol" class="w-20 bg-black border border-gray-700 rounded px-2 py-1 uppercase"></label>
      <label class="flex flex-col gap-1"><span class="text-[10px] text-gray-500">每跌 (%)</span>
        <input v-model.number="form.trigger_pct" type="number" step="0.5" min="0.5" class="w-20 bg-black border border-gray-700 rounded px-2 py-1"></label>
      <label class="flex flex-col gap-1"><span class="text-[10px] text-gray-500">加碼持股市值的 (%)，0 = 全部保留款</span>
        <input v-model.number="form.add_pct" type="number" step="1" min="0" class="w-24 bg-black border border-gray-700 rounded px-2 py-1"></label>
      <label class="flex flex-col gap-1"><span class="text-[10px] text-gray-500">每月投入</span>
        <input v-model.number="form.monthly" type="number" step="1000" min="1" class="w-24 bg-black border border-gray-700 rounded px-2 py-1"></label>
      <label class="flex flex-col gap-1"><span class="text-[10px] text-gray-500">其中保留做加碼</span>
        <input v-model.number="form.reserve" type="number" step="500" min="0" class="w-24 bg-black border border-gray-700 rounded px-2 py-1"></label>
      <label class="flex flex-col gap-1"><span class="text-[10px] text-gray-500">年數</span>
        <input v-model.number="form.years" type="number" min="1" max="30" class="w-16 bg-black border border-gray-700 rounded px-2 py-1"></label>
      <button @click="run" :disabled="isLoading" class="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white font-bold px-4 py-1.5 rounded">
        {{ isLoading ? '計算中…' : '回測' }}
      </button>
      <span v-if="error" class="text-red-400">{{ error }}</span>
    </div>

    <template v-if="result">
      <div class="grid grid-cols-3 gap-3 font-mono text-xs">
        <div v-for="l in LINES" :key="l.key" class="bg-[#161b22] border border-border-line rounded-lg px-4 py-3">
          <div class="text-[10px] mb-1" :style="{ color: l.color }">{{ l.label }}</div>
          <div class="text-lg font-bold text-white">{{ money(result.strategies[l.key].final) }}</div>
          <div class="text-[10px] text-gray-500">
            投入 {{ money(result.strategies[l.key].deposited) }}
            <template v-if="l.key === 'dip'"> · 加碼 {{ result.strategies.dip.adds.length }} 次 · 剩現金 {{ money(result.strategies.dip.cash_left) }}</template>
            <template v-if="l.key === 'idle_cash'"> · 現金 {{ money(result.strategies.idle_cash.cash_left) }}</template>
          </div>
        </div>
      </div>
      <div class="bg-[#161b22] border border-border-line rounded-lg px-4 py-3 text-xs flex flex-wrap gap-x-6 gap-y-1 font-mono">
        <span class="text-gray-500">{{ result.start }} → {{ result.end }}</span>
        <span class="text-gray-500">年化 {{ pct(result.cagr_pct) }} · 最大回撤 {{ result.max_drawdown_pct.toFixed(1) }}%</span>
        <span>下跌加碼 vs 立即投入：<b :class="result.dip_vs_invest_now_pct >= 0 ? 'text-text-green' : 'text-text-red'">{{ pct(result.dip_vs_invest_now_pct) }}</b></span>
        <span>vs 保留現金：<b :class="result.dip_vs_idle_cash_pct >= 0 ? 'text-text-green' : 'text-text-red'">{{ pct(result.dip_vs_idle_cash_pct) }}</b></span>
      </div>
      <div ref="chartEl" class="h-80 bg-[#161b22] border border-border-line rounded-lg overflow-hidden"></div>
    </template>
  </div>
</template>
