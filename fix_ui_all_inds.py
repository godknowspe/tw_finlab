with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'r') as f:
    html = f.read()

old_btn = """<button @click="toggleIndicator('macd')" :class="showMACD ? 'bg-orange-900 text-orange-300 border-orange-700' : 'bg-gray-800 text-gray-500 border-gray-700'" class="px-2 py-0.5 text-xs rounded border transition-colors">MACD</button>"""
new_btn = """<button @click="toggleIndicator('macd')" :class="showMACD ? 'bg-orange-900 text-orange-300 border-orange-700' : 'bg-gray-800 text-gray-500 border-gray-700'" class="px-2 py-0.5 text-xs rounded border transition-colors">MACD</button>
                    <button @click="toggleIndicator('rsi')" :class="showRSI ? 'bg-pink-900 text-pink-300 border-pink-700' : 'bg-gray-800 text-gray-500 border-gray-700'" class="px-2 py-0.5 text-xs rounded border transition-colors">RSI</button>
                    <button @click="toggleIndicator('bb')" :class="showBB ? 'bg-cyan-900 text-cyan-300 border-cyan-700' : 'bg-gray-800 text-gray-500 border-gray-700'" class="px-2 py-0.5 text-xs rounded border transition-colors">BB</button>"""
html = html.replace(old_btn, new_btn)

old_vars = "const showMACD = ref(false);"
new_vars = """const showMACD = ref(false);
                let rsiSeries = null;
                let bbUpSeries = null;
                let bbMidSeries = null;
                let bbLowSeries = null;
                const showRSI = ref(false);
                const showBB = ref(false);"""
html = html.replace(old_vars, new_vars)

old_ret = "showVOL, showSMA, showMACD, toggleIndicator,"
new_ret = "showVOL, showSMA, showMACD, showRSI, showBB, toggleIndicator,"
html = html.replace(old_ret, new_ret)

old_init_end = """chart.priceScale('macd').applyOptions({
                        scaleMargins: {
                            top: 0.8, // leave top 80% for candles
                            bottom: 0,
                        },
                    });

                    window.addEventListener('resize'"""
new_init_end = """chart.priceScale('macd').applyOptions({
                        scaleMargins: { top: 0.8, bottom: 0 },
                    });
                    
                    rsiSeries = chart.addLineSeries({
                        color: '#ec4899', // pink-500
                        lineWidth: 2,
                        priceScaleId: 'rsi',
                        visible: false,
                    });
                    chart.priceScale('rsi').applyOptions({
                        scaleMargins: { top: 0.8, bottom: 0 },
                    });
                    
                    bbUpSeries = chart.addLineSeries({ color: 'rgba(6, 182, 212, 0.6)', lineWidth: 1, lineStyle: 2, visible: false });
                    bbMidSeries = chart.addLineSeries({ color: 'rgba(6, 182, 212, 0.6)', lineWidth: 1, visible: false });
                    bbLowSeries = chart.addLineSeries({ color: 'rgba(6, 182, 212, 0.6)', lineWidth: 1, lineStyle: 2, visible: false });

                    window.addEventListener('resize'"""
html = html.replace(old_init_end, new_init_end)

old_data_arrays = "const volData = [];"
new_data_arrays = """const volData = [];
                            const rsiData = [];
                            const bbUpData = [];
                            const bbMidData = [];
                            const bbLowData = [];"""
html = html.replace(old_data_arrays, new_data_arrays)

old_loop_end = """if(d.value !== null) volData.push({
                                    time: d.time,
                                    value: d.value,
                                    color: d.close >= d.open ? 'rgba(63, 185, 80, 0.4)' : 'rgba(248, 81, 73, 0.4)'
                                });
                            });"""
new_loop_end = """if(d.value !== null) volData.push({
                                    time: d.time,
                                    value: d.value,
                                    color: d.close >= d.open ? 'rgba(63, 185, 80, 0.4)' : 'rgba(248, 81, 73, 0.4)'
                                });
                                if(d.rsi !== null) rsiData.push({ time: d.time, value: d.rsi });
                                if(d.bb_up !== null) bbUpData.push({ time: d.time, value: d.bb_up });
                                if(d.bb_mid !== null) bbMidData.push({ time: d.time, value: d.bb_mid });
                                if(d.bb_low !== null) bbLowData.push({ time: d.time, value: d.bb_low });
                            });"""
html = html.replace(old_loop_end, new_loop_end)

old_set_data = """volumeSeries.setData(volData);
                            smaSeries.setData(smaData);"""
new_set_data = """volumeSeries.setData(volData);
                            smaSeries.setData(smaData);
                            rsiSeries.setData(rsiData);
                            bbUpSeries.setData(bbUpData);
                            bbMidSeries.setData(bbMidData);
                            bbLowSeries.setData(bbLowData);"""
html = html.replace(old_set_data, new_set_data)

old_toggle_start = "} else if (type === 'macd') {"
new_toggle_start = """} else if (type === 'rsi') {
                        showRSI.value = !showRSI.value;
                        rsiSeries.applyOptions({ visible: showRSI.value });
                        updatePanes();
                    } else if (type === 'bb') {
                        showBB.value = !showBB.value;
                        bbUpSeries.applyOptions({ visible: showBB.value });
                        bbMidSeries.applyOptions({ visible: showBB.value });
                        bbLowSeries.applyOptions({ visible: showBB.value });
                    } else if (type === 'macd') {"""
html = html.replace(old_toggle_start, new_toggle_start)

old_macd_panes = """histogramSeries.applyOptions({ visible: showMACD.value });
                        
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
                };"""

new_macd_panes = """histogramSeries.applyOptions({ visible: showMACD.value });
                        updatePanes();
                    }
                };

                const updatePanes = () => {
                    let bottomCount = 0;
                    if (showMACD.value) bottomCount++;
                    if (showRSI.value) bottomCount++;
                    
                    if (bottomCount === 0) {
                        chart.priceScale('right').applyOptions({ scaleMargins: { top: 0.1, bottom: 0.1 } });
                    } else if (bottomCount === 1) {
                        chart.priceScale('right').applyOptions({ scaleMargins: { top: 0.1, bottom: 0.3 } });
                        if (showMACD.value) chart.priceScale('macd').applyOptions({ scaleMargins: { top: 0.75, bottom: 0 } });
                        if (showRSI.value) chart.priceScale('rsi').applyOptions({ scaleMargins: { top: 0.75, bottom: 0 } });
                    } else {
                        chart.priceScale('right').applyOptions({ scaleMargins: { top: 0.1, bottom: 0.45 } });
                        if (showMACD.value) chart.priceScale('macd').applyOptions({ scaleMargins: { top: 0.6, bottom: 0.22 } });
                        if (showRSI.value) chart.priceScale('rsi').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
                    }
                };"""
html = html.replace(old_macd_panes, new_macd_panes)

old_vis_hide = """volumeSeries.applyOptions({ visible: false });
                        smaSeries.applyOptions({ visible: false });"""
new_vis_hide = """volumeSeries.applyOptions({ visible: false });
                        smaSeries.applyOptions({ visible: false });
                        rsiSeries.applyOptions({ visible: false });
                        bbUpSeries.applyOptions({ visible: false });
                        bbMidSeries.applyOptions({ visible: false });
                        bbLowSeries.applyOptions({ visible: false });"""
html = html.replace(old_vis_hide, new_vis_hide)

old_vis_show = """if(showVOL.value) volumeSeries.applyOptions({ visible: true });
                        if(showSMA.value) smaSeries.applyOptions({ visible: true });"""
new_vis_show = """if(showVOL.value) volumeSeries.applyOptions({ visible: true });
                        if(showSMA.value) smaSeries.applyOptions({ visible: true });
                        if(showRSI.value) rsiSeries.applyOptions({ visible: true });
                        if(showBB.value) {
                            bbUpSeries.applyOptions({ visible: true });
                            bbMidSeries.applyOptions({ visible: true });
                            bbLowSeries.applyOptions({ visible: true });
                        }"""
html = html.replace(old_vis_show, new_vis_show)

with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'w') as f:
    f.write(html)
