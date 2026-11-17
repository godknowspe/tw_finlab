<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import axios from 'axios';

const props = defineProps({ symbol: { type: String, default: '' } });

// The index that gives the backdrop: TW symbols against the TAIEX, everything else the S&P 500.
const isTW = (s) => /^\d{4}[0-9A-Z]{0,2}$/.test(s) || s.endsWith('.TWO') || s === '^TWII';
const benchmark = computed(() => (isTW(props.symbol) ? '^TWII' : '^GSPC'));

const own = ref(null);
const bench = ref(null);
const trips = ref(null);
const open = ref(false);
let generation = 0;

const get = async (sym) => {
  try { return (await axios.get(`/api/regime/${encodeURIComponent(sym)}`)).data; } catch { return null; }
};

const load = async () => {
  const g = ++generation;
  if (!props.symbol) { own.value = bench.value = null; return; }
  const [a, b] = await Promise.all([get(props.symbol), props.symbol === benchmark.value ? null : get(benchmark.value)]);
  if (g !== generation) return;
  own.value = a; bench.value = b;
};
const loadTrips = async () => {
  if (trips.value) return;
  try { trips.value = (await axios.get('/api/regime-trips')).data; } catch { trips.value = { trips: [], groups: [] }; }
};
const toggle = () => { open.value = !open.value; if (open.value) loadTrips(); };

watch(() => props.symbol, load);
onMounted(load);

const TREND = { up: ['多頭', 'text-text-green border-green-500/40 bg-green-500/10'], down: ['空頭', 'text-text-red border-red-500/40 bg-red-500/10'], mixed: ['多空不明', 'text-gray-300 border-gray-500/40 bg-gray-500/10'] };
const VOL = { calm: ['平靜', 'text-sky-400'], normal: ['正常', 'text-gray-300'], wild: ['劇烈', 'text-yellow-400'] };
const pct = (v) => (v === null || v === undefined ? '—' : (v > 0 ? '+' : '') + (v * 100).toFixed(1) + '%');
const rate = (v) => (v === null || v === undefined ? '—' : (v * 100).toFixed(0) + '%');
const money = (v, cur) => (v > 0 ? '+' : '') + v.toLocaleString(undefined, { maximumFractionDigits: cur === 'USD' ? 2 : 0 });

const STAT_ROWS = [['all', '全部日子（基準）'], ['trend:up', '多頭'], ['trend:mixed', '多空不明'], ['trend:down', '空頭'], ['vol:calm', '波動平靜'], ['vol:normal', '波動正常'], ['vol:wild', '波動劇烈']];
const current = computed(() => (own.value?.available ? [`trend:${own.value.trend}`, `vol:${own.value.vol}`] : []));
</script>

<template>
  <div class="shrink-0 border-b border-border-line bg-[#0d1117]/80 text-[11px]">
    <div class="flex items-center gap-4 px-4 py-1.5 flex-wrap">
      <template v-if="own?.available">
        <div class="flex items-center gap-2" :title="own.facts.join('\n')">
          <span class="text-gray-500 font-mono">{{ symbol }}</span>
          <span :class="TREND[own.trend][1]" class="px-2 py-0.5 rounded border font-bold">{{ TREND[own.trend][0] }}</span>
          <span class="text-gray-400">{{ own.phase }}</span>
          <span class="text-gray-600">·</span>
          <span class="text-gray-500">波動</span><span :class="VOL[own.vol][1]" class="font-bold">{{ VOL[own.vol][0] }}</span>
          <span class="text-gray-600">· 已 {{ own.days_in_state }} 日</span>
        </div>
      </template>
      <span v-else-if="own && !own.available" class="text-gray-600">{{ symbol }}：{{ own.reason }}</span>

      <div v-if="bench?.available" class="flex items-center gap-2 border-l border-white/10 pl-4" :title="bench.facts.join('\n')">
        <span class="text-gray-500 font-mono">{{ benchmark }}</span>
        <span :class="TREND[bench.trend][1]" class="px-2 py-0.5 rounded border font-bold">{{ TREND[bench.trend][0] }}</span>
        <span class="text-gray-400">{{ bench.phase }}</span>
        <span class="text-gray-600">·</span>
        <span class="text-gray-500">波動</span><span :class="VOL[bench.vol][1]" class="font-bold">{{ VOL[bench.vol][0] }}</span>
      </div>

      <span v-if="own?.pending" class="text-yellow-500/80">{{ own.pending }}</span>
      <button v-if="own?.available" @click="toggle" class="ml-auto text-gray-500 hover:text-white px-2 py-0.5 rounded bg-white/5 border border-white/10">
        {{ open ? '收起 ▲' : '依據與歷史統計 ▼' }}
      </button>
    </div>

    <div v-if="open && own?.available" class="px-4 pb-3 space-y-3 border-t border-white/5 pt-2 max-h-[45vh] overflow-y-auto custom-scrollbar">
      <ul class="text-gray-400 space-y-0.5">
        <li v-for="f in own.facts" :key="f">· {{ f }}</li>
      </ul>

      <div class="bg-yellow-500/5 border border-yellow-600/30 rounded px-3 py-2 text-yellow-200/80 leading-relaxed">
        這個標籤只描述現在的狀態，不是買賣訊號。下表是這檔標的自己的歷史：各狀態確認後，接下來 {{ own.forward.days }} 個交易日的報酬，
        與「全部日子」的基準相比，差別通常很小，甚至相反（急跌確認後常見反彈）。相鄰日子的報酬高度重疊，樣本看「段數」比看「天數」可靠。
      </div>

      <table class="w-full text-left font-mono">
        <thead><tr class="text-gray-500 border-b border-white/10">
          <th class="py-1 font-medium">狀態</th><th class="text-right font-medium">天數</th><th class="text-right font-medium">段數</th>
          <th class="text-right font-medium">{{ own.forward.days }}日中位數</th><th class="text-right font-medium">平均</th><th class="text-right font-medium">勝率</th>
        </tr></thead>
        <tbody>
          <tr v-for="[key, label] in STAT_ROWS" :key="key" v-show="own.forward.stats[key]"
              :class="current.includes(key) ? 'bg-blue-500/10 text-white' : key === 'all' ? 'text-gray-300' : 'text-gray-400'" class="border-b border-white/5">
            <td class="py-1 font-sans">{{ label }}<span v-if="current.includes(key)" class="text-blue-400"> ← 目前</span></td>
            <td class="text-right">{{ own.forward.stats[key]?.days }}</td>
            <td class="text-right" :class="own.forward.stats[key]?.episodes < 10 ? 'text-yellow-500' : ''">{{ own.forward.stats[key]?.episodes }}</td>
            <td class="text-right">{{ pct(own.forward.stats[key]?.median) }}</td>
            <td class="text-right">{{ pct(own.forward.stats[key]?.mean) }}</td>
            <td class="text-right">{{ rate(own.forward.stats[key]?.win_rate) }}</td>
          </tr>
        </tbody>
      </table>

      <div v-if="trips">
        <div class="text-gray-300 font-bold mb-1">你的來回交易，依第一次賣出當天的狀態分組</div>
        <table v-if="trips.groups.length" class="w-full text-left font-mono">
          <thead><tr class="text-gray-500 border-b border-white/10">
            <th class="py-1 font-medium">賣出時狀態</th><th class="text-right font-medium">幣別</th><th class="text-right font-medium">輪數</th>
            <th class="text-right font-medium">賺（比持有）</th><th class="text-right font-medium">合計比持有</th>
          </tr></thead>
          <tbody>
            <template v-for="g in trips.groups" :key="g.trend + g.vol">
              <tr v-for="(c, cur) in g.currencies" :key="g.trend + g.vol + cur" class="border-b border-white/5 text-gray-300">
                <td class="py-1 font-sans">{{ TREND[g.trend][0] }} · 波動{{ VOL[g.vol][0] }}</td>
                <td class="text-right">{{ cur }}</td>
                <td class="text-right" :class="c.trips < 5 ? 'text-yellow-500' : ''">{{ c.trips }}</td>
                <td class="text-right">{{ c.won }}/{{ c.trips }}</td>
                <td class="text-right" :class="c.vs_hold >= 0 ? 'text-text-green' : 'text-text-red'">{{ money(c.vs_hold, cur) }}</td>
              </tr>
            </template>
          </tbody>
        </table>
        <div v-else class="text-gray-600">還沒有完成的來回交易。</div>
        <div class="text-gray-600 mt-1 font-sans">輪數少於 5 的標黃：樣本太小，只能參考，不能據此判斷哪種狀態適合賣出。只計已買回的完整來回，進行中與減碼不計。</div>
      </div>
    </div>
  </div>
</template>
