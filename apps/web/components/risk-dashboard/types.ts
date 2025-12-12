export type Severity = "info" | "low" | "medium" | "high" | "critical" | "warning";

export type WidgetType = "kpi_grid" | "table" | "chart" | "alert_list" | "text";

export interface DashboardMetadata {
  as_of: string;
  scenario_type?: string;
  base_currency?: string;
  portfolio_id?: string;
}

export interface Metric {
  id: string;
  label: string;
  value: number;
  unit?: string;
  change?: number;
  severity?: Severity;
}

export type ChartType = "line" | "bar" | "pie";

export interface ChartAxis {
  field: string;
  label?: string;
}

export interface ChartSeries {
  id: string;
  label: string;
  data_ref: string;
  color?: string;
}

export interface ChartSpec {
  id: string;
  type: ChartType;
  title: string;
  x_axis?: ChartAxis;
  y_axis?: ChartAxis;
  series: ChartSeries[];
}

export interface TableColumn {
  id: string;
  label: string;
  align?: "left" | "right" | "center";
}

export interface TableSpec {
  id: string;
  title?: string;
  columns: TableColumn[];
  data_ref: string;
}

export interface Alert {
  id: string;
  severity: Severity;
  message: string;
  related_ids?: string[];
}

export type RiskDashboardDataRow = Record<string, unknown>;

export interface RiskDashboardSpec {
  version?: string;
  metadata: DashboardMetadata;
  layout?: LayoutItem[];
  metrics?: Metric[];
  charts?: ChartSpec[];
  tables?: TableSpec[];
  alerts?: Alert[];
  data?: Record<string, unknown>;
  time_series?: Record<string, Array<Record<string, unknown>>>;
}

export interface LayoutItem {
  id: string;
  type: WidgetType;
  title?: string;
  description?: string;
  metric_ids?: string[];
  chart_id?: string;
  table_id?: string;
  alert_ids?: string[];
  columns?: number;
  options?: Record<string, unknown>;
}
