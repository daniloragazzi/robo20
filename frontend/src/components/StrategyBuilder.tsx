import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useStrategyStore } from "@/stores/strategyStore";
import { useIndicatorStore } from "@/stores/indicatorStore";
import type { DraftIndicator, DraftStep } from "@/stores/strategyStore";
import type { IndicatorInfo } from "@/api/indicators";
import type { ConditionNode, ConditionLeafNode, ConditionGroupNode, RiskConfigIn } from "@/api/strategies";

// ------------------------------------------------------------------ //
//  Condition types available per indicator category                     //
// ------------------------------------------------------------------ //

const OSCILLATOR_CONDITIONS = [
  { value: "gt", label: "Valor >" },
  { value: "lt", label: "Valor <" },
  { value: "gte", label: "Valor ≥" },
  { value: "lte", label: "Valor ≤" },
  { value: "cross_above", label: "Cruza acima" },
  { value: "cross_below", label: "Cruza abaixo" },
];

const SIGNAL_CONDITIONS = [
  { value: "signal_bull", label: "Sinal Bullish" },
  { value: "signal_bear", label: "Sinal Bearish" },
];

const LATERALIZATION_CONDITIONS = [
  { value: "in_range", label: "Em lateralização" },
  { value: "breakout", label: "Rompimento" },
  { value: "signal_bull", label: "Breakout Bull" },
  { value: "signal_bear", label: "Breakout Bear" },
];

const SIGNAL_INDICATORS = new Set(["mss", "choch", "fvg", "fibonacci"]);
const LATERALIZATION_INDICATORS = new Set(["lateralization"]);

function getConditions(indicatorType: string) {
  if (LATERALIZATION_INDICATORS.has(indicatorType)) return LATERALIZATION_CONDITIONS;
  if (SIGNAL_INDICATORS.has(indicatorType)) return [...SIGNAL_CONDITIONS, ...OSCILLATOR_CONDITIONS];
  return OSCILLATOR_CONDITIONS;
}

function needsThreshold(conditionType: string): boolean {
  return ["gt", "lt", "gte", "lte", "eq", "cross_above", "cross_below"].includes(conditionType);
}

const TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"];

const MODES = [
  { value: "SINAL_APENAS" as const, label: "Sinal Apenas", desc: "Apenas notificação" },
  { value: "SEMI_AUTO" as const, label: "Semi-Auto", desc: "Ordem pendente de confirmação" },
  { value: "TOTALMENTE_AUTO" as const, label: "Totalmente Auto", desc: "Execução automática" },
];

// ------------------------------------------------------------------ //
//  Main component                                                      //
// ------------------------------------------------------------------ //

export function StrategyBuilder() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEditing = id && id !== "new";

  // Store selectors
  const {
    name, description, mode, indicators, steps, riskConfig, saving, error, editingId,
    setName, setDescription, setMode, addIndicator,
    addStep, addGroupStep, removeStep, updateStep, moveStep, setRiskConfig,
    save, loadForEdit, resetDraft,
  } = useStrategyStore();

  // Indicator registry from backend
  const available = useIndicatorStore((s) => s.available);
  const loadAvailable = useIndicatorStore((s) => s.loadAvailable);

  useEffect(() => {
    loadAvailable();
  }, [loadAvailable]);

  useEffect(() => {
    if (isEditing && editingId !== Number(id)) {
      loadForEdit(Number(id));
    }
  }, [id, isEditing, editingId, loadForEdit]);

  const handleSave = async () => {
    try {
      await save();
      navigate("/strategies");
    } catch {
      // error is set in store
    }
  };

  // Natural language summary
  const summary = buildSummary(name, mode, indicators, steps, available);

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-xl font-bold">
          {isEditing ? "Editar Estratégia" : "Nova Estratégia"}
        </h2>
        <button
          onClick={() => { resetDraft(); navigate("/strategies"); }}
          className="text-xs text-zinc-500 hover:text-zinc-300"
        >
          ← Voltar
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded bg-red-500/10 px-3 py-2 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* ---- Name + Description + Mode ---- */}
      <section className="mb-6 space-y-3">
        <div>
          <label className="mb-1 block text-xs text-zinc-500">Nome</label>
          <input
            className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ex: RSI Oversold + MSS Bull"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-zinc-500">Descrição (opcional)</label>
          <textarea
            className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Descreva a lógica da estratégia..."
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-zinc-500">Modo de execução</label>
          <div className="flex gap-2">
            {MODES.map((m) => (
              <button
                key={m.value}
                onClick={() => setMode(m.value)}
                className={`rounded px-3 py-1.5 text-xs font-medium transition ${
                  mode === m.value
                    ? "bg-indigo-600 text-white"
                    : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
                }`}
                title={m.desc}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* ---- Indicators ---- */}
      <section className="mb-6">
        <h3 className="mb-3 text-sm font-semibold text-zinc-300">Indicadores</h3>
        {indicators.map((ind, idx) => (
          <IndicatorRow key={ind._key} ind={ind} idx={idx} available={available} />
        ))}
        <AddIndicatorButton available={available} onAdd={addIndicator} />
      </section>

      {/* ---- Steps ---- */}
      <section className="mb-6">
        <h3 className="mb-3 text-sm font-semibold text-zinc-300">Passos da State Machine</h3>
        {steps.length === 0 && (
          <p className="mb-2 text-xs text-zinc-600">Nenhum passo definido.</p>
        )}
        {steps.map((step, idx) => (
          <StepRow
            key={step._key}
            step={step}
            idx={idx}
            totalSteps={steps.length}
            indicators={indicators}
            onUpdate={(patch) => updateStep(step._key, patch)}
            onRemove={() => removeStep(step._key)}
            onMoveUp={() => idx > 0 && moveStep(idx, idx - 1)}
            onMoveDown={() => idx < steps.length - 1 && moveStep(idx, idx + 1)}
          />
        ))}
        <div className="flex gap-2 mt-2">
          <button
            onClick={addStep}
            disabled={indicators.length === 0}
            className="rounded border border-dashed border-zinc-700 px-3 py-1.5 text-xs text-zinc-500 hover:border-zinc-500 hover:text-zinc-300 disabled:opacity-30"
          >
            + Passo Simples
          </button>
          <button
            onClick={() => {
              const tree: ConditionGroupNode = {
                type: "and",
                conditions: [
                  { type: "condition", indicator_type: indicators[0]?.indicator_type ?? "", condition_type: "gt", indicator_ref: 0 },
                ],
              };
              addGroupStep(tree);
            }}
            disabled={indicators.length === 0}
            className="rounded border border-dashed border-indigo-700 px-3 py-1.5 text-xs text-indigo-400 hover:border-indigo-500 hover:text-indigo-300 disabled:opacity-30"
          >
            + Passo Composto (AND/OR)
          </button>
        </div>
      </section>

      {/* ---- Risk Config ---- */}
      <section className="mb-6">
        <h3 className="mb-3 text-sm font-semibold text-zinc-300">Gestão de Risco</h3>
        <RiskConfigPanel riskConfig={riskConfig} onChange={setRiskConfig} />
      </section>

      {/* ---- Summary ---- */}
      {summary && (
        <section className="mb-6 rounded border border-zinc-800 bg-zinc-900/50 p-4">
          <h3 className="mb-2 text-xs font-semibold text-zinc-400">Resumo da Estratégia</h3>
          <p className="whitespace-pre-wrap text-sm text-zinc-300">{summary}</p>
        </section>
      )}

      {/* ---- Save ---- */}
      <div className="flex gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="rounded bg-indigo-600 px-6 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {saving ? "Salvando..." : isEditing ? "Atualizar" : "Criar Estratégia"}
        </button>
        <button
          onClick={() => { resetDraft(); navigate("/strategies"); }}
          className="rounded bg-zinc-800 px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-700"
        >
          Cancelar
        </button>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ //
//  Indicator row                                                       //
// ------------------------------------------------------------------ //

function IndicatorRow({
  ind,
  idx,
  available,
}: {
  ind: DraftIndicator;
  idx: number;
  available: IndicatorInfo[];
}) {
  const removeIndicator = useStrategyStore((s) => s.removeIndicator);
  const updateIndicatorParams = useStrategyStore((s) => s.updateIndicatorParams);
  const info = available.find((a) => a.name === ind.indicator_type);
  const paramEntries = info
    ? Object.entries(info.params_schema.properties ?? {})
    : [];

  return (
    <div className="mb-2 rounded border border-zinc-800 bg-zinc-900 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="rounded bg-zinc-800 px-2 py-0.5 text-xs font-mono">
            #{idx}
          </span>
          <span className="text-sm font-medium">
            {info?.display_name ?? ind.indicator_type.toUpperCase()}
          </span>
          <span className="text-xs text-zinc-500">{ind.timeframe}</span>
        </div>
        <button
          onClick={() => removeIndicator(ind._key)}
          className="text-xs text-red-400 hover:text-red-300"
        >
          Remover
        </button>
      </div>
      {paramEntries.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-3">
          {paramEntries.map(([pname, pdef]) => (
            <div key={pname} className="flex items-center gap-1">
              <label className="text-xs text-zinc-500">{pname}</label>
              <input
                className="w-20 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs"
                type="number"
                value={
                  ind.params[pname] !== undefined
                    ? String(ind.params[pname])
                    : String(pdef.default ?? "")
                }
                onChange={(e) =>
                  updateIndicatorParams(ind._key, {
                    ...ind.params,
                    [pname]: Number(e.target.value),
                  })
                }
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ //
//  Add indicator button                                                //
// ------------------------------------------------------------------ //

function AddIndicatorButton({
  available,
  onAdd,
}: {
  available: IndicatorInfo[];
  onAdd: (ind: DraftIndicator) => void;
}) {
  const [open, setOpen] = useState(false);
  const [selectedTf, setSelectedTf] = useState("5m");

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="rounded border border-dashed border-zinc-700 px-3 py-1.5 text-xs text-zinc-500 hover:border-zinc-500 hover:text-zinc-300"
      >
        + Adicionar Indicador
      </button>
    );
  }

  return (
    <div className="rounded border border-zinc-700 bg-zinc-900 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold text-zinc-400">Selecionar Indicador</span>
        <div className="flex items-center gap-2">
          <label className="text-xs text-zinc-500">TF:</label>
          <select
            className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs"
            value={selectedTf}
            onChange={(e) => setSelectedTf(e.target.value)}
          >
            {TIMEFRAMES.map((tf) => (
              <option key={tf} value={tf}>
                {tf}
              </option>
            ))}
          </select>
          <button
            onClick={() => setOpen(false)}
            className="text-xs text-zinc-500 hover:text-zinc-300"
          >
            Fechar
          </button>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {available.map((info) => (
          <button
            key={info.name}
            className="rounded bg-zinc-800 px-2 py-1.5 text-xs hover:bg-zinc-700"
            onClick={() => {
              const defaultParams: Record<string, unknown> = {};
              for (const [k, v] of Object.entries(info.params_schema.properties ?? {})) {
                if (v.default !== undefined) defaultParams[k] = v.default;
              }
              onAdd({
                _key: "",
                indicator_type: info.name,
                params: defaultParams,
                timeframe: selectedTf,
                label: info.display_name,
              });
              setOpen(false);
            }}
          >
            {info.display_name}
          </button>
        ))}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ //
//  Step row                                                            //
// ------------------------------------------------------------------ //

function StepRow({
  step,
  idx,
  totalSteps,
  indicators,
  onUpdate,
  onRemove,
  onMoveUp,
  onMoveDown,
}: {
  step: DraftStep;
  idx: number;
  totalSteps: number;
  indicators: DraftIndicator[];
  onUpdate: (patch: Partial<DraftStep>) => void;
  onRemove: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}) {
  const isGroup = !!step.condition_tree;

  return (
    <div className="mb-2 rounded border border-zinc-800 bg-zinc-900 p-3">
      <div className="flex items-center gap-2">
        <span className="text-xs font-bold text-indigo-400">Passo {idx + 1}</span>
        {isGroup && (
          <span className="rounded bg-indigo-600/20 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-300">
            COMPOSTO
          </span>
        )}
        <div className="ml-auto flex gap-1">
          <button onClick={onMoveUp} disabled={idx === 0} className="rounded px-1 text-xs text-zinc-500 hover:text-zinc-300 disabled:opacity-30">↑</button>
          <button onClick={onMoveDown} disabled={idx === totalSteps - 1} className="rounded px-1 text-xs text-zinc-500 hover:text-zinc-300 disabled:opacity-30">↓</button>
          <button onClick={onRemove} className="rounded px-1 text-xs text-red-400 hover:text-red-300">✕</button>
        </div>
      </div>

      {isGroup ? (
        <ConditionTreeEditor
          node={step.condition_tree!}
          indicators={indicators}
          onChange={(tree) => onUpdate({ condition_tree: tree })}
        />
      ) : (
        <SimpleConditionEditor step={step} indicators={indicators} onUpdate={onUpdate} />
      )}

      {/* Description */}
      <input
        className="mt-2 w-full rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs text-zinc-400"
        placeholder="Descrição do passo (opcional)"
        value={step.description ?? ""}
        onChange={(e) => onUpdate({ description: e.target.value || null })}
      />
    </div>
  );
}

// ------------------------------------------------------------------ //
//  Simple condition editor (flat step)                                 //
// ------------------------------------------------------------------ //

function SimpleConditionEditor({
  step,
  indicators,
  onUpdate,
}: {
  step: DraftStep;
  indicators: DraftIndicator[];
  onUpdate: (patch: Partial<DraftStep>) => void;
}) {
  const selectedInd = indicators[step.indicator_ref];
  const conditions = selectedInd ? getConditions(selectedInd.indicator_type) : OSCILLATOR_CONDITIONS;

  return (
    <div className="mt-2 flex flex-wrap gap-2">
      <select
        className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs"
        value={step.indicator_ref}
        onChange={(e) => onUpdate({ indicator_ref: Number(e.target.value) })}
      >
        {indicators.map((ind, i) => (
          <option key={ind._key} value={i}>
            #{i} {ind.label ?? ind.indicator_type.toUpperCase()} ({ind.timeframe})
          </option>
        ))}
      </select>
      <select
        className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs"
        value={step.condition_type}
        onChange={(e) => onUpdate({ condition_type: e.target.value })}
      >
        {conditions.map((c) => (
          <option key={c.value} value={c.value}>{c.label}</option>
        ))}
      </select>
      {needsThreshold(step.condition_type) && (
        <input
          className="w-24 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs"
          type="number"
          placeholder="Valor"
          value={step.condition_value ?? ""}
          onChange={(e) => onUpdate({ condition_value: e.target.value || null })}
        />
      )}
    </div>
  );
}

// ------------------------------------------------------------------ //
//  Condition tree editor (AND / OR groups)                             //
// ------------------------------------------------------------------ //

function ConditionTreeEditor({
  node,
  indicators,
  onChange,
  depth = 0,
}: {
  node: ConditionNode;
  indicators: DraftIndicator[];
  onChange: (node: ConditionNode) => void;
  depth?: number;
}) {
  if (node.type === "condition") {
    return (
      <LeafConditionEditor node={node} indicators={indicators} onChange={onChange} />
    );
  }

  const group = node as ConditionGroupNode;
  const borderColor = depth === 0 ? "border-indigo-700/50" : "border-zinc-700";

  return (
    <div className={`mt-2 rounded border ${borderColor} bg-zinc-950/50 p-2`}>
      {/* Logic selector */}
      <div className="mb-2 flex items-center gap-2">
        <span className="text-[10px] font-semibold text-zinc-500 uppercase">Operador:</span>
        <button
          onClick={() => onChange({ ...group, type: "and" })}
          className={`rounded px-2 py-0.5 text-[10px] font-bold ${
            group.type === "and" ? "bg-emerald-600 text-white" : "bg-zinc-800 text-zinc-500"
          }`}
        >
          AND
        </button>
        <button
          onClick={() => onChange({ ...group, type: "or" })}
          className={`rounded px-2 py-0.5 text-[10px] font-bold ${
            group.type === "or" ? "bg-amber-600 text-white" : "bg-zinc-800 text-zinc-500"
          }`}
        >
          OR
        </button>
      </div>

      {/* Child conditions */}
      {group.conditions.map((child, ci) => (
        <div key={ci} className="mb-1 flex items-start gap-1">
          <div className="flex-1">
            <ConditionTreeEditor
              node={child}
              indicators={indicators}
              onChange={(updated) => {
                const newChildren = [...group.conditions];
                newChildren[ci] = updated;
                onChange({ ...group, conditions: newChildren });
              }}
              depth={depth + 1}
            />
          </div>
          {group.conditions.length > 1 && (
            <button
              onClick={() => {
                const newChildren = group.conditions.filter((_, i) => i !== ci);
                onChange({ ...group, conditions: newChildren });
              }}
              className="mt-1 text-xs text-red-400 hover:text-red-300"
            >
              ✕
            </button>
          )}
        </div>
      ))}

      {/* Add buttons */}
      <div className="mt-1 flex gap-2">
        <button
          onClick={() => {
            const newLeaf: ConditionLeafNode = {
              type: "condition",
              indicator_type: indicators[0]?.indicator_type ?? "",
              condition_type: "gt",
              indicator_ref: 0,
            };
            onChange({ ...group, conditions: [...group.conditions, newLeaf] });
          }}
          className="text-[10px] text-zinc-500 hover:text-zinc-300"
        >
          + Condição
        </button>
        <button
          onClick={() => {
            const newGroup: ConditionGroupNode = {
              type: group.type === "and" ? "or" : "and",
              conditions: [
                { type: "condition", indicator_type: indicators[0]?.indicator_type ?? "", condition_type: "gt", indicator_ref: 0 },
              ],
            };
            onChange({ ...group, conditions: [...group.conditions, newGroup] });
          }}
          className="text-[10px] text-indigo-400 hover:text-indigo-300"
        >
          + Grupo ()
        </button>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ //
//  Leaf condition editor (inside tree)                                  //
// ------------------------------------------------------------------ //

function LeafConditionEditor({
  node,
  indicators,
  onChange,
}: {
  node: ConditionLeafNode;
  indicators: DraftIndicator[];
  onChange: (node: ConditionNode) => void;
}) {
  const ref = node.indicator_ref ?? 0;
  const selectedInd = indicators[ref];
  const conditions = selectedInd ? getConditions(selectedInd.indicator_type) : OSCILLATOR_CONDITIONS;

  return (
    <div className="mt-1 flex flex-wrap items-center gap-1.5">
      <select
        className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs"
        value={ref}
        onChange={(e) => {
          const newRef = Number(e.target.value);
          const newInd = indicators[newRef];
          onChange({
            ...node,
            indicator_ref: newRef,
            indicator_type: newInd?.indicator_type ?? "",
          });
        }}
      >
        {indicators.map((ind, i) => (
          <option key={ind._key} value={i}>
            #{i} {ind.label ?? ind.indicator_type.toUpperCase()} ({ind.timeframe})
          </option>
        ))}
      </select>
      <select
        className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs"
        value={node.condition_type}
        onChange={(e) => onChange({ ...node, condition_type: e.target.value })}
      >
        {conditions.map((c) => (
          <option key={c.value} value={c.value}>{c.label}</option>
        ))}
      </select>
      {needsThreshold(node.condition_type) && (
        <input
          className="w-20 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs"
          type="number"
          placeholder="Valor"
          value={node.condition_value ?? ""}
          onChange={(e) => onChange({ ...node, condition_value: e.target.value || null })}
        />
      )}
    </div>
  );
}

// ------------------------------------------------------------------ //
//  Risk config panel                                                   //
// ------------------------------------------------------------------ //

function RiskConfigPanel({
  riskConfig,
  onChange,
}: {
  riskConfig: RiskConfigIn;
  onChange: (patch: Partial<RiskConfigIn>) => void;
}) {
  const partials = riskConfig.partial_exits ?? [];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        {/* Stop Loss */}
        <div>
          <label className="mb-1 block text-xs text-zinc-500">Stop Loss</label>
          <select
            className="w-full rounded border border-zinc-700 bg-zinc-800 px-2 py-1.5 text-xs"
          value={riskConfig.stop_loss_type ?? ""}
            onChange={(e) => onChange({ stop_loss_type: e.target.value || null })}
          >
            <option value="">Nenhum</option>
            <option value="fixed_pct">% Fixo</option>
            <option value="atr">ATR Múltiplo</option>
            <option value="swing">Swing Low/High</option>
          </select>
          {riskConfig.stop_loss_type && (
            <input
              className="mt-1 w-full rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs"
              type="number"
              step="0.1"
              placeholder={riskConfig.stop_loss_type === "fixed_pct" ? "% (ex: 2)" : "Multiplicador"}
              value={riskConfig.stop_loss_value ?? ""}
              onChange={(e) => onChange({ stop_loss_value: e.target.value ? Number(e.target.value) : null })}
            />
          )}
        </div>

        {/* Take Profit */}
        <div>
          <label className="mb-1 block text-xs text-zinc-500">Take Profit</label>
          <select
            className="w-full rounded border border-zinc-700 bg-zinc-800 px-2 py-1.5 text-xs"
            value={riskConfig.take_profit_type ?? ""}
            onChange={(e) => onChange({ take_profit_type: e.target.value || null })}
          >
            <option value="">Nenhum</option>
            <option value="fixed_pct">% Fixo</option>
            <option value="rr_ratio">Risco/Retorno</option>
          </select>
          {riskConfig.take_profit_type && (
            <input
              className="mt-1 w-full rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs"
              type="number"
              step="0.1"
              placeholder={riskConfig.take_profit_type === "fixed_pct" ? "% (ex: 4)" : "R:R (ex: 2)"}
              value={riskConfig.take_profit_value ?? ""}
              onChange={(e) => onChange({ take_profit_value: e.target.value ? Number(e.target.value) : null })}
            />
          )}
        </div>
      </div>

      {/* Position Sizing */}
      <div>
        <label className="mb-1 block text-xs text-zinc-500">Dimensionamento da Posição</label>
        <select
          className="w-full rounded border border-zinc-700 bg-zinc-800 px-2 py-1.5 text-xs"
          value={riskConfig.sizing_mode ?? ""}
          onChange={(e) => onChange({ sizing_mode: e.target.value || null })}
        >
          <option value="">Nenhum</option>
          <option value="fixed_pct">% Fixo do Capital</option>
          <option value="risk_based">Baseado no Risco (% Stop)</option>
        </select>

        {riskConfig.sizing_mode === "fixed_pct" && (
          <div className="mt-2">
            <label className="mb-1 block text-[10px] text-zinc-500">% do Capital</label>
            <input
              className="w-32 rounded border border-zinc-700 bg-zinc-800 px-2 py-1.5 text-xs"
              type="number" min="0.1" max="100" step="0.5"
              placeholder="Ex: 5"
              value={riskConfig.position_size_pct ?? ""}
              onChange={(e) => onChange({ position_size_pct: e.target.value ? Number(e.target.value) : null })}
            />
          </div>
        )}

        {riskConfig.sizing_mode === "risk_based" && (
          <div className="mt-2 rounded border border-zinc-800 bg-zinc-950/50 p-3">
            <p className="mb-2 text-[10px] text-zinc-400">
              O sistema calcula o tamanho da posição de forma que se o stop for atingido,
              a perda seja exatamente o % do capital definido abaixo.
            </p>
            <label className="mb-1 block text-[10px] text-zinc-500">% do Capital a Arriscar</label>
            <input
              className="w-32 rounded border border-zinc-700 bg-zinc-800 px-2 py-1.5 text-xs"
              type="number" min="0.1" max="100" step="0.1"
              placeholder="Ex: 1 ou 2"
              value={riskConfig.risk_pct ?? ""}
              onChange={(e) => onChange({ risk_pct: e.target.value ? Number(e.target.value) : null })}
            />
            <p className="mt-1 text-[10px] text-zinc-600">
              Fórmula: Posição = (Capital × {riskConfig.risk_pct ?? "?"}%) ÷ Distância do Stop
            </p>
          </div>
        )}
      </div>

      {/* Partial Exits */}
      <div>
        <label className="mb-1 block text-xs text-zinc-500">Saídas Parciais</label>
        {partials.length === 0 && (
          <p className="mb-2 text-[10px] text-zinc-600">Nenhuma saída parcial definida — saída total no TP.</p>
        )}
        {partials.map((pe, i) => (
          <div key={i} className="mb-2 flex items-center gap-2 rounded border border-zinc-800 bg-zinc-950/50 p-2">
            <div>
              <label className="block text-[10px] text-zinc-500">% da Posição</label>
              <input
                className="w-16 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs"
                type="number" min="1" max="100" step="5"
                value={pe.pct}
                onChange={(e) => {
                  const updated = [...partials];
                  updated[i] = { ...pe, pct: Number(e.target.value) };
                  onChange({ partial_exits: updated });
                }}
              />
            </div>
            <div>
              <label className="block text-[10px] text-zinc-500">Tipo de Alvo</label>
              <select
                className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs"
                value={pe.target_type}
                onChange={(e) => {
                  const updated = [...partials];
                  updated[i] = { ...pe, target_type: e.target.value };
                  onChange({ partial_exits: updated });
                }}
              >
                <option value="rr_ratio">Risco:Retorno</option>
                <option value="fixed_pct">% Fixo</option>
                <option value="trailing_pct">Trailing %</option>
              </select>
            </div>
            <div>
              <label className="block text-[10px] text-zinc-500">
                {pe.target_type === "rr_ratio" ? "R:R" : pe.target_type === "trailing_pct" ? "Trail %" : "%"}
              </label>
              <input
                className="w-16 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs"
                type="number" min="0.1" step="0.1"
                value={pe.target_value}
                onChange={(e) => {
                  const updated = [...partials];
                  updated[i] = { ...pe, target_value: Number(e.target.value) };
                  onChange({ partial_exits: updated });
                }}
              />
            </div>
            <button
              onClick={() => onChange({ partial_exits: partials.filter((_, j) => j !== i) })}
              className="mt-3 text-xs text-red-400 hover:text-red-300"
            >
              ✕
            </button>
          </div>
        ))}
        <button
          onClick={() =>
            onChange({
              partial_exits: [...partials, { pct: 50, target_type: "rr_ratio", target_value: 1 }],
            })
          }
          className="rounded border border-dashed border-zinc-700 px-3 py-1 text-[10px] text-zinc-500 hover:border-zinc-500 hover:text-zinc-300"
        >
          + Adicionar Saída Parcial
        </button>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ //
//  Natural language summary builder                                    //
// ------------------------------------------------------------------ //

const CONDITION_TEXT: Record<string, string> = {
  gt: "está acima de",
  lt: "está abaixo de",
  gte: "está em ou acima de",
  lte: "está em ou abaixo de",
  eq: "é igual a",
  cross_above: "cruza acima de",
  cross_below: "cruza abaixo de",
  signal_bull: "dá sinal BULLISH",
  signal_bear: "dá sinal BEARISH",
  in_range: "está em lateralização",
  breakout: "rompe a lateralização",
};

function describeNode(node: ConditionNode, indicators: DraftIndicator[]): string {
  if (node.type === "condition") {
    const ref = node.indicator_ref ?? 0;
    const ind = indicators[ref];
    if (!ind) return "?";
    const label = ind.label ?? ind.indicator_type.toUpperCase();
    const cond = CONDITION_TEXT[node.condition_type] ?? node.condition_type;
    const val = node.condition_value ? ` ${node.condition_value}` : "";
    return `${label} (${ind.timeframe}) ${cond}${val}`;
  }
  const group = node as ConditionGroupNode;
  const parts = group.conditions.map((c) => describeNode(c, indicators));
  const joiner = group.type === "and" ? " E " : " OU ";
  const inner = parts.join(joiner);
  return parts.length > 1 ? `(${inner})` : inner;
}

function buildSummary(
  name: string,
  mode: string,
  indicators: DraftIndicator[],
  steps: DraftStep[],
  _available: IndicatorInfo[],
): string | null {
  if (!steps.length || !indicators.length) return null;

  const modeText =
    mode === "SINAL_APENAS"
      ? "apenas sinalizar"
      : mode === "SEMI_AUTO"
        ? "abrir ordem pendente de confirmação"
        : "executar ordem automaticamente";

  let text = `Estratégia "${name || "Sem nome"}" (${modeText}):\n\n`;

  for (const step of steps) {
    if (step.condition_tree) {
      text += `  ${step.step_index + 1}. Quando ${describeNode(step.condition_tree, indicators)}\n`;
    } else {
      const ind = indicators[step.indicator_ref];
      if (!ind) continue;
      const label = ind.label ?? ind.indicator_type.toUpperCase();
      const cond = CONDITION_TEXT[step.condition_type] ?? step.condition_type;
      const val = step.condition_value ? ` ${step.condition_value}` : "";
      text += `  ${step.step_index + 1}. Quando ${label} (${ind.timeframe}) ${cond}${val}\n`;
    }
  }

  return text.trim();
}
