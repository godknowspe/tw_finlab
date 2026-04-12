with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'r') as f:
    html = f.read()

old_code = """if(data && data.length > 0) {
                            candleSeries.setData(data);
                            chart.timeScale().fitContent();
                            
                            // 載入歷史資料後，啟動即時報價 WebSocket
                            connectWebSocket(symbol);
                        }"""

new_code = """if(data && data.length > 0) {
                            candleSeries.setData(data);
                            chart.timeScale().fitContent();
                        } else {
                            candleSeries.setData([]);
                        }
                        connectWebSocket(symbol);"""

html = html.replace(old_code, new_code)

with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'w') as f:
    f.write(html)
