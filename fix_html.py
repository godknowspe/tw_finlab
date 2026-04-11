with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'r') as f:
    html = f.read()

old_init = "chart = LightweightCharts.createChart(container, {"
new_init = """chart = LightweightCharts.createChart(container, {
                        width: container.clientWidth || 800,
                        height: container.clientHeight || 600,
                        autoSize: true,"""

html = html.replace(old_init, new_init)

with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'w') as f:
    f.write(html)
