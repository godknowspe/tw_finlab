<script setup>
import { onMounted, ref, watch, onUnmounted, nextTick } from 'vue';
import { createChart, CrosshairMode } from 'lightweight-charts';
import { useMarketStore } from '@/stores/market';
import { usePortfolioStore } from '@/stores/portfolio';
import axios from 'axios';

const props = defineProps({
  mode: { type: String, default: 'symbol' },
  symbol: String
});

const marketStore = useMarketStore();
const portfolioStore = usePortfolioStore();
const chartContainer = ref(null);
const showEqTotal = ref(true);
const showEqTW = ref(true);
const showEqUS = ref(true);

const toggleEquityLine = (type) => {
  if (type === 'Total') {
    showEqTotal.value = !showEqTotal.value;
    if (equityTotalSeries) equityTotalSeries.applyOptions({ visible: showEqTotal.value });
  } else if (type === 'TW') {
    showEqTW.value = !showEqTW.value;
    if (equityTWSeries) equityTWSeries.applyOptions({ visible: showEqTW.value });
  } else if (type === 'US') {
    showEqUS.value = !showEqUS.value;
    if (equityUSSeries) equityUSSeries.applyOptions({ visible: showEqUS.value });
  }
};

const legendPos = ref({ x: 12, y: 12 });
const isLegendExpanded = ref(true);
let isDragging = false;
let dragOffset = { x: 0, y: 0 };

const startDrag = (e) => {
  isDragging = true;
  dragOffset.x = e.clientX - legendPos.value.x;
  dragOffset.y = e.clientY - legendPos.value.y;
  document.addEventListener('mousemove', doDrag);
  document.addEventListener('mouseup', stopDrag);
};

const doDrag = (e) => {
  if (!isDragging) return;
  const newX = Math.max(0, e.clientX - dragOffset.x);
  const newY = Math.max(0, e.clientY - dragOffset.y);
  legendPos.value = { x: newX, y: newY };
};

const stopDrag = () => {
  isDragging = false;
  document.removeEventListener('mousemove', doDrag);
  document.removeEventListener('mouseup', stopDrag);
};

const legendData = ref({
  time: '--', open: '--', high: '--', low: '--', close: '--', v: '--', indicators: {}
});

let chart = null;
let candleSeries = null;
let volumeSeries = null;
let equityTotalSeries = null;
let equityTWSeries = null;
let equityUSSeries = null;
let pnlSeries = null;
let backtestLineSeries = null;
let indicatorSeries = {};                 // overlay lines on the main chart (SMA, Bollinger)
let lastValidData = null;
let fetchGeneration = 0;
let rowsByTime = new Map();               // bar time -> API row, for the legend
let btByTime = new Map();                 // bar time -> backtest equity

// RSI and MACD each live in their own chart under the main one. A chart has a single set of
// price-axis labels spanning its whole height, so a shared chart cannot give each indicator
// a correct axis. The charts share the time axis: scrolling or zooming any of them moves all.
const PANEL_PX = 130;
const PANEL_ORDER = ['RSI', 'MACD'];
const activePanels = ref([]);
const panelEls = {};                      // panel name -> chart container element
const panelCharts = {};                   // panel name -> chart
const axisGap = ref({ main: 0, RSI: 0, MACD: 0 });   // px, equalises the price-axis widths
let resizeObserver = null;
const observed = new Map();               // element -> chart it sizes

// Content box (excluding the padding used for axis alignment), the same size the observer reports.
const contentSize = (el) => {
  const cs = getComputedStyle(el);
  return {
    width: Math.max(1, el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)),
    height: Math.max(1, el.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom)),
  };
};
const chartOptions = (el, extra = {}) => ({
  layout: { background: { type: 'solid', color: '#0d1117' }, textColor: '#c9d1d9', fontSize: 11, fontFamily: 'Inter, system-ui, sans-serif' },
  grid: { vertLines: { color: '#30363d' }, horzLines: { color: '#30363d' } },
  crosshair: { mode: CrosshairMode.Normal, vertLine: { labelBackgroundColor: '#1f6feb' }, horzLine: { labelBackgroundColor: '#1f6feb' } },
  timeScale: { borderColor: '#30363d', timeVisible: true },
  rightPriceScale: { borderColor: '#30363d', autoScale: true },
  handleScroll: true,
  handleScale: true,
  ...contentSize(el),
  ...extra,
});
const observe = (el, c) => {
  observed.set(el, c);
  resizeObserver.observe(el);
};
const allCharts = () => [chart, ...activePanels.value.map(n => panelCharts[n])].filter(Boolean);

// Whitespace for missing values keeps every chart on the same set of time points, so logical
// indices (used to sync the visible range) mean the same bar in each.
const lineData = (data, key) => data.map(d => (d[key] === null || d[key] === undefined ? { time: d.time } : { time: d.time, value: d[key] }));

let syncing = false;
const syncRange = (source) => (range) => {
  if (!range || syncing) return;
  syncing = true;
  try { allCharts().forEach(c => { if (c !== source) c.timeScale().setVisibleLogicalRange(range); }); }
  finally { syncing = false; }
  scheduleAlign();
};

// Price-axis labels of different width would shift the plot areas sideways. Give the charts
// with narrower axes a right margin so every plot area spans the same pixels.
let alignQueued = false;
const scheduleAlign = () => {
  if (alignQueued) return;
  alignQueued = true;
  requestAnimationFrame(() => {
    alignQueued = false;
    if (!chart) return;
    const widths = { main: chart.priceScale('right').width() };
    activePanels.value.forEach(n => { widths[n] = panelCharts[n]?.priceScale('right').width() || 0; });
    const max = Math.max(...Object.values(widths));
    const next = { main: max - widths.main, RSI: 0, MACD: 0 };
    activePanels.value.forEach(n => { next[n] = max - widths[n]; });
    const cur = axisGap.value;
    if (['main', 'RSI', 'MACD'].some(k => Math.abs((cur[k] || 0) - next[k]) >= 1)) axisGap.value = next;
  });
};

const destroyPanels = () => {
  for (const [name, c] of Object.entries(panelCharts)) {
    const el = panelEls[name];
    if (el) { resizeObserver?.unobserve(el); observed.delete(el); }
    c.remove();
    delete panelCharts[name];
  }
  activePanels.value = [];
};

const buildPanels = async (names, data, colors) => {
  activePanels.value = names;
  await nextTick();
  names.forEach((name, i) => {
    const el = panelEls[name];
    if (!el) return;
    const last = i === names.length - 1;
    const c = createChart(el, chartOptions(el, { timeScale: { borderColor: '#30363d', timeVisible: true, visible: last } }));
    panelCharts[name] = c;
    observe(el, c);
    c.subscribeCrosshairMove(onCrosshair);
    c.timeScale().subscribeVisibleLogicalRangeChange(syncRange(c));
    const line = (key, color, width = 1, extra = {}) => {
      const sr = c.addLineSeries({ color, lineWidth: width, priceLineVisible: false, lastValueVisible: false, ...extra });
      sr.setData(lineData(data, key));
      return sr;
    };
    if (name === 'RSI') {
      c.priceScale('right').applyOptions({ scaleMargins: { top: 0.06, bottom: 0.06 } });
      const rsi = line('rsi', colors.RSI, 2, { autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }) });
      [70, 30].forEach(price => rsi.createPriceLine({ price, color: '#6b7280', lineStyle: 2, lineWidth: 1, axisLabelVisible: true, title: '' }));
    } else {
      const macd = line('macd', colors.MACD);
      line('signal', '#FF6D00');
      macd.createPriceLine({ price: 0, color: '#6b7280', lineStyle: 2, lineWidth: 1, axisLabelVisible: false, title: '' });
    }
  });
};

// Bar times from the API: daily+ are 'YYYY-MM-DD'; intraday are exchange wall-clock time sent
// as if UTC. Trade timestamps are exchange wall-clock too, so compare both as UTC.
const barStartMs = (t) => typeof t === 'number' ? t * 1000 : Date.parse(t + 'T00:00:00Z');
const tradeMs = (ts) => Date.parse(ts.length === 16 ? ts + ':00Z' : ts + 'Z');

// The bar containing `ms`: start <= ms < end, using the bar end sent by the API. Trades outside
// every loaded bar (before the first, after the last, or in a session gap) get no marker.
const barFor = (data, ms) => {
  let lo = 0, hi = data.length - 1;
  if (hi < 0 || ms < barStartMs(data[0].time)) return null;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (barStartMs(data[mid].time) <= ms) lo = mid; else hi = mid - 1;
  }
  return ms < data[lo].end * 1000 ? data[lo] : null;
};

const timeLabel = (t) => {
  if (typeof t === 'string') return t;
  if (typeof t === 'number') return new Date(t * 1000).toISOString().slice(0, 16).replace('T', ' ');
  if (t?.year) return `${t.year}-${String(t.month).padStart(2, '0')}-${String(t.day).padStart(2, '0')}`;
  return '';
};
const keyOf = (t) => (typeof t === 'object' && t?.year ? timeLabel(t) : t);
const f2 = (v) => (v === null || v === undefined ? undefined : v.toFixed(2));

// One legend for every chart: any crosshair move looks the bar up by time in the API rows.
const legendFor = (row) => {
  const indicators = {};
  for (const [label, key] of [['SMA5', 'sma5'], ['SMA10', 'sma10'], ['SMA20', 'sma20'], ['BB Up', 'bb_up'], ['BB Mid', 'bb_mid'], ['BB Low', 'bb_low'],
                              ['RSI', 'rsi'], ['MACD', 'macd'], ['Signal', 'signal']]) {
    const wanted = label.startsWith('BB') ? marketStore.selectedIndicators.includes('BB')
      : label === 'Signal' ? marketStore.selectedIndicators.includes('MACD') : marketStore.selectedIndicators.includes(label);
    if (wanted && f2(row[key]) !== undefined) indicators[label] = f2(row[key]);
  }
  if (pnlSeries && row.total_pnl !== null && row.total_pnl !== undefined) indicators['PnL'] = row.total_pnl.toFixed(0);
  const bt = btByTime.get(row.time);
  if (backtestLineSeries && bt !== undefined) indicators['BT Equity'] = bt.toFixed(0);
  return {
    time: timeLabel(row.time), open: f2(row.open), high: f2(row.high), low: f2(row.low), close: f2(row.close),
    v: row.value === null || row.value === undefined ? '--' : (row.value / 1000).toFixed(0) + 'K', indicators,
  };
};

const onCrosshair = (param) => {
  if (!param || !param.time || !param.point || param.point.x < 0 || param.point.y < 0) {
    if (lastValidData) legendData.value = lastValidData;
    return;
  }
  if (props.mode === 'equity') {
    if (!param.seriesPrices) return;
    const newLegend = { time: timeLabel(param.time), indicators: {} };
    for (const [label, series] of [['Total ROI', equityTotalSeries], ['TW ROI', equityTWSeries], ['US ROI', equityUSSeries]]) {
      const val = series && param.seriesPrices.get(series);
      if (val !== undefined && val !== null) newLegend.indicators[label] = val.toFixed(2) + '%';
    }
    legendData.value = newLegend;
    return;
  }
  const row = rowsByTime.get(keyOf(param.time));
  if (row) legendData.value = legendFor(row);
};

const initChart = () => {
  if (!chartContainer.value) return;

  chart = createChart(chartContainer.value, chartOptions(chartContainer.value, {
    leftPriceScale: { borderColor: '#30363d', visible: false },
  }));

  // lightweight-charts 3.x has no autoSize option; follow the container sizes ourselves.
  resizeObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      const c = observed.get(entry.target);
      const { width, height } = entry.contentRect;
      if (c && width > 0 && height > 0) c.resize(width, height);
    }
    scheduleAlign();
  });
  observe(chartContainer.value, chart);

  candleSeries = chart.addCandlestickSeries({
    upColor: '#3fb950', downColor: '#f85149', borderVisible: false,
    wickUpColor: '#3fb950', wickDownColor: '#f85149',
  });

  volumeSeries = chart.addHistogramSeries({
    color: '#238636', priceFormat: { type: 'volume' }, priceScaleId: 'volume', lastValueVisible: false, priceLineVisible: false,
  });
  volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });

  chart.subscribeCrosshairMove(onCrosshair);
  chart.timeScale().subscribeVisibleLogicalRangeChange(syncRange(chart));
};

// Money-valued lines (PnL, backtest equity) are drawn on an axis-less overlay scale in the top
// part of the main chart; their value is read from the legend.
const addMoneySeries = (options) => {
  const series = chart.addLineSeries({ lineWidth: 2, priceLineVisible: false, lastValueVisible: false, priceScaleId: 'money', ...options });
  series.priceScale().applyOptions({ scaleMargins: { top: 0.06, bottom: 0.6 } });
  return series;
};

const clearIndicators = () => {
  for (const series of Object.values(indicatorSeries)) { chart.removeSeries(series); }
  indicatorSeries = {};
  if (pnlSeries) { chart.removeSeries(pnlSeries); pnlSeries = null; }
  if (backtestLineSeries) { chart.removeSeries(backtestLineSeries); backtestLineSeries = null; }
  btByTime = new Map();
  destroyPanels();
  scheduleAlign();
};

const fetchData = async () => {
  if (!chart) return;
  const generation = ++fetchGeneration;
  const stale = () => generation !== fetchGeneration || !chart;
  if (props.mode === 'symbol' && props.symbol) {
    try {
      const res = await axios.get(`/api/kbars/${encodeURIComponent(props.symbol)}`, { params: { interval: marketStore.currentInterval, t: Date.now() } });
      if (stale()) return;
      const data = res.data;
      if (!data || data.length === 0) {
        candleSeries.setData([]); volumeSeries.setData([]); clearIndicators();
        return;
      }

      const candles = data.map(d => ({ time: d.time, open: d.open, high: d.high, low: d.low, close: d.close }));
      const volumes = data.map(d => ({ time: d.time, value: d.value, color: d.close >= d.open ? 'rgba(63, 185, 80, 0.3)' : 'rgba(248, 81, 73, 0.3)' }));

      candleSeries.setData(candles);
      volumeSeries.setData(volumes);
      rowsByTime = new Map(data.map(d => [d.time, d]));

      clearIndicators();
      const colors = { SMA5: '#f2c94c', SMA10: '#f2994a', SMA20: '#1f6feb', BB: '#9b51e0', RSI: '#56ccf2', MACD: '#2962FF' };

      const panels = PANEL_ORDER.filter(n => marketStore.selectedIndicators.includes(n) && data[0][n.toLowerCase()] !== undefined);
      // The date axis is drawn once, under the last chart.
      chart.applyOptions({ timeScale: { visible: panels.length === 0 } });
      await buildPanels(panels, data, colors);
      if (stale()) return;

      marketStore.selectedIndicators.forEach(id => {
        const key = id.toLowerCase();
        if (id === 'BB' && data[0].bb_up !== undefined) {
          indicatorSeries['BB Up'] = chart.addLineSeries({ color: colors.BB, lineWidth: 1, lineStyle: 2, priceLineVisible: false });
          indicatorSeries['BB Low'] = chart.addLineSeries({ color: colors.BB, lineWidth: 1, lineStyle: 2, priceLineVisible: false });
          indicatorSeries['BB Mid'] = chart.addLineSeries({ color: '#56ccf2', lineWidth: 1, priceLineVisible: false });
          indicatorSeries['BB Up'].setData(lineData(data, 'bb_up'));
          indicatorSeries['BB Low'].setData(lineData(data, 'bb_low'));
          indicatorSeries['BB Mid'].setData(lineData(data, 'bb_mid'));
        } else if (id === 'MACD' || id === 'RSI') {
          // drawn in their own charts (buildPanels)
        } else if (data[0][key] !== undefined) {
          indicatorSeries[id] = chart.addLineSeries({ color: colors[id] || '#56ccf2', lineWidth: 1, priceLineVisible: false });
          indicatorSeries[id].setData(lineData(data, key));
        }
      });

      
      let markers = [];
      const bt = marketStore.backtestResults;
      if (marketStore.backtestEnabled && bt && bt.symbol === props.symbol && bt.interval === marketStore.currentInterval) {
        // BACKTEST MODE (bar times come from the same series, so they match exactly)
        let validBtMarkers = [];
        bt.trades.forEach(t => {
           const candle = barFor(data, barStartMs(t.time));
           if (candle) {
             validBtMarkers.push({
               time: candle.time,
               position: t.side === 'buy' ? 'belowBar' : 'aboveBar',
               color: t.side === 'buy' ? '#3fb950' : '#f85149',
               shape: t.side === 'buy' ? 'arrowUp' : 'arrowDown',
               text: 'BT ' + t.side.toUpperCase()
             });
           }
        });
        markers = validBtMarkers;

        
        if (bt.chart_data?.length > 0) {
          backtestLineSeries = addMoneySeries({ color: '#f2c94c' });
          backtestLineSeries.setData(bt.chart_data);
          btByTime = new Map(bt.chart_data.map(d => [d.time, d.value]));
        }
      } else {
        
        // REAL PORTFOLIO MODE
        const actualTrades = portfolioStore.trades.filter(t => t.symbol === props.symbol);
        
        // We need to map trade timestamps to the EXACT candle time
        // If data is minute/hourly, data[i].time is a UNIX timestamp (number)
        // If daily, it's a string 'YYYY-MM-DD'
        
        let validMarkers = [];
        actualTrades.forEach(t => {
           const closestCandle = barFor(data, tradeMs(t.timestamp));
           if (closestCandle) {
             const existingMarker = validMarkers.find(m => m.time === closestCandle.time && m.originalAction === t.action);
             if (existingMarker) {
               existingMarker.shares += t.shares;
               existingMarker.text = `${t.action === 'BUY' ? 'B' : 'S'} ${existingMarker.shares}`;
             } else {
               validMarkers.push({
                 time: closestCandle.time,
                 originalAction: t.action,
                 position: t.action === 'BUY' ? 'belowBar' : 'aboveBar',
                 color: t.action === 'BUY' ? '#3fb950' : '#f85149',
                 shape: t.action === 'BUY' ? 'arrowUp' : 'arrowDown',
                 shares: t.shares,
                 text: `${t.action === 'BUY' ? 'B' : 'S'} ${t.shares}`
               });
             }
           }
        });
        
        // Remove the temporary 'originalAction' and 'shares' properties before passing to Lightweight Charts
        markers = validMarkers.map(m => ({
          time: m.time,
          position: m.position,
          color: m.color,
          shape: m.shape,
          text: m.text
        }));

        const pnlData = data.filter(d => d.total_pnl !== undefined && d.total_pnl !== null).map(d => ({ time: d.time, value: d.total_pnl }));
        if (pnlData.length > 0) {
            pnlSeries = addMoneySeries({ color: '#ff7eb9' });
            pnlSeries.setData(pnlData);
        }
      }

      markers.sort((a, b) => barStartMs(a.time) - barStartMs(b.time));
      candleSeries.setMarkers(markers);

      if (equityTotalSeries) { chart.removeSeries(equityTotalSeries); equityTotalSeries = null; }
      if (equityTWSeries) { chart.removeSeries(equityTWSeries); equityTWSeries = null; }
      if (equityUSSeries) { chart.removeSeries(equityUSSeries); equityUSSeries = null; }
      const barsToDisplay = 120;
      const range = data.length > barsToDisplay
        ? { from: data.length - barsToDisplay, to: data.length - 1 + 3 }
        : { from: 0, to: data.length - 1 + 3 };
      allCharts().forEach(c => c.timeScale().setVisibleLogicalRange(range));
      scheduleAlign();

      lastValidData = legendFor(data[data.length - 1]);
      legendData.value = lastValidData;
    } catch (e) { console.error('Fetch Error:', e); }
  } else if (props.mode === 'equity') {
    try {
      const res = await axios.get('/api/equity');
      if (stale()) return;
      const data = res.data;
      candleSeries.setData([]); volumeSeries.setData([]); clearIndicators();
      const eqOptions = {
        priceFormat: { type: 'custom', formatter: price => price.toFixed(2) + '%' }
      };
      if (!equityTotalSeries) equityTotalSeries = chart.addLineSeries({ color: '#f2c94c', lineWidth: 3, title: 'Total ROI', ...eqOptions });
      if (!equityTWSeries) equityTWSeries = chart.addLineSeries({ color: '#1f6feb', lineWidth: 2, title: 'TW ROI', ...eqOptions });
      if (!equityUSSeries) equityUSSeries = chart.addLineSeries({ color: '#f87171', lineWidth: 2, title: 'US ROI', ...eqOptions });
      
      // Read the legend values first: setData() rewrites each point's `time` string in place
      // into a {year, month, day} object (lightweight-charts 3.x), which would then print as JSON.
      const lastTotal = data.total && data.total.length ? { ...data.total[data.total.length - 1] } : null;
      const lastTw = data.tw && data.tw.length ? data.tw[data.tw.length - 1].value : 0;
      const lastUs = data.us && data.us.length ? data.us[data.us.length - 1].value : 0;

      if (data.total && data.total.length) equityTotalSeries.setData(data.total);
      if (data.tw && data.tw.length) equityTWSeries.setData(data.tw);
      if (data.us && data.us.length) equityUSSeries.setData(data.us);
      
      chart.timeScale().fitContent();
      
      if (lastTotal) {
        const last = lastTotal;
        legendData.value = {
          time: last.time,
          indicators: {
            'Total ROI': last.value.toFixed(2) + '%',
            'TW ROI': lastTw.toFixed(2) + '%',
            'US ROI': lastUs.toFixed(2) + '%'
          }
        };
      }
    } catch (e) { console.error('Equity Error:', e); }
  }
};

onMounted(() => { initChart(); fetchData(); });
watch(() => [props.symbol, props.mode, marketStore.currentInterval, marketStore.selectedIndicators, marketStore.backtestEnabled, marketStore.backtestResults, portfolioStore.trades], () => fetchData(), { deep: true });
onUnmounted(() => {
  fetchGeneration++;
  if (resizeObserver) resizeObserver.disconnect();
  destroyPanels();
  observed.clear();
  if (chart) { chart.remove(); chart = null; }
});
</script>

<template>
  <div class="relative w-full h-full select-none overflow-hidden flex flex-col">
    <div ref="chartContainer" class="flex-1 min-h-0" :style="{ paddingRight: axisGap.main + 'px' }"></div>
    <div v-for="name in activePanels" :key="name" class="relative shrink-0 border-t border-border-line" :style="{ height: PANEL_PX + 'px' }">
      <div :ref="el => { if (el) panelEls[name] = el }" class="absolute inset-0" :style="{ paddingRight: (axisGap[name] || 0) + 'px' }"></div>
      <div class="absolute left-2 top-1 z-10 text-[10px] font-mono text-gray-500 pointer-events-none">
        {{ name }}<span v-if="name === 'RSI'" class="text-gray-600"> · 30 / 70</span>
      </div>
    </div>

    <!-- Equity Controls -->
    <div v-if="mode === 'equity'" class="absolute top-4 right-4 z-20 flex gap-2">
      <button @click="toggleEquityLine('Total')" :class="showEqTotal ? 'bg-yellow-500/20 text-yellow-500 border-yellow-500' : 'bg-gray-800 text-gray-500 border-gray-700'" class="px-2 py-1 text-xs font-bold border rounded transition-colors cursor-pointer select-none">Total</button>
      <button @click="toggleEquityLine('TW')" :class="showEqTW ? 'bg-blue-500/20 text-blue-500 border-blue-500' : 'bg-gray-800 text-gray-500 border-gray-700'" class="px-2 py-1 text-xs font-bold border rounded transition-colors cursor-pointer select-none">TW (TWD)</button>
      <button @click="toggleEquityLine('US')" :class="showEqUS ? 'bg-red-500/20 text-red-500 border-red-500' : 'bg-gray-800 text-gray-500 border-gray-700'" class="px-2 py-1 text-xs font-bold border rounded transition-colors cursor-pointer select-none">US (USD)</button>
    </div>
    <div :style="{ top: legendPos.y + 'px', left: legendPos.x + 'px' }" class="absolute bg-black/80 backdrop-blur-md border border-white/10 p-3 rounded-lg text-[11px] z-20 shadow-2xl flex flex-col gap-2 min-w-[220px] transition-opacity hover:opacity-100 opacity-90">
      <div @mousedown.prevent="startDrag" class="flex justify-between items-center border-b border-white/10 pb-1.5 cursor-move" title="Drag to move">
        <div class="flex items-center gap-2">
          <span class="text-white font-bold uppercase tracking-wider">{{ symbol }}</span>
          <span class="text-gray-500 font-mono">{{ legendData.time }}</span>
        </div>
        <button @mousedown.stop @click="isLegendExpanded = !isLegendExpanded" class="text-gray-500 hover:text-white px-1.5 py-0.5 rounded bg-white/5 cursor-pointer z-30">
          {{ isLegendExpanded ? '−' : '+' }}
        </button>
      </div>
      <div v-show="isLegendExpanded" class="flex flex-col gap-2">
        <div v-if="mode !== 'equity'" class="grid grid-cols-2 gap-x-4 gap-y-1.5">
          <div class="flex justify-between items-center"><span class="text-gray-500 text-[10px]">OPEN</span><span class="text-white font-mono">{{ legendData.open }}</span></div>
          <div class="flex justify-between items-center"><span class="text-gray-500 text-[10px]">HIGH</span><span class="text-white font-mono">{{ legendData.high }}</span></div>
          <div class="flex justify-between items-center"><span class="text-gray-500 text-[10px]">LOW</span><span class="text-white font-mono">{{ legendData.low }}</span></div>
          <div class="flex justify-between items-center"><span class="text-gray-500 text-[10px]">CLOSE</span><span :class="legendData.close >= legendData.open ? 'text-text-green' : 'text-text-red'" class="font-mono font-bold text-sm">{{ legendData.close }}</span></div>
          <div class="flex justify-between col-span-2 border-t border-white/10 pt-1.5 mt-0.5">
             <span class="text-gray-500 text-[10px]">VOLUME</span><span class="text-gray-300 font-mono">{{ legendData.v }}</span>
          </div>
        </div>
        <div v-if="Object.keys(legendData.indicators || {}).length > 0" class="border-t border-white/10 pt-1.5 mt-0.5 grid grid-cols-1 gap-1">
          <div v-for="(val, id) in legendData.indicators" :key="id" class="flex justify-between items-center">
            <span class="text-gray-500 text-[9px] uppercase tracking-tighter">{{ id.replace('_', ' ') }}</span>
            <span :class="(id.includes('PnL') || id.includes('ROI')) ? (parseFloat(val) >= 0 ? 'text-text-green' : 'text-text-red') : 'text-blue-400'" class="font-mono font-bold">{{ val }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
