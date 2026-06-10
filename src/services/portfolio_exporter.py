import os
import json
import base64
import requests
from loguru import logger
from src.services.portfolio_service import PortfolioService

def trigger_portfolio_export(app_state: dict):
    """
    Recalculates positions and exports them to local/cloud destinations
    based on app settings and environment variables.
    """
    try:
        logger.info("Starting portfolio export calculation...")
        
        # 1. Initialize PortfolioService with current cash settings
        cash_twd = app_state.get("cash", {}).get("TWD", 1000000.0)
        cash_usd = app_state.get("cash", {}).get("USD", 50000.0)
        usd_twd_rate = app_state.get("settings", {}).get("usd_twd_rate", 32.5)
        
        portfolio_service = PortfolioService(
            initial_cash_twd=cash_twd,
            initial_cash_usd=cash_usd,
            usd_twd_rate=usd_twd_rate
        )
        
        # 2. Calculate current positions from trades
        trades = app_state.get("trades", [])
        port_data = portfolio_service.calculate_positions(trades)
        positions = port_data.get("positions", {})
        
        # 3. Format holdings to match portfolio_notify.py's portfolio.json structure
        portfolio_list = []
        for sym, pos in positions.items():
            shares = pos.get("shares", 0.0)
            # Only export symbols with active holdings
            if shares <= 0:
                continue
                
            is_tw = pos.get("currency") == "TWD" or sym.isdigit()
            symbol = f"{sym}.TW" if (is_tw and not sym.endswith(".TW")) else sym
            market = "TW" if is_tw else "US"
            
            portfolio_list.append({
                "symbol": symbol,
                "market": market,
                "quantity": int(shares),
                "cost_basis": round(pos.get("avg_cost", 0.0), 2)
            })
            
        portfolio_json = {"portfolio": portfolio_list}
        logger.info(f"Calculated {len(portfolio_list)} active holdings for export.")
        
        # 4. Resolve configurations (settings or environment variables)
        export_config = app_state.get("settings", {}).get("portfolio_export", {})
        
        # Methods config (list of strings, e.g. ["local", "gist"])
        methods_env = os.environ.get("PORTFOLIO_EXPORT_METHODS")
        if methods_env:
            methods = [m.strip() for m in methods_env.split(",") if m.strip()]
        else:
            methods = export_config.get("methods", ["local"])
            
        github_token = os.environ.get("PORTFOLIO_EXPORT_GITHUB_TOKEN") or export_config.get("github_token")
        gist_id = os.environ.get("PORTFOLIO_EXPORT_GIST_ID") or export_config.get("gist_id")
        github_repo = os.environ.get("PORTFOLIO_EXPORT_GITHUB_REPO") or export_config.get("github_repo", "godknowspe/openclaw-workspace")
        github_path = os.environ.get("PORTFOLIO_EXPORT_GITHUB_PATH") or export_config.get("github_path", "portfolio.json")
        local_path = os.environ.get("PORTFOLIO_EXPORT_LOCAL_PATH") or export_config.get("local_path") or "/Users/godknows/.openclaw/workspace/portfolio.json"
        
        # 5. Execute each requested export method
        for method in methods:
            if method == "local":
                _export_local(portfolio_json, local_path)
            elif method == "gist":
                _export_gist(portfolio_json, gist_id, github_token)
            elif method == "github_repo":
                _export_github_repo(portfolio_json, github_repo, github_path, github_token)
            else:
                logger.warning(f"Unknown portfolio export method: {method}")
                
    except Exception as e:
        logger.error(f"Error executing portfolio export: {e}")

def _export_local(portfolio_json: dict, path: str):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_path = path + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(portfolio_json, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
        logger.info(f"Successfully exported portfolio locally to {path}")
    except Exception as e:
        logger.error(f"Local export failed: {e}")

def _export_gist(portfolio_json: dict, gist_id: str, token: str):
    if not gist_id or not token:
        logger.warning("Skipping Gist export: Gist ID or GitHub token is not configured.")
        return
    try:
        url = f"https://api.github.com/gists/{gist_id}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        payload = {
            "files": {
                "portfolio.json": {
                    "content": json.dumps(portfolio_json, indent=2, ensure_ascii=False)
                }
            }
        }
        resp = requests.patch(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        logger.info(f"Successfully exported portfolio to GitHub Gist {gist_id}")
    except Exception as e:
        logger.error(f"Gist export failed: {e}")

def _export_github_repo(portfolio_json: dict, repo: str, path: str, token: str):
    if not repo or not token:
        logger.warning("Skipping GitHub Repo export: Repo or GitHub token is not configured.")
        return
    try:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Get SHA of existing file if it exists (needed for updates)
        sha = None
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            sha = resp.json().get("sha")
        elif resp.status_code != 404:
            resp.raise_for_status()
            
        content_str = json.dumps(portfolio_json, indent=2, ensure_ascii=False)
        content_bytes = content_str.encode("utf-8")
        content_b64 = base64.b64encode(content_bytes).decode("utf-8")
        
        payload = {
            "message": "Automated update of portfolio holdings from tw_finlab",
            "content": content_b64
        }
        if sha:
            payload["sha"] = sha
            
        put_resp = requests.put(url, json=payload, headers=headers, timeout=10)
        put_resp.raise_for_status()
        logger.info(f"Successfully exported portfolio to GitHub Repository {repo}/{path}")
    except Exception as e:
        logger.error(f"GitHub Repository export failed: {e}")
