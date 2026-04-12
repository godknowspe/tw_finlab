with open('/Users/godknows/code/tw_finlab/src/web/server.py', 'r') as f:
    content = f.read()

old_pos = """        "positions": [
            {"symbol": "2330", "shares": 1000, "avg_cost": 750.00, "unrealized": 55500}
        ],"""

new_pos = """        "positions": [
            {"symbol": "2330", "shares": 2000, "avg_cost": 1850.00, "unrealized": 300000},
            {"symbol": "2317", "shares": 5000, "avg_cost": 140.50, "unrealized": -100000}
        ],"""

content = content.replace(old_pos, new_pos)

with open('/Users/godknows/code/tw_finlab/src/web/server.py', 'w') as f:
    f.write(content)
