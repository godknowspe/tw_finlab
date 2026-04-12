with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'r') as f:
    html = f.read()

old_wl_item = """<div class="font-bold text-white flex items-center gap-2">
                            {{ item.symbol }}
                            <span v-if="currentSymbol === item.symbol && wsConnected" class="w-2 h-2 rounded-full bg-green-500 animate-pulse" title="Live Data"></span>
                        </div>
                        <div class="text-xs text-gray-500">{{ item.name }}</div>
                    </div>
                    <div class="text-right">"""
new_wl_item = """<div class="font-bold text-white flex items-center gap-2 group">
                            {{ item.symbol }}
                            <span v-if="currentSymbol === item.symbol && wsConnected" class="w-2 h-2 rounded-full bg-green-500 animate-pulse" title="Live Data"></span>
                            <button @click.stop="delWatchlist(item.symbol)" class="hidden group-hover:block ml-1 text-red-500 hover:text-red-400">×</button>
                        </div>
                        <div class="text-xs text-gray-500">{{ item.name }}</div>
                    </div>
                    <div class="text-right">"""
html = html.replace(old_wl_item, new_wl_item)

old_wl_header = """<div class="flex justify-between px-4 py-2 text-xs text-gray-500 border-b border-line">
                <span>SYM</span>
                <span>LAST</span>
                <span>CHG%</span>
            </div>"""
new_wl_header = """<div class="flex justify-between px-4 py-2 text-xs text-gray-500 border-b border-line items-center">
                <span>SYM</span>
                <span class="flex-1 text-center">LAST</span>
                <div class="flex items-center gap-2">
                    <span>CHG%</span>
                    <button @click="showAddModal('watchlist')" class="text-blue-400 hover:text-blue-300 ml-1">+</button>
                </div>
            </div>"""
html = html.replace(old_wl_header, new_wl_header)

old_pos_item = """<div class="font-bold text-white flex items-center gap-2">
                            {{ pos.symbol }}
                        </div>
                        <div class="text-xs text-blue-400 font-mono">{{ pos.shares }} 股</div>
                    </div>
                    <div class="text-right">"""
new_pos_item = """<div class="font-bold text-white flex items-center gap-2 group">
                            {{ pos.symbol }}
                            <button @click.stop="delPosition(pos.symbol)" class="hidden group-hover:block ml-1 text-red-500 hover:text-red-400">×</button>
                        </div>
                        <div class="text-xs text-blue-400 font-mono">{{ pos.shares }} 股</div>
                    </div>
                    <div class="text-right">"""
html = html.replace(old_pos_item, new_pos_item)

old_pos_header = """<div class="flex justify-between px-4 py-2 text-xs text-gray-500 border-b border-line">
                <span>SYM</span>
                <span>QTY/AVG</span>
                <span>UNREALIZED</span>
            </div>"""
new_pos_header = """<div class="flex justify-between px-4 py-2 text-xs text-gray-500 border-b border-line items-center">
                <span>SYM</span>
                <span>QTY/AVG</span>
                <div class="flex items-center gap-2">
                    <span>UNREALIZED</span>
                    <button @click="showAddModal('positions')" class="text-blue-400 hover:text-blue-300 ml-1">+</button>
                </div>
            </div>"""
html = html.replace(old_pos_header, new_pos_header)

modal_html = """
    <div v-if="modalType" class="absolute inset-0 z-50 bg-black/70 flex items-center justify-center">
        <div class="bg-gray-800 border border-gray-600 rounded-lg p-6 w-80 shadow-2xl">
            <h2 class="text-white font-bold mb-4">{{ modalType === 'watchlist' ? '加入自選股' : '新增/更新持股' }}</h2>
            <div class="space-y-3">
                <div>
                    <label class="block text-xs text-gray-400 mb-1">股票代號 (Symbol)</label>
                    <input v-model="modalForm.symbol" type="text" class="w-full bg-gray-900 border border-gray-700 text-white px-3 py-2 rounded focus:outline-none focus:border-blue-500" placeholder="e.g. 2330">
                </div>
                <template v-if="modalType === 'watchlist'">
                    <div>
                        <label class="block text-xs text-gray-400 mb-1">名稱 (Name)</label>
                        <input v-model="modalForm.name" type="text" class="w-full bg-gray-900 border border-gray-700 text-white px-3 py-2 rounded focus:outline-none focus:border-blue-500" placeholder="e.g. TSMC">
                    </div>
                    <div>
                        <label class="block text-xs text-gray-400 mb-1">參考價/成本 (Ref Price)</label>
                        <input v-model.number="modalForm.ref_price" type="number" class="w-full bg-gray-900 border border-gray-700 text-white px-3 py-2 rounded focus:outline-none focus:border-blue-500">
                    </div>
                </template>
                <template v-else>
                    <div>
                        <label class="block text-xs text-gray-400 mb-1">股數 (Shares)</label>
                        <input v-model.number="modalForm.shares" type="number" class="w-full bg-gray-900 border border-gray-700 text-white px-3 py-2 rounded focus:outline-none focus:border-blue-500">
                    </div>
                    <div>
                        <label class="block text-xs text-gray-400 mb-1">平均成本 (Avg Cost)</label>
                        <input v-model.number="modalForm.avg_cost" type="number" step="0.01" class="w-full bg-gray-900 border border-gray-700 text-white px-3 py-2 rounded focus:outline-none focus:border-blue-500">
                    </div>
                </template>
            </div>
            <div class="mt-6 flex gap-3">
                <button @click="modalType = null" class="flex-1 bg-gray-700 hover:bg-gray-600 text-white py-2 rounded transition-colors">取消</button>
                <button @click="submitModal" class="flex-1 bg-blue-600 hover:bg-blue-500 text-white py-2 rounded transition-colors font-bold">儲存</button>
            </div>
        </div>
    </div>
"""
html = html.replace('    <!-- 右側邊欄：控制台 -->', modal_html + '\n    <!-- 右側邊欄：控制台 -->')

old_vars_js = "const showBB = ref(false);"
new_vars_js = """const showBB = ref(false);
                const modalType = ref(null); // 'watchlist' or 'positions'
                const modalForm = reactive({ symbol: '', name: '', ref_price: 0, shares: 0, avg_cost: 0 });"""
html = html.replace(old_vars_js, new_vars_js)

old_ret_js = "showVOL, showSMA, showMACD, showRSI, showBB, toggleIndicator,"
new_ret_js = "showVOL, showSMA, showMACD, showRSI, showBB, toggleIndicator, modalType, modalForm, showAddModal, submitModal, delWatchlist, delPosition,"
html = html.replace(old_ret_js, new_ret_js)

js_methods = """
                const showAddModal = (type) => {
                    modalType.value = type;
                    modalForm.symbol = '';
                    modalForm.name = '';
                    modalForm.ref_price = 0;
                    modalForm.shares = 0;
                    modalForm.avg_cost = 0;
                };

                const submitModal = async () => {
                    const endpoint = modalType.value === 'watchlist' ? '/api/watchlist' : '/api/positions';
                    try {
                        const res = await fetch(endpoint, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(modalForm)
                        });
                        const result = await res.json();
                        showToast(result.message, '✅');
                        modalType.value = null;
                        fetchPortfolio();
                    } catch(e) { console.error(e); }
                };

                const delWatchlist = async (symbol) => {
                    try {
                        const res = await fetch(`/api/watchlist/${symbol}`, { method: 'DELETE' });
                        const result = await res.json();
                        showToast(result.message, '🗑️');
                        fetchPortfolio();
                    } catch(e) { console.error(e); }
                };

                const delPosition = async (symbol) => {
                    try {
                        const res = await fetch(`/api/positions/${symbol}`, { method: 'DELETE' });
                        const result = await res.json();
                        showToast(result.message, '🗑️');
                        fetchPortfolio();
                    } catch(e) { console.error(e); }
                };
"""
html = html.replace('const fetchPortfolio = async () => {', js_methods + '\n                const fetchPortfolio = async () => {')

with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'w') as f:
    f.write(html)
