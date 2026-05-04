import { defineStore } from 'pinia';
import axios from 'axios';

export const usePortfolioStore = defineStore('portfolio', {
  state: () => ({
    positions: [],
    trades: [],
    summary: {},
    agentState: {},
    settings: {
      take_profit_pct: 10,
      stop_loss_pct: 5
    }
  }),
  actions: {
    async fetchPortfolio() {
      try {
        const res = await axios.get('/api/portfolio');
        this.positions = res.data.positions;
        this.trades = res.data.trades;
        this.summary = res.data.summary;
        this.agentState = res.data.agent_state;
        this.settings = res.data.settings;
      } catch (error) {
        console.error('Failed to fetch portfolio:', error);
      }
    },
    async updateSettings(newSettings) {
      this.settings = { ...this.settings, ...newSettings };
    },
    
    async addTrade(trade) {
      try {
        await axios.post('/api/trades', trade);
        await this.fetchPortfolio();
      } catch (error) {
        console.error('Failed to add trade:', error);
        throw error;
      }
    },
    async deleteTrade(tradeId) {

      try {
        await axios.delete(`/api/trades/${tradeId}`);
        await this.fetchPortfolio();
      } catch (error) {
        console.error('Failed to delete trade:', error);
      }
    },
    async syncTrades() {
      try {
        const res = await axios.post('/api/sync/trades');
        await this.fetchPortfolio();
        return res.data;
      } catch (error) {
        console.error('Failed to sync trades:', error);
        throw error;
      }
    }
  }
});
