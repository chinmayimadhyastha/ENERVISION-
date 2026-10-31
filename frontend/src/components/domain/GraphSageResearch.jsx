import { useState } from 'react'
import {
  Award,
  BrainCircuit,
  Cpu,
  Layers,
  Network,
  Share2,
  Sparkles,
  Zap,
} from 'lucide-react'

import Card from '../ui/Card.jsx'
import Badge from '../ui/Badge.jsx'
import SectionTitle from '../ui/SectionTitle.jsx'
import Select from '../ui/Select.jsx'
import {
  GRAPHSAGE_RESEARCH_METADATA,
  GRAPHSAGE_EXPERIMENT_BENCHMARK,
  PLANT_NEIGHBOR_GRAPH,
} from '../../data/graphsageData.js'

export default function GraphSageResearch() {
  const plantKeys = Object.keys(PLANT_NEIGHBOR_GRAPH)
  const [selectedPlantKey, setSelectedPlantKey] = useState(plantKeys[0])

  const selectedNode = PLANT_NEIGHBOR_GRAPH[selectedPlantKey] || PLANT_NEIGHBOR_GRAPH[plantKeys[0]]

  return (
    <div className="space-y-6">
      <SectionTitle
        eyebrow="Research Innovation"
        title="Spatial-Temporal GraphSAGE + LSTM Architecture"
        description="Enhancing Karnataka solar power forecasts by capturing geographical grid topology and weather interactions across neighboring solar parks."
        badge={
          <span className="flex items-center gap-1.5 text-xs font-semibold text-solar-400">
            <Sparkles className="h-3.5 w-3.5" /> Best Test R²: 0.8641
          </span>
        }
      />

      {/* Overview Highlight Banner */}
      <Card padded accent="solar" className="relative overflow-hidden bg-gradient-to-r from-solar-950/20 via-brand-950/10 to-transparent">
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-3">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-solar-400/30 bg-solar-400/10 text-solar-300">
                <Network className="h-4 w-4" />
              </span>
              <div>
                <h3 className="font-display text-base font-bold text-white">
                  {GRAPHSAGE_RESEARCH_METADATA.title}
                </h3>
                <p className="eyebrow">{GRAPHSAGE_RESEARCH_METADATA.subtitle}</p>
              </div>
            </div>
            <p className="text-xs leading-relaxed text-graphite-300">
              Traditional LSTM networks model time-dependency for individual solar plants in isolation. 
              Our proposed architecture introduces a <strong>GraphSAGE spatial aggregation branch</strong> over Karnataka’s solar grid. 
              By dynamically exchanging cloud cover, irradiance, and generation states between neighboring plants, 
              the model achieved the highest test accuracy (<strong>R² = 0.8641</strong>), outperforming standalone recurrent baselines.
            </p>
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <Badge tone="solar" size="sm">k-NN Topology: k=10</Badge>
              <Badge tone="brand" size="sm">Lookback: 7 Days</Badge>
              <Badge tone="emerald" size="sm">Mean Neighborhood Pooling</Badge>
              <Badge tone="neutral" size="sm">Dual-Stream Fusion</Badge>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 lg:border-l lg:border-graphite-800 lg:pl-6">
            <div className="rounded-lg border border-graphite-800 bg-white/[0.02] p-3 text-center">
              <span className="eyebrow block">Validation R²</span>
              <span className="font-mono text-lg font-bold text-white">0.8345</span>
              <span className="block text-[10px] text-graphite-500">Seed 44</span>
            </div>
            <div className="rounded-lg border border-solar-400/30 bg-solar-400/[0.05] p-3 text-center">
              <span className="eyebrow block text-solar-300">Test R² (Top)</span>
              <span className="font-mono text-lg font-bold text-solar-300">0.8641</span>
              <span className="block text-[10px] text-solar-400/80">🏆 +0.41% over LSTM</span>
            </div>
            <div className="rounded-lg border border-graphite-800 bg-white/[0.02] p-3 text-center">
              <span className="eyebrow block">Test MAE</span>
              <span className="font-mono text-base font-bold text-white">0.1446</span>
              <span className="block text-[10px] text-graphite-500">MU/day</span>
            </div>
            <div className="rounded-lg border border-graphite-800 bg-white/[0.02] p-3 text-center">
              <span className="eyebrow block">Test RMSE</span>
              <span className="font-mono text-base font-bold text-white">0.2365</span>
              <span className="block text-[10px] text-graphite-500">Lowest error</span>
            </div>
          </div>
        </div>
      </Card>

      {/* Head-to-Head Benchmark Table */}
      <Card padded={false}>
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-graphite-700/70 px-4 py-3.5">
          <div className="flex items-center gap-2.5">
            <Award className="h-4 w-4 text-solar-400" />
            <div>
              <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">
                Head-to-Head Model Benchmark (Ablation Study)
              </h3>
              <p className="eyebrow">Evaluated across test split (2026 chronological window)</p>
            </div>
          </div>
          <Badge tone="solar" size="sm">Empirical Proof</Badge>
        </div>
        <div className="overflow-x-auto p-3">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-graphite-800 text-[11px] font-semibold uppercase text-graphite-400">
                <th className="pb-2 pl-3">Architecture</th>
                <th className="pb-2">Spatial Branch</th>
                <th className="pb-2 text-right">Features</th>
                <th className="pb-2 text-right">Val R²</th>
                <th className="pb-2 text-right">Test R²</th>
                <th className="pb-2 text-right">Test RMSE</th>
                <th className="pb-2 text-right pr-3">Test MAE</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-graphite-800/60 font-mono">
              {GRAPHSAGE_EXPERIMENT_BENCHMARK.map((row) => (
                <tr
                  key={row.model}
                  className={
                    row.isWinner
                      ? 'bg-solar-400/[0.08] text-white font-medium'
                      : 'text-graphite-300 hover:bg-white/[0.02]'
                  }
                >
                  <td className="py-3 pl-3 font-sans flex items-center gap-2">
                    {row.isWinner && <span className="h-2 w-2 rounded-full bg-solar-400 animate-pulse" />}
                    <span>{row.model}</span>
                    <span className="ml-1 text-[10px] font-normal text-graphite-500">({row.status})</span>
                  </td>
                  <td className="py-3 font-sans text-graphite-400 text-[11px]">{row.spatialGraph}</td>
                  <td className="py-3 text-right">{row.features}</td>
                  <td className="py-3 text-right">{row.valR2.toFixed(4)}</td>
                  <td className="py-3 text-right font-bold text-solar-300">{row.testR2.toFixed(4)}</td>
                  <td className="py-3 text-right">{row.testRMSE.toFixed(4)}</td>
                  <td className="py-3 text-right pr-3">{row.testMAE.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Interactive Plant Topology Explorer */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card padded className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Share2 className="h-4 w-4 text-brand-400" />
              <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">
                Interactive Plant Topology Graph
              </h3>
            </div>
            <Select
              aria-label="Select Plant"
              value={selectedPlantKey}
              onChange={(e) => setSelectedPlantKey(e.target.value)}
              options={plantKeys.map((k) => ({ value: k, label: k }))}
              className="w-48"
              selectClassName="py-1 text-xs"
            />
          </div>

          <div className="rounded-xl border border-graphite-800 bg-graphite-950/60 p-4">
            <div className="flex items-center justify-between border-b border-graphite-800/80 pb-3">
              <div>
                <span className="eyebrow block">Target Node (v)</span>
                <p className="font-display text-sm font-bold text-white">{selectedPlantKey}</p>
              </div>
              <div className="text-right">
                <span className="eyebrow block">Capacity</span>
                <p className="font-mono text-xs font-semibold text-solar-300">{selectedNode.capacityMW} MW</p>
              </div>
            </div>

            <div className="mt-3">
              <span className="eyebrow block mb-2 text-graphite-400">
                Connected Spatial Neighbors N(v) — k=10 Nearest Peers:
              </span>
              <div className="flex flex-wrap gap-1.5">
                {selectedNode.neighbors.map((nbr, idx) => (
                  <span
                    key={nbr}
                    className="inline-flex items-center gap-1 rounded-md border border-brand-400/20 bg-brand-400/10 px-2 py-1 text-[11px] font-medium text-brand-200"
                  >
                    <span className="font-mono text-[9px] text-brand-400">#{idx + 1}</span>
                    {nbr}
                  </span>
                ))}
              </div>
            </div>

            <div className="mt-4 rounded-lg border border-white/5 bg-white/[0.02] p-2.5 text-[11px] text-graphite-400 leading-relaxed">
              <span className="font-semibold text-graphite-200">GraphSAGE Inductive Aggregation:</span>
              <p className="mt-1">
                At each forecast step, GraphSAGE computes the normalized mean feature vector across these {selectedNode.neighbors.length} neighbors, 
                capturing incoming cloud fronts and temperature shifts before fusing with the local LSTM temporal embedding.
              </p>
            </div>
          </div>
        </Card>

        {/* Dual-Branch Architecture Box */}
        <Card padded className="space-y-4">
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-emerald-400" />
            <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">
              Dual-Stream Neural Network Pipeline
            </h3>
          </div>

          <div className="space-y-2.5 text-xs">
            <div className="rounded-lg border border-solar-400/20 bg-solar-400/[0.04] p-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-solar-200 flex items-center gap-1.5">
                  <Network className="h-3.5 w-3.5 text-solar-400" /> Stream 1: Spatial GraphSAGE
                </span>
                <span className="font-mono text-[10px] text-graphite-400">32 dims</span>
              </div>
              <p className="mt-1 text-[11px] text-graphite-300 leading-relaxed">
                2× MeanGraphSAGE layers (32 units each) with symmetric cosine similarity adjacency + Dropout (0.3).
              </p>
            </div>

            <div className="rounded-lg border border-brand-400/20 bg-brand-400/[0.04] p-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-brand-200 flex items-center gap-1.5">
                  <Cpu className="h-3.5 w-3.5 text-brand-400" /> Stream 2: Temporal LSTM
                </span>
                <span className="font-mono text-[10px] text-graphite-400">64 → 32 units</span>
              </div>
              <p className="mt-1 text-[11px] text-graphite-300 leading-relaxed">
                2-layer stacked LSTM over a 7-day chronological sequence with 0.3 dropout.
              </p>
            </div>

            <div className="rounded-lg border border-emerald-400/20 bg-emerald-400/[0.04] p-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-emerald-200 flex items-center gap-1.5">
                  <BrainCircuit className="h-3.5 w-3.5 text-emerald-400" /> Fusion & Output
                </span>
                <span className="font-mono text-[10px] text-graphite-400">Dense(16) → Dense(1)</span>
              </div>
              <p className="mt-1 text-[11px] text-graphite-300 leading-relaxed">
                Concatenates [Temporal Hidden State ‖ GraphSAGE Spatial State] into Dense(16, ReLU) to output day-ahead DailyGeneration_MU.
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}
