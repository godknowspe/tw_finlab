import { defineStore } from 'pinia';
import axios from 'axios';

export const usePortfolioStore = defineStore('portfolio', {
  state: () => ({
    positions: [],
    trades: [],
    summary: {},
    agentState: {},
    settings: { take_profit_pct: 10, stop_loss_pct: 5 }
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
    }
  }
});
