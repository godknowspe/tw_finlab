with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'r') as f:
    html = f.read()

old_tabs = """<div class="p-4 border-b border-line flex justify-between items-center">
            <span @click="activeTab = 'watchlist'" :class="activeTab === 'watchlist' ? 'text-white' : 'text-gray-500'" class="font-bold tracking-wider text-xs cursor-pointer hover:text-white transition-colors">WATCHLIST</span>
            <span @click="activeTab = 'positions'" :class="activeTab === 'positions' ? 'text-white' : 'text-gray-500'" class="font-bold tracking-wider text-xs cursor-pointer hover:text-white transition-colors">POSITIONS</span>
        </div>"""
new_tabs = """<div class="p-4 border-b border-line flex justify-between items-center">
            <span @click="activeTab = 'watchlist'" :class="activeTab === 'watchlist' ? 'text-white' : 'text-gray-500'" class="font-bold tracking-wider text-xs cursor-pointer hover:text-white transition-colors">WATCHLIST</span>
            <span @click="activeTab = 'positions'" :class="activeTab === 'positions' ? 'text-white' : 'text-gray-500'" class="font-bold tracking-wider text-xs cursor-pointer hover:text-white transition-colors">POSITIONS</span>
            <span @click="activeTab = 'trades'" :class="activeTab === 'trades' ? 'text-white' : 'text-gray-500'" class="font-bold tracking-wider text-xs cursor-pointer hover:text-white transition-colors">TRADES</span>
        </div>"""
html = html.replace(old_tabs, new_tabs)

old_pos_end = """<div v-if="!portfolio.positions || portfolio.positions.length === 0" class="p-4 text-center text-gray-500 text-xs">
                    No open positions.
                </div>
            </div>
        </div>"""
new_trades = """<div v-if="!portfolio.positions || portfolio.positions.length === 0" class="p-4 text-center text-gray-500 text-xs">
                    No open positions.
                </div>
            </div>
        </div>

        <!-- Trades 列表 -->
        <div v-if="activeTab === 'trades'" class="flex-1 flex flex-col min-h-0">
            <div class="flex justify-between px-4 py-2 text-xs text-gray-500 border-b border-line items-center">
                <span>ACTION/SYM</span>
                <span>QTY/PRICE</span>
                <div class="flex items-center gap-2">
                    <span>TIME</span>
                    <button @click="showAddModal('trades')" class="text-blue-400 hover:text-blue-300 ml-1">+</button>
                </div>
            </div>
            <div class="flex-1 overflow-y-auto">
                <div v-for="trade in portfolio.trades" :key="trade.id" 
                     class="flex justify-between items-center px-4 py-3 border-b border-line hover:bg-gray-800 cursor-pointer transition-colors duration-200 group">
                    <div>
                        <div class="font-bold text-white flex items-center gap-2">
                            <span :class="trade.action === 'BUY' ? 'text-red-400' : 'text-green-400'">{{ trade.action }}</span> {{ trade.symbol }}
                            <button @click.stop="delTrade(trade.id)" class="hidden group-hover:block ml-1 text-gray-500 hover:text-red-400">×</button>
                        </div>
                    </div>
                    <div class="text-right">
                        <div class="text-xs text-white font-mono">{{ trade.shares }} 股</div>
                        <div class="text-xs text-gray-400 font-mono">@{{ trade.price.toFixed(2) }}</div>
                    </div>
                    <div class="text-right">
                        <div class="text-xs text-gray-500 font-mono">{{ trade.timestamp.split('T')[0] }}</div>
                    </div>
                </div>
                <div v-if="!portfolio.trades || portfolio.trades.length === 0" class="p-4 text-center text-gray-500 text-xs">
                    No trade history.
                </div>
            </div>
        </div>"""
html = html.replace(old_pos_end, new_trades)

old_pos_header = """<div class="flex justify-between px-4 py-2 text-xs text-gray-500 border-b border-line items-center">
                <span>SYM</span>
                <span>QTY/AVG</span>
                <div class="flex items-center gap-2">
                    <span>UNREALIZED</span>
                    <button @click="showAddModal('positions')" class="text-blue-400 hover:text-blue-300 ml-1">+</button>
                </div>
            </div>"""
new_pos_header = """<div class="flex justify-between px-4 py-2 text-xs text-gray-500 border-b border-line items-center">
                <span>SYM</span>
                <span>QTY/AVG</span>
                <span>UNREALIZED</span>
            </div>"""
html = html.replace(old_pos_header, new_pos_header)

old_sync = """<div class="text-xs text-gray-500 mb-2 font-mono">[TECHNICAL SYNC]</div>
                <div class="bg-gray-900 rounded p-3 font-mono text-xs text-gray-300 space-y-1">
                    <div>Target: {{ portfolio.agent_state?.target }}</div>
                    <div>Phase: <span :class="portfolio.agent_state?.halted ? 'text-red' : 'text-white'">{{ portfolio.agent_state?.phase }}</span></div>
                    <div>SMA20: <span class="text-white">Active</span></div>
                    <div>MACD: <span class="text-green">Bullish Divergence</span></div>
                </div>"""
new_sync = """<div class="text-xs text-gray-500 mb-2 font-mono">[ACCOUNT SUMMARY]</div>
                <div class="bg-gray-900 rounded p-3 font-mono text-xs text-gray-300 space-y-1">
                    <div class="flex justify-between"><span>Total Equity:</span> <span class="text-white">${{ portfolio.summary?.total_equity?.toLocaleString() }}</span></div>
                    <div class="flex justify-between"><span>Cash Balance:</span> <span class="text-gray-400">${{ portfolio.summary?.cash?.toLocaleString() }}</span></div>
                    <div class="flex justify-between"><span>Market Value:</span> <span class="text-blue-400">${{ portfolio.summary?.market_value?.toLocaleString() }}</span></div>
                    <div class="flex justify-between"><span>Realized PnL:</span> <span :class="portfolio.summary?.realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'">${{ portfolio.summary?.realized_pnl?.toLocaleString() }}</span></div>
                </div>"""
html = html.replace(old_sync, new_sync)

old_modal = """<h2 class="text-white font-bold mb-4">{{ modalType === 'watchlist' ? '加入自選股' : '新增/更新持股' }}</h2>"""
new_modal = """<h2 class="text-white font-bold mb-4">{{ modalType === 'watchlist' ? '加入自選股' : '新增交易紀錄' }}</h2>"""
html = html.replace(old_modal, new_modal)

old_pos_fields = """<template v-else>
                    <div>
                        <label class="block text-xs text-gray-400 mb-1">股數 (Shares)</label>
                        <input v-model.number="modalForm.shares" type="number" class="w-full bg-gray-900 border border-gray-700 text-white px-3 py-2 rounded focus:outline-none focus:border-blue-500">
                    </div>
                    <div>
                        <label class="block text-xs text-gray-400 mb-1">平均成本 (Avg Cost)</label>
                        <input v-model.number="modalForm.avg_cost" type="number" step="0.01" class="w-full bg-gray-900 border border-gray-700 text-white px-3 py-2 rounded focus:outline-none focus:border-blue-500">
                    </div>
                </template>"""

new_trade_fields = """<template v-else>
                    <div>
                        <label class="block text-xs text-gray-400 mb-1">買賣方向 (Action)</label>
                        <select v-model="modalForm.action" class="w-full bg-gray-900 border border-gray-700 text-white px-3 py-2 rounded focus:outline-none focus:border-blue-500">
                            <option value="BUY">買進 (BUY)</option>
                            <option value="SELL">賣出 (SELL)</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs text-gray-400 mb-1">股數 (Shares)</label>
                        <input v-model.number="modalForm.shares" type="number" class="w-full bg-gray-900 border border-gray-700 text-white px-3 py-2 rounded focus:outline-none focus:border-blue-500">
                    </div>
                    <div>
                        <label class="block text-xs text-gray-400 mb-1">成交單價 (Price)</label>
                        <input v-model.number="modalForm.price" type="number" step="0.01" class="w-full bg-gray-900 border border-gray-700 text-white px-3 py-2 rounded focus:outline-none focus:border-blue-500">
                    </div>
                </template>"""
html = html.replace(old_pos_fields, new_trade_fields)

old_js_vars = "const modalForm = reactive({ symbol: '', name: '', ref_price: 0, shares: 0, avg_cost: 0 });"
new_js_vars = "const modalForm = reactive({ symbol: '', name: '', ref_price: 0, action: 'BUY', shares: 0, price: 0 });"
html = html.replace(old_js_vars, new_js_vars)

old_show_modal = """modalForm.shares = 0;
                    modalForm.avg_cost = 0;"""
new_show_modal = """modalForm.shares = 0;
                    modalForm.price = 0;
                    modalForm.action = 'BUY';"""
html = html.replace(old_show_modal, new_show_modal)

old_submit = "const endpoint = modalType.value === 'watchlist' ? '/api/watchlist' : '/api/positions';"
new_submit = "const endpoint = modalType.value === 'watchlist' ? '/api/watchlist' : '/api/trades';"
html = html.replace(old_submit, new_submit)

old_edit_pos = """const editPosition = (pos) => {
                    modalType.value = 'positions';
                    modalForm.symbol = pos.symbol;
                    modalForm.shares = pos.shares;
                    modalForm.avg_cost = pos.avg_cost;
                };"""
new_edit_pos = ""
html = html.replace(old_edit_pos, new_edit_pos)

old_del_pos = """const delPosition = async (symbol) => {
                    try {
                        const res = await fetch(`/api/positions/${symbol}`, { method: 'DELETE' });
                        const result = await res.json();
                        showToast(result.message, '🗑️');
                        fetchPortfolio();
                    } catch(e) { console.error(e); }
                };"""
new_del_trade = """const delTrade = async (id) => {
                    try {
                        const res = await fetch(`/api/trades/${id}`, { method: 'DELETE' });
                        const result = await res.json();
                        showToast(result.message, '🗑️');
                        fetchPortfolio();
                    } catch(e) { console.error(e); }
                };"""
html = html.replace(old_del_pos, new_del_trade)

old_ret_js = "submitModal, editWatchlist, editPosition, delWatchlist, delPosition,"
new_ret_js = "submitModal, editWatchlist, delWatchlist, delTrade,"
html = html.replace(old_ret_js, new_ret_js)

old_pos_edit_btn = """<button @click.stop="editPosition(pos)" class="hidden group-hover:block ml-1 text-blue-400 hover:text-blue-300">✎</button>
                            <button @click.stop="delPosition(pos.symbol)" class="hidden group-hover:block ml-1 text-red-500 hover:text-red-400">×</button>"""
new_pos_edit_btn = """"""
html = html.replace(old_pos_edit_btn, new_pos_edit_btn)

with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'w') as f:
    f.write(html)
