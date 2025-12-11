import { RiskDashboardSpec } from '@/components/risk-dashboard/types';

export const riskDashboardMock: RiskDashboardSpec = {
  metadata: {
    as_of: '2025-12-11T10:00:00Z',
    scenario_type: 'portfolio_risk_basic',
    base_currency: 'RUB',
    portfolio_id: 'demo-portfolio-001',
  },
  metrics: [
    {
      id: 'portfolio_total_return_pct',
      label: 'Доходность портфеля за период',
      value: 11.63,
      unit: '%',
      severity: 'info',
      change: 1.2,
    },
    {
      id: 'portfolio_var_light',
      label: 'Var_light (95%, 1д)',
      value: 4.47,
      unit: '%',
      severity: 'medium',
      change: 0.4,
    },
    {
      id: 'portfolio_annualized_volatility_pct',
      label: 'Годовая волатильность',
      value: 18.2,
      unit: '%',
      severity: 'low',
    },
    {
      id: 'top1_weight_pct',
      label: 'Концентрация Top-1',
      value: 15.2,
      unit: '%',
      severity: 'high',
    },
    {
      id: 'portfolio_max_drawdown_pct',
      label: 'Макс. просадка',
      value: -9.8,
      unit: '%',
      severity: 'info',
    },
  ],
  charts: [
    {
      id: 'equity_curve',
      type: 'line',
      title: 'Динамика стоимости портфеля',
      x_axis: { field: 'date', label: 'Дата' },
      y_axis: { field: 'value', label: 'Стоимость, млн ₽' },
      series: [
        {
          id: 'portfolio',
          label: 'Портфель',
          data_ref: 'time_series.portfolio_value',
        },
      ],
    },
    {
      id: 'weights_by_ticker',
      type: 'bar',
      title: 'Структура портфеля по бумагам',
      x_axis: { field: 'ticker', label: 'Тикер' },
      y_axis: { field: 'weight_pct', label: 'Вес, %' },
      series: [
        {
          id: 'weights',
          label: 'Вес бумаги',
          data_ref: 'data.per_instrument',
        },
      ],
    },
  ],
  tables: [
    {
      id: 'positions',
      title: 'Позиции портфеля',
      columns: [
        { id: 'ticker', label: 'Тикер' },
        { id: 'weight_pct', label: 'Вес, %', align: 'right' },
        { id: 'total_return_pct', label: 'Доходность, %', align: 'right' },
        { id: 'annualized_volatility_pct', label: 'Волатильность, %', align: 'right' },
        { id: 'max_drawdown_pct', label: 'Max DD, %', align: 'right' },
      ],
      data_ref: 'data.per_instrument',
    },
    {
      id: 'stress_results',
      title: 'Результаты стресс-сценариев',
      columns: [
        { id: 'id', label: 'Сценарий' },
        { id: 'description', label: 'Описание' },
        { id: 'pnl_pct', label: 'P&L, %', align: 'right' },
      ],
      data_ref: 'data.stress_results',
    },
  ],
  alerts: [
    {
      id: 'issuer_concentration',
      severity: 'high',
      message: 'Концентрация по эмитенту SBER превышает лимит 15%.',
      related_ids: ['ticker:SBER', 'metric:top1_weight_pct'],
    },
    {
      id: 'var_limit_near',
      severity: 'medium',
      message: 'Var_light 4.5% близок к установленному лимиту 5%.',
      related_ids: ['metric:portfolio_var_light'],
    },
  ],
  data: {
    per_instrument: [
      {
        ticker: 'SBER',
        weight_pct: 15.2,
        total_return_pct: 12.4,
        annualized_volatility_pct: 18.3,
        max_drawdown_pct: -9.3,
      },
      {
        ticker: 'GAZP',
        weight_pct: 12.8,
        total_return_pct: 9.1,
        annualized_volatility_pct: 16.4,
        max_drawdown_pct: -8.7,
      },
      {
        ticker: 'LKOH',
        weight_pct: 10.5,
        total_return_pct: 11.6,
        annualized_volatility_pct: 15.9,
        max_drawdown_pct: -7.1,
      },
      {
        ticker: 'ROSN',
        weight_pct: 8.2,
        total_return_pct: 7.4,
        annualized_volatility_pct: 14.2,
        max_drawdown_pct: -6.8,
      },
      {
        ticker: 'MTSS',
        weight_pct: 7.4,
        total_return_pct: 5.1,
        annualized_volatility_pct: 13.3,
        max_drawdown_pct: -5.2,
      },
    ],
    stress_results: [
      { id: 'oil_drop', description: 'Падение нефти -15%', pnl_pct: -4.2 },
      { id: 'usd_rub_90', description: 'Ослабление рубля до 90', pnl_pct: 2.1 },
      { id: 'rate_hike', description: 'Рост ставки +200 б.п.', pnl_pct: -1.7 },
    ],
  },
  time_series: {
    portfolio_value: [
      { date: '2025-11-01', value: 100 },
      { date: '2025-11-05', value: 101.5 },
      { date: '2025-11-10', value: 102.3 },
      { date: '2025-11-15', value: 103.8 },
      { date: '2025-11-20', value: 104.1 },
      { date: '2025-11-25', value: 104.9 },
      { date: '2025-11-30', value: 106.2 },
      { date: '2025-12-05', value: 108.4 },
      { date: '2025-12-10', value: 110.2 },
      { date: '2025-12-11', value: 111.6 },
    ],
  },
};
