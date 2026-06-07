/**
 * Shared query mix for Phase 10 load and baseline runs.
 * Simple queries are fast-path; complex queries exercise orchestration.
 */
export const QUERIES = [
  {
    label: 'entity_confirm_simple',
    complexity: 'simple',
    message: 'show me Zayidia Boys School costs',
  },
  {
    label: 'project_cost_simple',
    complexity: 'simple',
    message: 'show me National Guard project costs last month',
  },
  {
    label: 'payslip_honest',
    complexity: 'simple',
    message: 'what is my last payslip',
  },
  {
    label: 'financial_pandl',
    complexity: 'complex',
    message: 'show me profit and loss for last quarter',
  },
  {
    label: 'multi_project_compare',
    complexity: 'complex',
    message: 'compare top 5 projects by revenue this year vs last year',
  },
  {
    label: 'arabic_pandl',
    complexity: 'complex',
    message: 'أرني تقرير الأرباح والخسائر لهذا الشهر',
  },
  {
    label: 'forecast_oos',
    complexity: 'simple',
    message: "Forecast next month's cash position",
  },
  {
    label: 'empty_entity',
    complexity: 'simple',
    message: 'show me XYZNONEXISTENT999 project costs',
  },
];
