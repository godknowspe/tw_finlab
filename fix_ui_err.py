with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'r') as f:
    html = f.read()

new_catch = "} catch(e) { console.error(e); showToast('Chart Error: ' + e.message, '❌'); }"
html = html.replace("} catch(e) { console.error(e); }", new_catch)

with open('/Users/godknows/code/tw_finlab/src/web/static/index.html', 'w') as f:
    f.write(html)
