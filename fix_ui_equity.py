import re

with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'r') as f:
    html = f.read()

# 1. Top bar changes for Equity/Symbol toggle
old_top_bar = """<div class="h-12 border-b border-line flex items-center justify-between px-4">
            <div class="flex items-center gap-4">
                <span class="font-bold text-lg text-white">{{ currentSymbol }}</span>
                <span class="text-gray-400">| 1D</span>
                <!-- 最新報價顯示列 -->
                <span v-if="currentQuote" class="font-mono text-lg ml-4 flex items-center gap-2" :class="currentQuote.chg >= 0 ? 'text-green' : 'text-red'">
                    {{ currentQuote.close.toFixed(2) }} 
                    <span class="text-sm">({{ currentQuote.chg >= 0 ? '+' : '' }}{{ currentQuote.chgPct }}%)</span>
                </span>
            </div>
            
            <div class="flex items-center gap-2 text-xs text-gray-400">
                <span v-if="wsConnected" class="flex items-center gap-1 text-green-400"><span class="w-2 h-2 rounded-full bg-green-500"></span> LIVE</span>
                <span v-else class="flex items-center gap-1 text-red-400"><span class="w-2 h-2 rounded-full bg-red-500"></span> OFFLINE</span>
            </div>
        </div>"""

new_top_bar = """<div class="h-12 border-b border-line flex items-center justify-between px-4">
            <div class="flex items-center gap-4">
                <!-- Toggle Mode -->
                <div class="flex bg-gray-900 rounded p-1 border border-gray-700">
                    <button @click="switchMode('symbol')" :class="chartMode === 'symbol' ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'" class="px-3 py-0.5 text-xs rounded transition-colors font-bold tracking-wider">SYMBOL</button>
                    <button @click="switchMode('equity')" :class="chartMode === 'equity' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-gray-300'" class="px-3 py-0.5 text-xs rounded transition-colors font-bold tracking-wider">EQUITY</button>
                </div>
                
                <span v-if="chartMode === 'symbol'" class="font-bold text-lg text-white">{{ currentSymbol }}</span>
                <span v-else class="font-bold text-lg text-blue-400">TOTAL EQUITY (NTD)</span>
                
                <span v-if="chartMode === 'symbol'" class="text-gray-400">| 1D</span>
                <span v-else class="text-gray-400">| Simulated Performance</span>
                
                <!-- 最新報價顯示列 -->
                <span v-if="chartMode === 'symbol' && currentQuote" class="font-mono text-lg ml-4 flex items-center gap-2" :class="currentQuote.chg >= 0 ? 'text-green' : 'text-red'">
                    {{ currentQuote.close.toFixed(2) }} 
                    <span class="text-sm">({{ currentQuote.chg >= 0 ? '+' : '' }}{{ currentQuote.chgPct }}%)</span>
                </span>
                
                <!-- Equity 總額顯示 -->
                <span v-if="chartMode === 'equity' && equityValue" class="font-mono text-lg ml-4 flex items-center gap-2 text-white">
                    {{ equityValue.toLocaleString() }}
                </span>
            </div>
            
            <div v-if="chartMode === 'symbol'" class="flex items-center gap-2 text-xs text-gray-400">
                <span v-if="wsConnected" class="flex items-center gap-1 text-green-400"><span class="w-2 h-2 rounded-full bg-green-500"></span> LIVE</span>
                <span v-else class="flex items-center gap-1 text-red-400"><span class="w-2 h-2 rounded-full bg-red-500"></span> OFFLINE</span>
            </div>
        </div>"""

html = html.replace(old_top_bar, new_top_bar)

# 2. Add chartMode, equityValue, and areaSeries variables to setup
old_setup = "const activeTab = ref('watchlist');"
new_setup = "const activeTab = ref('watchlist');\n                const chartMode = ref('symbol');\n                const equityValue = ref(null);"
html = html.replace(old_setup, new_setup)

old_return = "activeTab,"
new_return = "activeTab, chartMode, equityValue, switchMode,"
html = html.replace(old_return, new_return)

old_vars = "let candleSeries = null;"
new_vars = "let candleSeries = null;\n                let areaSeries = null;"
html = html.replace(old_vars, new_vars)

# 3. Create areaSeries in initChart
old_init_end = "});\n\n                    window.addEventListener('resize'"
new_init_end = """});
                    
                    areaSeries = chart.addAreaSeries({
                        topColor: 'rgba(59, 130, 246, 0.4)',
                        bottomColor: 'rgba(59, 130, 246, 0.0)',
                        lineColor: '#3b82f6',
                        lineWidth: 2,
                    });
                    // Initially hide equity curve
                    areaSeries.applyOptions({ visible: false });

                    window.addEventListener('resize'"""
html = html.replace(old_init_end, new_init_end)

# 4. Handle switchMode logic
switch_mode_logic = """
                const switchMode = async (mode) => {
                    chartMode.value = mode;
                    if (mode === 'symbol') {
                        areaSeries.applyOptions({ visible: false });
                        candleSeries.applyOptions({ visible: true });
                        loadChart(currentSymbol.value);
                    } else {
                        candleSeries.applyOptions({ visible: false });
                        areaSeries.applyOptions({ visible: true });
                        if(ws) { ws.close(); wsConnected.value = false; }
                        
                        try {
                            const res = await fetch('/api/equity');
                            const data = await res.json();
                            if(data && data.length > 0) {
                                areaSeries.setData(data);
                                chart.timeScale().fitContent();
                                equityValue.value = data[data.length - 1].value;
                            }
                        } catch(e) { console.error(e); }
                    }
                };
"""
html = html.replace('const loadChart = async (symbol) => {', switch_mode_logic + '\n                const loadChart = async (symbol) => {')

# 5. Fix loadChart to only fetch if in symbol mode, or switch to symbol mode if clicked from watchlist
old_load = """const loadChart = async (symbol) => {
                    currentSymbol.value = symbol;
                    try {"""
new_load = """const loadChart = async (symbol) => {
                    if (chartMode.value !== 'symbol') {
                        chartMode.value = 'symbol';
                        areaSeries.applyOptions({ visible: false });
                        candleSeries.applyOptions({ visible: true });
                    }
                    currentSymbol.value = symbol;
                    try {"""
html = html.replace(old_load, new_load)


with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'w') as f:
    f.write(html)
