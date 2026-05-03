import { defineStore } from 'pinia';
import axios from 'axios';

export const useMarketStore = defineStore('market', {
  state: () => ({
    watchlist: [],
    currentSymbol: '',
    currentInterval: '1d',
    wsConnected: false,
    ws: null,
    // New states
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
    async fetchWatchlist() {
      try {
        const res = await axios.get('/api/portfolio');
        this.watchlist = res.data.watchlist.map(item => ({
          ...item,
          flashClass: ''
        }));
        if (!this.currentSymbol && this.watchlist.length > 0) {
          this.currentSymbol = this.watchlist[0].symbol;
        }
      } catch (error) {
        console.error('Failed to fetch watchlist:', error);
      }
    },
    setCurrentSymbol(symbol) {
      this.currentSymbol = symbol;
      // Clear backtest results when changing symbol to avoid confusion
      this.backtestResults = null;
    },
    async runBacktest() {
      if (!this.currentSymbol) return;
      this.isBacktesting = true;
      try {
        const res = await axios.get(`/api/backtest/${this.currentSymbol}`, {
          params: {
            strategies: this.selectedStrategy,
            interval: this.currentInterval
          }
        });
        this.backtestResults = res.data[this.selectedStrategy];
        this.backtestEnabled = true;
      } catch (e) {
        console.error('Backtest failed:', e);
      } finally {
        this.isBacktesting = false;
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
      const wsUrl = `${protocol}//${window.location.host}/api/ws/watchlist`;
      this.ws = new WebSocket(wsUrl);
      this.ws.onopen = () => { this.wsConnected = true; };
      this.ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.type === 'updates') {
          payload.data.forEach(data => {
            const watchItem = this.watchlist.find(i => i.symbol === data.symbol);
            if (watchItem) {
              watchItem.last = data.price;
              watchItem.flashClass = 'flash-green';
              setTimeout(() => { watchItem.flashClass = ''; }, 500);
            }
          });
        }
      };
      this.ws.onclose = () => {
        this.wsConnected = false;
        this.ws = null;
        setTimeout(() => this.connectWebSocket(), 5000);
      };
    }
  }
});
