import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useStrategyStore } from "@/stores/strategyStore";

const MODE_LABELS: Record<string, string> = {
  SINAL_APENAS: "Sinal Apenas",
  SEMI_AUTO: "Semi-Auto",
  TOTALMENTE_AUTO: "Totalmente Auto",
};

export function StrategyList() {
  const strategies = useStrategyStore((s) => s.strategies);
  const listLoading = useStrategyStore((s) => s.listLoading);
  const loadStrategies = useStrategyStore((s) => s.loadStrategies);
  const remove = useStrategyStore((s) => s.remove);
  const resetDraft = useStrategyStore((s) => s.resetDraft);
  const navigate = useNavigate();

  useEffect(() => {
    loadStrategies();
  }, [loadStrategies]);

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-xl font-bold">Minhas Estratégias</h2>
        <button
          onClick={() => {
            resetDraft();
            navigate("/strategies/new");
          }}
          className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
        >
          + Nova Estratégia
        </button>
      </div>

      {listLoading && (
        <p className="text-sm text-zinc-500">Carregando...</p>
      )}

      {!listLoading && strategies.length === 0 && (
        <p className="text-sm text-zinc-500">
          Nenhuma estratégia criada. Clique em "+ Nova Estratégia" para começar.
        </p>
      )}

      <div className="space-y-3">
        {strategies.map((s) => (
          <div
            key={s.id}
            className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900 p-4"
          >
            <div
              className="flex-1 cursor-pointer"
              onClick={() => navigate(`/strategies/${s.id}`)}
            >
              <div className="font-medium">{s.name}</div>
              {s.description && (
                <div className="mt-1 text-xs text-zinc-500">{s.description}</div>
              )}
              <div className="mt-2 flex items-center gap-3 text-xs text-zinc-500">
                <span className="rounded bg-zinc-800 px-2 py-0.5">
                  {MODE_LABELS[s.mode] ?? s.mode}
                </span>
                <span>{s.indicator_count} indicadores</span>
                <span>{s.step_count} passos</span>
              </div>
            </div>
            <button
              onClick={async (e) => {
                e.stopPropagation();
                if (confirm(`Excluir "${s.name}"?`)) {
                  await remove(s.id);
                }
              }}
              className="ml-4 rounded px-2 py-1 text-xs text-red-400 hover:bg-red-400/10"
            >
              Excluir
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
