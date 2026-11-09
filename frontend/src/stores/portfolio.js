import { defineStore } from 'pinia';
import axios from 'axios';

export const apiError = (e) => e.response?.data?.detail || e.message;

export const usePortfolioStore = defineStore('portfolio', {
  state: () => ({
    positions: [],
    trades: [],
    summary: {},
    sync: {},
    revision: null,
  }),
  actions: {
    async fetchPortfolio() {
      try {
        const res = await axios.get('/api/portfolio');
        this.positions = res.data.positions;
        this.trades = res.data.trades;
        this.summary = res.data.summary;
        this.sync = res.data.sync || {};
        this.revision = res.data.revision;
        return res.data;
      } catch (error) {
        console.error('Failed to fetch portfolio:', error);
      }
    },
    async addTrade(trade) {
      await axios.post('/api/trades', trade);
      await this.fetchPortfolio();
    },
    async deleteTrade(uid) {
      await axios.delete(`/api/trades/${encodeURIComponent(uid)}`);
      await this.fetchPortfolio();
    },
    async pollRevision() {
      // Returns true when the server state changed since the last fetch (e.g. another host synced).
      try {
        const res = await axios.get('/api/revision');
        this.sync = res.data.sync || {};
        return this.revision !== null && res.data.revision !== this.revision;
      } catch (e) {
        return false;
      }
    },
    async syncTrades() {
      const res = await axios.post('/api/sync/trades');
      await this.fetchPortfolio();
      return res.data;
    }
  }
});
