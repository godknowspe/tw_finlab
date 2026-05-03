import { defineStore } from 'pinia';
import axios from 'axios';

export const useMarketStore = defineStore('market', {
  state: () => ({
    watchlist: [],
    currentSymbol: '',
    currentInterval: '1d',
    wsConnected: false,
  }),
  actions: {
    async fetchWatchlist() {
      try {
        const res = await axios.get('/api/portfolio');
        this.watchlist = res.data.watchlist;
      } catch (error) {
        console.error('Failed to fetch watchlist:', error);
      }
    },
    setCurrentSymbol(symbol) {
      this.currentSymbol = symbol;
    },
    connectWebSocket() {
      console.log('WS Connection Logic Placeholder');
    }
  }
});
