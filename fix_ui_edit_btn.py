with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'r') as f:
    html = f.read()

old_wl_item = """<button @click.stop="delWatchlist(item.symbol)" class="hidden group-hover:block ml-1 text-red-500 hover:text-red-400">×</button>
                        </div>"""
new_wl_item = """<button @click.stop="editWatchlist(item)" class="hidden group-hover:block ml-1 text-blue-400 hover:text-blue-300">✎</button>
                            <button @click.stop="delWatchlist(item.symbol)" class="hidden group-hover:block ml-1 text-red-500 hover:text-red-400">×</button>
                        </div>"""
html = html.replace(old_wl_item, new_wl_item)

old_pos_item = """<button @click.stop="delPosition(pos.symbol)" class="hidden group-hover:block ml-1 text-red-500 hover:text-red-400">×</button>
                        </div>"""
new_pos_item = """<button @click.stop="editPosition(pos)" class="hidden group-hover:block ml-1 text-blue-400 hover:text-blue-300">✎</button>
                            <button @click.stop="delPosition(pos.symbol)" class="hidden group-hover:block ml-1 text-red-500 hover:text-red-400">×</button>
                        </div>"""
html = html.replace(old_pos_item, new_pos_item)

old_js = """const delWatchlist = async (symbol) => {"""
new_js = """const editWatchlist = (item) => {
                    modalType.value = 'watchlist';
                    modalForm.symbol = item.symbol;
                    modalForm.name = item.name;
                    modalForm.ref_price = item.ref_price;
                };

                const editPosition = (pos) => {
                    modalType.value = 'positions';
                    modalForm.symbol = pos.symbol;
                    modalForm.shares = pos.shares;
                    modalForm.avg_cost = pos.avg_cost;
                };

                const delWatchlist = async (symbol) => {"""
html = html.replace(old_js, new_js)

old_ret = "submitModal, delWatchlist, delPosition,"
new_ret = "submitModal, editWatchlist, editPosition, delWatchlist, delPosition,"
html = html.replace(old_ret, new_ret)

with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'w') as f:
    f.write(html)
