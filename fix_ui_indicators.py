import re

with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'r') as f:
    html = f.read()

# 1. Add toggle for indicators in Top Bar
old_top_bar = """<span v-if="chartMode === 'symbol'" class="text-gray-400">| 1D</span>"""
new_top_bar = """<span v-if="chartMode === 'symbol'" class="text-gray-400">| 1D</span>
                <div v-if="chartMode === 'symbol'" class="flex gap-2 ml-4">
                    <button @click="toggleIndicator('sma')" :class="showSMA ? 'bg-purple-900 text-purple-300 border-purple-700' : 'bg-gray-800 text-gray-500 border-gray-700'" class="px-2 py-0.5 text-xs rounded border transition-colors">SMA20</button>
                    <button @click="toggleIndicator('macd')" :class="showMACD ? 'bg-orange-900 text-orange-300 border-orange-700' : 'bg-gray-800 text-gray-500 border-gray-700'" class="px-2 py-0.5 text-xs rounded border transition-colors">MACD</button>
                </div>"""
html = html.replace(old_top_bar, new_top_bar)

# 2. Add variables for indicators
old_vars = """let candleSeries = null;
                let areaSeries = null;"""
new_vars = """let candleSeries = null;
                let areaSeries = null;
                let smaSeries = null;
                let macdSeries = null;
                let signalSeries = null;
                let histogramSeries = null;
                const showSMA = ref(false);
                const showMACD = ref(false);"""
html = html.replace(old_vars, new_vars)

old_return = "activeTab, chartMode, equityValue, switchMode,"
new_return = "activeTab, chartMode, equityValue, switchMode, showSMA, showMACD, toggleIndicator,"
html = html.replace(old_return, new_return)

# 3. Initialize indicator series in initChart
old_init_end = """areaSeries.applyOptions({ visible: false });

                    window.addEventListener('resize'"""
new_init_end = """areaSeries.applyOptions({ visible: false });
                    
                    smaSeries = chart.addLineSeries({
                        color: '#c084fc', // purple-400
                        lineWidth: 2,
                        visible: false,
                    });
                    
                    // Create MACD pane (bottom)
                    histogramSeries = chart.addHistogramSeries({
                        color: '#f97316',
                        priceFormat: { type: 'volume' },
                        priceScaleId: 'macd',
                        visible: false,
                    });
                    macdSeries = chart.addLineSeries({
                        color: '#fb923c', // orange-400
                        lineWidth: 2,
                        priceScaleId: 'macd',
                        visible: false,
                    });
                    signalSeries = chart.addLineSeries({
                        color: '#60a5fa', // blue-400
                        lineWidth: 2,
                        priceScaleId: 'macd',
                        visible: false,
                    });
                    
                    chart.priceScale('macd').applyOptions({
                        scaleMargins: {
                            top: 0.8, // leave top 80% for candles
                            bottom: 0,
                        },
                    });

                    window.addEventListener('resize'"""
html = html.replace(old_init_end, new_init_end)

# 4. Set data for indicators in loadChart
old_load_set = """if(data && data.length > 0) {
                            candleSeries.setData(data);
                            chart.timeScale().fitContent();
                        } else {"""
new_load_set = """if(data && data.length > 0) {
                            candleSeries.setData(data);
                            
                            // 準備指標資料
                            const smaData = [];
                            const macdData = [];
                            const signalData = [];
                            const histData = [];
                            
                            data.forEach(d => {
                                if(d.sma20 !== null) smaData.push({ time: d.time, value: d.sma20 });
                                if(d.macd !== null) macdData.push({ time: d.time, value: d.macd });
                                if(d.signal !== null) signalData.push({ time: d.time, value: d.signal });
                                if(d.histogram !== null) histData.push({ 
                                    time: d.time, 
                                    value: d.histogram, 
                                    color: d.histogram >= 0 ? 'rgba(63, 185, 80, 0.5)' : 'rgba(248, 81, 73, 0.5)'
                                });
                            });
                            
                            smaSeries.setData(smaData);
                            macdSeries.setData(macdData);
                            signalSeries.setData(signalData);
                            histogramSeries.setData(histData);
                            
                            chart.timeScale().fitContent();
                        } else {"""
html = html.replace(old_load_set, new_load_set)

# 5. Add toggleIndicator function
toggle_func = """
                const toggleIndicator = (type) => {
                    if (type === 'sma') {
                        showSMA.value = !showSMA.value;
                        smaSeries.applyOptions({ visible: showSMA.value });
                    } else if (type === 'macd') {
                        showMACD.value = !showMACD.value;
                        macdSeries.applyOptions({ visible: showMACD.value });
                        signalSeries.applyOptions({ visible: showMACD.value });
                        histogramSeries.applyOptions({ visible: showMACD.value });
                        
                        // 調整主圖比例
                        if (showMACD.value) {
                            chart.priceScale('right').applyOptions({
                                scaleMargins: { top: 0.1, bottom: 0.25 },
                            });
                        } else {
                            chart.priceScale('right').applyOptions({
                                scaleMargins: { top: 0.1, bottom: 0.1 },
                            });
                        }
                    }
                };
"""
html = html.replace('const loadChart = async', toggle_func + '\n                const loadChart = async')

# 6. Hide indicators when switching to Equity mode
old_switch = """candleSeries.applyOptions({ visible: false });
                        areaSeries.applyOptions({ visible: true });"""
new_switch = """candleSeries.applyOptions({ visible: false });
                        smaSeries.applyOptions({ visible: false });
                        macdSeries.applyOptions({ visible: false });
                        signalSeries.applyOptions({ visible: false });
                        histogramSeries.applyOptions({ visible: false });
                        areaSeries.applyOptions({ visible: true });"""
html = html.replace(old_switch, new_switch)

# 7. Restore indicators when switching to Symbol mode
old_switch_sym = """areaSeries.applyOptions({ visible: false });
                        candleSeries.applyOptions({ visible: true });"""
new_switch_sym = """areaSeries.applyOptions({ visible: false });
                        candleSeries.applyOptions({ visible: true });
                        if(showSMA.value) smaSeries.applyOptions({ visible: true });
                        if(showMACD.value) {
                            macdSeries.applyOptions({ visible: true });
                            signalSeries.applyOptions({ visible: true });
                            histogramSeries.applyOptions({ visible: true });
                        }"""
html = html.replace(old_switch_sym, new_switch_sym)

with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'w') as f:
    f.write(html)
