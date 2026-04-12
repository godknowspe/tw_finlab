with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'r') as f:
    html = f.read()

old_trade_fields = """<div>
                        <label class="block text-xs text-gray-400 mb-1">成交單價 (Price)</label>
                        <input v-model.number="modalForm.price" type="number" step="0.01" class="w-full bg-gray-900 border border-gray-700 text-white px-3 py-2 rounded focus:outline-none focus:border-blue-500">
                    </div>
                </template>"""

new_trade_fields = """<div>
                        <label class="block text-xs text-gray-400 mb-1">成交單價 (Price)</label>
                        <input v-model.number="modalForm.price" type="number" step="0.01" class="w-full bg-gray-900 border border-gray-700 text-white px-3 py-2 rounded focus:outline-none focus:border-blue-500">
                    </div>
                    <div>
                        <label class="block text-xs text-gray-400 mb-1">成交時間 (Time)</label>
                        <!-- 使用 color-scheme:dark 讓原生日曆選單變黑底 -->
                        <input v-model="modalForm.timestamp" type="datetime-local" class="w-full bg-gray-900 border border-gray-700 text-white px-3 py-2 rounded focus:outline-none focus:border-blue-500 [color-scheme:dark]">
                    </div>
                </template>"""
html = html.replace(old_trade_fields, new_trade_fields)

old_form = "const modalForm = reactive({ symbol: '', name: '', ref_price: 0, action: 'BUY', shares: 0, price: 0 });"
new_form = "const modalForm = reactive({ symbol: '', name: '', ref_price: 0, action: 'BUY', shares: 0, price: 0, timestamp: '' });"
html = html.replace(old_form, new_form)

old_show_modal = """modalForm.shares = 0;
                    modalForm.price = 0;
                    modalForm.action = 'BUY';"""

new_show_modal = """modalForm.shares = 0;
                    modalForm.price = 0;
                    modalForm.action = 'BUY';
                    
                    const now = new Date();
                    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
                    modalForm.timestamp = now.toISOString().slice(0,16);"""
html = html.replace(old_show_modal, new_show_modal)

old_time_display = """<div class="text-xs text-gray-500 font-mono">{{ trade.timestamp.split('T')[0] }}</div>"""
new_time_display = """<div class="text-xs text-gray-500 font-mono">{{ trade.timestamp.substring(5, 16).replace('T', ' ') }}</div>"""
html = html.replace(old_time_display, new_time_display)

with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'w') as f:
    f.write(html)
