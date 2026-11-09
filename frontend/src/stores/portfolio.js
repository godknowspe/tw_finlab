import { defineStore } from 'pinia';
import axios from 'axios';

export const apiError = (e) => e.response?.data?.detail || e.message;

export const usePortfolioStore = defineStore('portfolio', {
  state: () => ({
    positions: [],
    trades: [],
    summary: {},
    sync: {},
  }),
  actions: {
    async fetchPortfolio() {
      try {
        const res = await axios.get('/api/portfolio');
        this.positions = res.data.positions;
        this.trades = res.data.trades;
        this.summary = res.data.summary;
        this.sync = res.data.sync || {};
        return res.data;
      } catch (error) {
        console.error('Failed to fetch portfolio:', error);
      }
    },
    async addTrade(trade) {
      await axios.post('/api/trades', trade);
      await this.fetchPortfolio();
    },
    async deleteTrade(tradeId) {
      await axios.delete(`/api/trades/${tradeId}`);
      await this.fetchPortfolio();
    },
    async syncTrades() {
      const res = await axios.post('/api/sync/trades');
      await this.fetchPortfolio();
      return res.data;
    }
  }
});
