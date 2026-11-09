import { defineStore } from 'pinia';
import axios from 'axios';
import { usePortfolioStore } from './portfolio';

let backtestGeneration = 0;

export const useMarketStore = defineStore('market', {
  state: () => ({
    watchlist: [],
    currentSymbol: '',
    currentInterval: '1d',
    wsConnected: false,
    ws: null,
    selectedIndicators: ['SMA20'],
    backtestResults: null,
    isBacktesting: false,
    backtestEnabled: false,
    selectedStrategy: 'RSI'
  }),
  getters: {
    watchlistTW: (state) => state.watchlist.filter(i => i.market === 'TW'),
    watchlistUS: (state) => state.watchlist.filter(i => i.market === 'US'),
  },
  actions: {
    async addToWatchlist(symbol) {
      await axios.post('/api/watchlist', { symbol, name: '' });
      await this.fetchWatchlist();
    },
    async removeFromWatchlist(symbol) {
      await axios.delete(`/api/watchlist/${encodeURIComponent(symbol)}`);
      await this.fetchWatchlist();
    },
    async fetchWatchlist() {
      // /api/portfolio carries both the watchlist and the portfolio; fetch it once for both stores.
      const data = await usePortfolioStore().fetchPortfolio();
      if (!data) return;
      this.watchlist = data.watchlist.map(item => ({ ...item, flashClass: '' }));
      if (!this.currentSymbol && this.watchlist.length > 0) {
        this.currentSymbol = this.watchlist[0].symbol;
      }
    },
    setCurrentSymbol(symbol) {
      this.currentSymbol = symbol;
      this.clearBacktest();
    },
    clearBacktest() {
      backtestGeneration++;
      this.backtestResults = null;
      this.backtestEnabled = false;
      this.isBacktesting = false;
    },
    async runBacktest() {
      if (!this.currentSymbol) return;
      const request = { symbol: this.currentSymbol, interval: this.currentInterval, strategy: this.selectedStrategy };
      const generation = ++backtestGeneration;
      this.isBacktesting = true;
      try {
        const res = await axios.get(`/api/backtest/${encodeURIComponent(request.symbol)}`, {
          params: { strategies: request.strategy, interval: request.interval }
        });
        // Drop the result if the user switched symbol/interval/strategy while it ran.
        if (generation !== backtestGeneration) return;
        this.backtestResults = res.data[request.strategy] || null;
        this.backtestEnabled = !!this.backtestResults;
      } catch (e) {
        if (generation === backtestGeneration) alert('Backtest failed: ' + (e.response?.data?.detail || e.message));
      } finally {
        if (generation === backtestGeneration) this.isBacktesting = false;
      }
    },
    toggleIndicator(name) {
      const idx = this.selectedIndicators.indexOf(name);
      if (idx === -1) this.selectedIndicators.push(name);
      else this.selectedIndicators.splice(idx, 1);
    },
    connectWebSocket() {
      if (this.ws) return;
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      this.ws = new WebSocket(`${protocol}//${window.location.host}/api/ws/watchlist`);
      this.ws.onopen = () => { this.wsConnected = true; };
      this.ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.type !== 'updates') return;
        payload.data.forEach(data => {
          const item = this.watchlist.find(i => i.symbol === data.symbol);
          if (!item) return;
          item.last = data.price;
          if (item.ref_price > 0) {
            const pct = ((data.price - item.ref_price) / item.ref_price) * 100;
            item.chg_pct = (pct > 0 ? '+' : '') + pct.toFixed(2) + '%';
          }
          item.flashClass = 'flash-green';
          setTimeout(() => { item.flashClass = ''; }, 500);
        });
      };
      this.ws.onclose = () => {
        this.wsConnected = false;
        this.ws = null;
        setTimeout(() => this.connectWebSocket(), 5000);
      };
    }
  }
});
