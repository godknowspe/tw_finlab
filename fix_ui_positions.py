with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'r') as f:
    html = f.read()

old_tabs = """<div class="p-4 border-b border-line flex justify-between items-center">
            <span class="font-bold tracking-wider text-gray-400 text-xs cursor-pointer hover:text-white">WATCHLIST</span>
            <span class="font-bold tracking-wider text-gray-400 text-xs cursor-pointer hover:text-white">POSITIONS</span>
        </div>"""
        
new_tabs = """<div class="p-4 border-b border-line flex justify-between items-center">
            <span @click="activeTab = 'watchlist'" :class="activeTab === 'watchlist' ? 'text-white' : 'text-gray-500'" class="font-bold tracking-wider text-xs cursor-pointer hover:text-white transition-colors">WATCHLIST</span>
            <span @click="activeTab = 'positions'" :class="activeTab === 'positions' ? 'text-white' : 'text-gray-500'" class="font-bold tracking-wider text-xs cursor-pointer hover:text-white transition-colors">POSITIONS</span>
        </div>"""
html = html.replace(old_tabs, new_tabs)

old_list = """<div class="flex justify-between px-4 py-2 text-xs text-gray-500 border-b border-line">
            <span>SYM</span>
            <span>LAST</span>
            <span>CHG%</span>
        </div>
        <div class="flex-1 overflow-y-auto">
            <div v-for="item in portfolio.watchlist" :key="item.symbol" 
                 class="flex justify-between items-center px-4 py-3 border-b border-line hover:bg-gray-800 cursor-pointer transition-colors duration-200"
                 :class="[currentSymbol === item.symbol ? 'bg-gray-800' : '', item.flashClass]"
                 @click="loadChart(item.symbol)">
                <div>
                    <div class="font-bold text-white flex items-center gap-2">
                        {{ item.symbol }}
                        <span v-if="currentSymbol === item.symbol && wsConnected" class="w-2 h-2 rounded-full bg-green-500 animate-pulse" title="Live Data"></span>
                    </div>
                    <div class="text-xs text-gray-500">{{ item.name }}</div>
                </div>
                <div class="text-right">
                    <div class="font-mono text-white">{{ item.last.toFixed(2) }}</div>
                    <div class="text-xs font-mono" :class="item.chg_pct.startsWith('+') ? 'text-green' : 'text-red'">
                        {{ item.chg_pct }}
                    </div>
                </div>
            </div>
        </div>"""

new_list = """
        <!-- Watchlist 列表 -->
        <div v-if="activeTab === 'watchlist'" class="flex-1 flex flex-col min-h-0">
            <div class="flex justify-between px-4 py-2 text-xs text-gray-500 border-b border-line">
                <span>SYM</span>
                <span>LAST</span>
                <span>CHG%</span>
            </div>
            <div class="flex-1 overflow-y-auto">
                <div v-for="item in portfolio.watchlist" :key="item.symbol" 
                     class="flex justify-between items-center px-4 py-3 border-b border-line hover:bg-gray-800 cursor-pointer transition-colors duration-200"
                     :class="[currentSymbol === item.symbol ? 'bg-gray-800' : '', item.flashClass]"
                     @click="loadChart(item.symbol)">
                    <div>
                        <div class="font-bold text-white flex items-center gap-2">
                            {{ item.symbol }}
                            <span v-if="currentSymbol === item.symbol && wsConnected" class="w-2 h-2 rounded-full bg-green-500 animate-pulse" title="Live Data"></span>
                        </div>
                        <div class="text-xs text-gray-500">{{ item.name }}</div>
                    </div>
                    <div class="text-right">
                        <div class="font-mono text-white">{{ item.last.toFixed(2) }}</div>
                        <div class="text-xs font-mono" :class="item.chg_pct.startsWith('+') ? 'text-green' : 'text-red'">
                            {{ item.chg_pct }}
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Positions 列表 -->
        <div v-if="activeTab === 'positions'" class="flex-1 flex flex-col min-h-0">
            <div class="flex justify-between px-4 py-2 text-xs text-gray-500 border-b border-line">
                <span>SYM</span>
                <span>QTY/AVG</span>
                <span>UNREALIZED</span>
            </div>
            <div class="flex-1 overflow-y-auto">
                <div v-for="pos in portfolio.positions" :key="pos.symbol" 
                     class="flex justify-between items-center px-4 py-3 border-b border-line hover:bg-gray-800 cursor-pointer transition-colors duration-200"
                     :class="currentSymbol === pos.symbol ? 'bg-gray-800' : ''"
                     @click="loadChart(pos.symbol)">
                    <div>
                        <div class="font-bold text-white flex items-center gap-2">
                            {{ pos.symbol }}
                        </div>
                        <div class="text-xs text-blue-400 font-mono">{{ pos.shares }} 股</div>
                    </div>
                    <div class="text-right">
                        <div class="text-xs text-gray-400 font-mono">@{{ pos.avg_cost.toFixed(2) }}</div>
                        <div class="text-sm font-mono font-bold" :class="pos.unrealized >= 0 ? 'text-green' : 'text-red'">
                            {{ pos.unrealized > 0 ? '+' : '' }}{{ pos.unrealized.toLocaleString() }}
                        </div>
                    </div>
                </div>
                <div v-if="!portfolio.positions || portfolio.positions.length === 0" class="p-4 text-center text-gray-500 text-xs">
                    No open positions.
                </div>
            </div>
        </div>
"""
html = html.replace(old_list, new_list)

old_setup = "const currentSymbol = ref('2330');"
new_setup = "const currentSymbol = ref('2330');\n                const activeTab = ref('watchlist');\n                let costLine = null;"
html = html.replace(old_setup, new_setup)

old_return = "currentSymbol, currentQuote,"
new_return = "currentSymbol, currentQuote, activeTab,"
html = html.replace(old_return, new_return)

cost_line_logic = """
                            if (costLine) {
                                candleSeries.removePriceLine(costLine);
                                costLine = null;
                            }
                            const pos = portfolio.value.positions?.find(p => p.symbol === symbol);
                            if (pos) {
                                costLine = candleSeries.createPriceLine({
                                    price: pos.avg_cost,
                                    color: '#3b82f6',
                                    lineWidth: 2,
                                    lineStyle: LightweightCharts.LineStyle.Dashed,
                                    axisLabelVisible: true,
                                    title: 'AVG COST',
                                });
                            }
"""
html = html.replace('connectWebSocket(symbol);', f'connectWebSocket(symbol);{cost_line_logic}')

with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'w') as f:
    f.write(html)
