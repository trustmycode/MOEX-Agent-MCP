import { RiskCockpit } from '@/components/risk-dashboard/RiskCockpit';
import { riskDashboardMock } from '@/mocks/riskDashboardMock';

export default function RiskDashboardPage() {
  return (
    <main className="min-h-screen bg-background p-6 lg:p-10">
      <div className="mb-6 flex flex-col gap-2">
        <p className="text-sm uppercase tracking-[0.2em] text-slate-400">
          Risk Dashboard · Demo
        </p>
        <h1 className="text-3xl font-semibold text-white lg:text-4xl">RiskCockpit (mock)</h1>
        <p className="max-w-3xl text-slate-300">
          Захардкоженный пример из спецификации RiskDashboardSpec. Используйте для быстрой проверки
          верстки и поведения компонент без вызова агента.
        </p>
      </div>

      <RiskCockpit data={riskDashboardMock} />
    </main>
  );
}
