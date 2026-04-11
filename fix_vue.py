with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'r') as f:
    html = f.read()

# Fix 1: Move <script> tags outside of the Vue app mount element #app
# Currently body is #app, which wraps the whole script. Vue 3 compiler hates this.
html = html.replace('<body id="app" class="flex h-screen font-sans text-sm">', '<body class="flex h-screen font-sans text-sm">\n<div id="app" class="flex w-full h-full">')
html = html.replace('    <script>\n        const { createApp', '</div>\n\n    <script>\n        const { createApp')

# Fix 2: LightweightCharts breaking change fix. Use v3.8.0.
html = html.replace('unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js', 'unpkg.com/lightweight-charts@3.8.0/dist/lightweight-charts.standalone.production.js')

with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'w') as f:
    f.write(html)
