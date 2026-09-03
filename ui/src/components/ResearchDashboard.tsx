'use client'

/**
 * ResearchDashboard.tsx
 *
 * Research-grade metrics panel for the India Flood Intelligence system.
 * Displays four research pillars side-by-side:
 *   1. ML Model Metrics      — RMSE / MAE / NSE / KGE per model per horizon
 *   2. Baseline Comparison   — Skill scores vs persistence, Wilcoxon p-values
 *   3. LLM Ablation Study    — rule_only vs llm_enhanced vs llm_only scores
 *   4. Feature Importances   — Random Forest importance rankings
 *
 * All data is fetched from /api/research/* endpoints.
 */

import { useState, useEffect, useCallback } from 'react'
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
    ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis,
    PolarRadiusAxis, Radar, Legend, Cell
} from 'recharts'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
    Brain, BarChart3, FlaskConical, GitCompare,
    RefreshCw, Play, CheckCircle, Clock, AlertTriangle,
    TrendingUp, Award, Layers
} from 'lucide-react'

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------
const API = (path: string) => `/api/${path}`

async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
    const res = await fetch(API(path), {
        headers: { 'Content-Type': 'application/json',
                    'Authorization': 'Bearer dev-token', ...opts?.headers },
        ...opts,
    })
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
    return res.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface ModelMetric {
    model_name: string
    val_rmse?: number
    val_mae?: number
    trained_at?: string
    n_samples?: number
    feature_importances?: Record<string, number>
}

interface ValidationRow {
    Model: string
    'Horizon (h)': number
    N: number
    'RMSE (CFS)': number
    'MAE (CFS)': number
    NSE: number
    KGE: number
    CSI: number
    POD: number
    FAR: number
    F1: number
    Bias: number
}

interface AblationCondition {
    factual_accuracy: number
    actionability: number
    safety_compliance: number
    specificity: number
    overall_score: number
}

interface ResearchStatus {
    torch_available: boolean
    sklearn_available: boolean
    models_trained: boolean
    models_available: string[]
}

// ---------------------------------------------------------------------------
// Colour palette (dark-theme friendly)
// ---------------------------------------------------------------------------
const MODEL_COLORS: Record<string, string> = {
    lstm: '#60a5fa',
    gru: '#34d399',
    transformer: '#a78bfa',
    random_forest: '#fbbf24',
    rule_based: '#f87171',
    persistence: '#94a3b8',
    climatology: '#fb923c',
    threshold: '#e879f9',
    linear_trend: '#2dd4bf',
    arima: '#facc15',
}

const CONDITION_COLORS: Record<string, string> = {
    rule_only: '#f87171',
    llm_only: '#fbbf24',
    llm_enhanced: '#34d399',
}

const HORIZON_OPTIONS = ['6', '12', '24', '48', '72']

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
    return (
        <Badge className={ok
            ? 'bg-green-500/20 text-green-400 border border-green-500/30'
            : 'bg-red-500/20 text-red-400 border border-red-500/30'}>
            {ok ? <CheckCircle className="h-3 w-3 mr-1 inline" /> : <AlertTriangle className="h-3 w-3 mr-1 inline" />}
            {label}
        </Badge>
    )
}

function MetricBadge({ value, good }: { value: number | undefined; good: boolean }) {
    if (value === undefined || value === null) return <span className="text-gray-500">—</span>
    return (
        <span className={good ? 'text-green-400 font-mono' : 'text-amber-400 font-mono'}>
            {value.toLocaleString(undefined, { maximumFractionDigits: 3 })}
        </span>
    )
}

// ---------------------------------------------------------------------------
// Panel 1: ML Model Training Metrics
// ---------------------------------------------------------------------------
function ModelMetricsPanel() {
    const [data, setData] = useState<ModelMetric[]>([])
    const [loading, setLoading] = useState(false)
    const [training, setTraining] = useState(false)
    const [status, setStatus] = useState<ResearchStatus | null>(null)

    const load = useCallback(async () => {
        setLoading(true)
        try {
            const [metrics, st] = await Promise.all([
                apiFetch<{ models: ModelMetric[] }>('research/model-metrics'),
                apiFetch<ResearchStatus>('research/status'),
            ])
            setData(metrics.models || [])
            setStatus(st)
        } catch (e) {
            console.error('model-metrics fetch failed:', e)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => { load() }, [load])

    const handleTrain = async () => {
        setTraining(true)
        try {
            await apiFetch('research/train-models', { method: 'POST' })
            setTimeout(load, 3000)
        } catch (e) {
            console.error('train failed:', e)
        } finally {
            setTimeout(() => setTraining(false), 2000)
        }
    }

    const chartData = data.map(m => ({
        name: m.model_name,
        RMSE: Math.round(m.val_rmse ?? 0),
        MAE: Math.round(m.val_mae ?? 0),
    }))

    return (
        <Card className="bg-gray-900/60 border-gray-700/50 h-full flex flex-col">
            <CardHeader className="pb-3 flex-shrink-0">
                <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                        <Brain className="h-5 w-5 text-blue-400" />
                        <CardTitle className="text-white text-base">ML Model Training Metrics</CardTitle>
                    </div>
                    <div className="flex items-center gap-2">
                        {status && (
                            <>
                                <StatusBadge ok={status.torch_available} label="PyTorch" />
                                <StatusBadge ok={status.sklearn_available} label="sklearn" />
                                <StatusBadge ok={status.models_trained} label="Trained" />
                            </>
                        )}
                        <Button size="sm" variant="ghost"
                            className="h-7 px-2 text-gray-400 hover:text-white"
                            onClick={handleTrain} disabled={training}>
                            <Play className={`h-3 w-3 mr-1 ${training ? 'animate-spin' : ''}`} />
                            {training ? 'Training…' : 'Train'}
                        </Button>
                        <Button size="sm" variant="ghost"
                            className="h-7 px-2 text-gray-400 hover:text-white"
                            onClick={load} disabled={loading}>
                            <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
                        </Button>
                    </div>
                </div>
                <CardDescription className="text-gray-400 text-xs mt-1">
                    Validation RMSE &amp; MAE (CFS) on 15% held-out GloFAS data — lower is better
                </CardDescription>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col gap-4 overflow-y-auto">
                {data.length === 0 ? (
                    <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
                        {loading ? 'Loading…' : 'No trained models yet — click Train to start.'}
                    </div>
                ) : (
                    <>
                        {/* Bar chart */}
                        <div className="h-48">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                    <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 11 }} />
                                    <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} />
                                    <Tooltip
                                        contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8 }}
                                        labelStyle={{ color: '#f9fafb' }}
                                        itemStyle={{ color: '#d1d5db' }} />
                                    <Legend wrapperStyle={{ color: '#9ca3af', fontSize: 11 }} />
                                    <Bar dataKey="RMSE" fill="#60a5fa" radius={[3, 3, 0, 0]} />
                                    <Bar dataKey="MAE" fill="#34d399" radius={[3, 3, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>

                        {/* Metrics table */}
                        <div className="overflow-x-auto">
                            <table className="w-full text-xs text-left">
                                <thead>
                                    <tr className="border-b border-gray-700">
                                        <th className="pb-2 text-gray-400 font-medium">Model</th>
                                        <th className="pb-2 text-gray-400 font-medium text-right">Val RMSE</th>
                                        <th className="pb-2 text-gray-400 font-medium text-right">Val MAE</th>
                                        <th className="pb-2 text-gray-400 font-medium text-right">Samples</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.map((m, i) => (
                                        <tr key={i} className="border-b border-gray-800/50">
                                            <td className="py-1.5">
                                                <span className="inline-block w-2 h-2 rounded-full mr-2"
                                                    style={{ background: MODEL_COLORS[m.model_name] ?? '#6b7280' }} />
                                                <span className="text-gray-200 font-mono">{m.model_name}</span>
                                            </td>
                                            <td className="py-1.5 text-right">
                                                <MetricBadge value={m.val_rmse} good={(m.val_rmse ?? 999) < 80000} />
                                            </td>
                                            <td className="py-1.5 text-right">
                                                <MetricBadge value={m.val_mae} good={(m.val_mae ?? 999) < 50000} />
                                            </td>
                                            <td className="py-1.5 text-right text-gray-400">
                                                {m.n_samples?.toLocaleString() ?? '—'}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        {/* Feature importance (RF only) */}
                        {(() => {
                            const rf = data.find(m => m.model_name === 'random_forest')
                            const fi = rf?.feature_importances
                            if (!fi) return null
                            const sorted = Object.entries(fi).sort((a, b) => b[1] - a[1]).slice(0, 6)
                            return (
                                <div>
                                    <p className="text-xs text-gray-400 mb-2 font-medium">
                                        Top Feature Importances (Random Forest)
                                    </p>
                                    <div className="space-y-1">
                                        {sorted.map(([feat, imp]) => (
                                            <div key={feat} className="flex items-center gap-2">
                                                <span className="text-xs text-gray-400 w-36 truncate">{feat}</span>
                                                <div className="flex-1 bg-gray-800 rounded-full h-1.5">
                                                    <div className="bg-amber-400 h-1.5 rounded-full"
                                                        style={{ width: `${imp * 100}%` }} />
                                                </div>
                                                <span className="text-xs text-gray-400 w-10 text-right">
                                                    {(imp * 100).toFixed(1)}%
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )
                        })()}
                    </>
                )}
            </CardContent>
        </Card>
    )
}

// ---------------------------------------------------------------------------
// Panel 2: Validation & Baseline Comparison
// ---------------------------------------------------------------------------
function ValidationPanel() {
    const [horizon, setHorizon] = useState('24')
    const [rows, setRows] = useState<ValidationRow[]>([])
    const [skillScores, setSkillScores] = useState<Record<string, number>>({})
    const [sigSummary, setSigSummary] = useState<Record<string, string | number>>({})
    const [loading, setLoading] = useState(false)

    const load = useCallback(async () => {
        setLoading(true)
        try {
            const data = await apiFetch<{
                comparison_table: ValidationRow[]
                skill_scores: Record<string, number>
                significance_summary: Record<string, string | number>
            }>(`research/baselines?horizon=${horizon}`)
            setRows(data.comparison_table || [])
            setSkillScores(data.skill_scores || {})
            setSigSummary(data.significance_summary || {})
        } catch (e) {
            console.error('baselines fetch failed:', e)
        } finally {
            setLoading(false)
        }
    }, [horizon])

    useEffect(() => { load() }, [load])

    const chartData = rows.map(r => ({
        name: r.Model,
        RMSE: r['RMSE (CFS)'],
        NSE: Math.round((r.NSE ?? 0) * 1000) / 10,   // NSE → % for readability
        F1: Math.round((r.F1 ?? 0) * 1000) / 10,
        skill: Math.round((skillScores[r.Model] ?? 0) * 100),
    }))

    return (
        <Card className="bg-gray-900/60 border-gray-700/50 h-full flex flex-col">
            <CardHeader className="pb-3 flex-shrink-0">
                <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                        <GitCompare className="h-5 w-5 text-purple-400" />
                        <CardTitle className="text-white text-base">Model vs Baseline Comparison</CardTitle>
                    </div>
                    <div className="flex items-center gap-2">
                        <Select value={horizon} onValueChange={setHorizon}>
                            <SelectTrigger className="w-24 h-7 text-xs bg-gray-800 border-gray-600 text-gray-200">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-gray-800 border-gray-600">
                                {HORIZON_OPTIONS.map(h => (
                                    <SelectItem key={h} value={h}
                                        className="text-gray-200 text-xs focus:bg-gray-700">
                                        {h}h horizon
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <Button size="sm" variant="ghost"
                            className="h-7 px-2 text-gray-400 hover:text-white"
                            onClick={load} disabled={loading}>
                            <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
                        </Button>
                    </div>
                </div>
                <CardDescription className="text-gray-400 text-xs mt-1">
                    India historical flood events (n=35, 2015-2024) • Wilcoxon p&lt;0.05 significance
                </CardDescription>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col gap-4 overflow-y-auto">
                {loading && rows.length === 0 ? (
                    <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">Loading…</div>
                ) : (
                    <>
                        {/* Skill scores bar */}
                        {Object.keys(skillScores).length > 0 && (
                            <div>
                                <p className="text-xs text-gray-400 mb-2 font-medium flex items-center gap-1">
                                    <Award className="h-3 w-3" /> Skill Score vs Persistence (higher = better)
                                </p>
                                <div className="space-y-1">
                                    {Object.entries(skillScores)
                                        .sort((a, b) => b[1] - a[1])
                                        .map(([name, ss]) => (
                                            <div key={name} className="flex items-center gap-2">
                                                <span className="text-xs font-mono w-28 truncate"
                                                    style={{ color: MODEL_COLORS[name] ?? '#9ca3af' }}>
                                                    {name}
                                                </span>
                                                <div className="flex-1 bg-gray-800 rounded-full h-2">
                                                    <div className="h-2 rounded-full transition-all"
                                                        style={{
                                                            width: `${Math.max(0, Math.min(100, ss * 100))}%`,
                                                            background: MODEL_COLORS[name] ?? '#6b7280',
                                                        }} />
                                                </div>
                                                <span className="text-xs font-mono w-10 text-right"
                                                    style={{ color: ss > 0 ? '#34d399' : '#f87171' }}>
                                                    {(ss * 100).toFixed(1)}%
                                                </span>
                                            </div>
                                        ))}
                                </div>
                            </div>
                        )}

                        {/* RMSE comparison chart */}
                        {chartData.length > 0 && (
                            <div className="h-44">
                                <p className="text-xs text-gray-400 mb-1 font-medium">RMSE (CFS) — lower is better</p>
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={chartData} layout="vertical"
                                        margin={{ top: 0, right: 8, left: 60, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" horizontal={false} />
                                        <XAxis type="number" tick={{ fill: '#9ca3af', fontSize: 10 }} />
                                        <YAxis dataKey="name" type="category"
                                            tick={{ fill: '#9ca3af', fontSize: 10 }} width={60} />
                                        <Tooltip
                                            contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8 }}
                                            labelStyle={{ color: '#f9fafb' }}
                                            itemStyle={{ color: '#d1d5db' }} />
                                        <Bar dataKey="RMSE" radius={[0, 3, 3, 0]}>
                                            {chartData.map((entry) => (
                                                <Cell key={entry.name}
                                                    fill={MODEL_COLORS[entry.name] ?? '#6b7280'} />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        )}

                        {/* Full metrics table */}
                        {rows.length > 0 && (
                            <div className="overflow-x-auto">
                                <table className="w-full text-xs text-left min-w-[480px]">
                                    <thead>
                                        <tr className="border-b border-gray-700">
                                            {['Model', 'RMSE', 'NSE', 'KGE', 'CSI', 'F1', 'Skill'].map(h => (
                                                <th key={h} className="pb-2 text-gray-400 font-medium text-right first:text-left">
                                                    {h}
                                                </th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {rows.map((r, i) => {
                                            const isML = ['lstm', 'gru', 'transformer', 'random_forest'].includes(r.Model)
                                            return (
                                                <tr key={i} className={`border-b border-gray-800/50 ${isML ? 'bg-blue-500/5' : ''}`}>
                                                    <td className="py-1.5">
                                                        <span className="inline-block w-2 h-2 rounded-full mr-1.5"
                                                            style={{ background: MODEL_COLORS[r.Model] ?? '#6b7280' }} />
                                                        <span className={`font-mono ${isML ? 'text-blue-300' : 'text-gray-300'}`}>
                                                            {r.Model}
                                                        </span>
                                                    </td>
                                                    <td className="py-1.5 text-right font-mono text-gray-300">
                                                        {r['RMSE (CFS)']?.toLocaleString() ?? '—'}
                                                    </td>
                                                    <td className="py-1.5 text-right">
                                                        <MetricBadge value={r.NSE} good={(r.NSE ?? 0) > 0.7} />
                                                    </td>
                                                    <td className="py-1.5 text-right">
                                                        <MetricBadge value={r.KGE} good={(r.KGE ?? 0) > 0.6} />
                                                    </td>
                                                    <td className="py-1.5 text-right">
                                                        <MetricBadge value={r.CSI} good={(r.CSI ?? 0) > 0.5} />
                                                    </td>
                                                    <td className="py-1.5 text-right">
                                                        <MetricBadge value={r.F1} good={(r.F1 ?? 0) > 0.6} />
                                                    </td>
                                                    <td className="py-1.5 text-right">
                                                        <MetricBadge
                                                            value={skillScores[r.Model] !== undefined
                                                                ? Math.round(skillScores[r.Model] * 1000) / 1000
                                                                : undefined}
                                                            good={(skillScores[r.Model] ?? -1) > 0} />
                                                    </td>
                                                </tr>
                                            )
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        )}

                        {/* Significance summary */}
                        {sigSummary.interpretation && (
                            <div className="rounded-lg bg-purple-500/10 border border-purple-500/20 p-3">
                                <p className="text-xs text-purple-300 leading-relaxed">
                                    <strong className="text-purple-200">Statistical Significance: </strong>
                                    {sigSummary.interpretation as string}
                                </p>
                            </div>
                        )}
                    </>
                )}
            </CardContent>
        </Card>
    )
}

// ---------------------------------------------------------------------------
// Panel 3: LLM Ablation Study
// ---------------------------------------------------------------------------
function AblationPanel() {
    const [data, setData] = useState<{
        condition_scores: Record<string, AblationCondition>
        llm_contribution_delta: Record<string, number>
        paper_table: Array<Record<string, string | number>>
        interpretation: Record<string, string>
        category_breakdown: Record<string, Record<string, number>>
    } | null>(null)
    const [loading, setLoading] = useState(false)
    const [running, setRunning] = useState(false)

    const load = useCallback(async () => {
        setLoading(true)
        try {
            const hist = await apiFetch<{ summary_by_condition: AblationCondition[] }>(
                'research/ablation/history')
            if (hist.summary_by_condition?.length) {
                // Build a minimal display object from history
                const conds: Record<string, AblationCondition> = {}
                for (const row of hist.summary_by_condition) {
                    conds[(row as unknown as Record<string, string>).condition] = row
                }
                setData({
                    condition_scores: conds,
                    llm_contribution_delta: {},
                    paper_table: [],
                    interpretation: {},
                    category_breakdown: {},
                })
            }
        } catch (e) {
            console.error('ablation history fetch failed:', e)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => { load() }, [load])

    const handleRun = async () => {
        setRunning(true)
        try {
            const result = await apiFetch<typeof data>('research/ablation', {
                method: 'POST',
                body: JSON.stringify({ n_queries: 10 }),
            })
            setData(result)
        } catch (e) {
            console.error('ablation run failed:', e)
        } finally {
            setRunning(false)
        }
    }

    const dimensions = ['factual_accuracy', 'actionability', 'safety_compliance', 'specificity', 'overall_score']
    const dimLabels: Record<string, string> = {
        factual_accuracy: 'Factual',
        actionability: 'Actionable',
        safety_compliance: 'Safety',
        specificity: 'Specific',
        overall_score: 'Overall',
    }

    const radarData = dimensions.slice(0, 4).map(d => {
        const entry: Record<string, string | number> = { dimension: dimLabels[d] }
        if (data?.condition_scores) {
            for (const [cond, scores] of Object.entries(data.condition_scores)) {
                entry[cond] = Math.round((scores[d as keyof AblationCondition] ?? 0) * 100)
            }
        }
        return entry
    })

    return (
        <Card className="bg-gray-900/60 border-gray-700/50 h-full flex flex-col">
            <CardHeader className="pb-3 flex-shrink-0">
                <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                        <FlaskConical className="h-5 w-5 text-green-400" />
                        <CardTitle className="text-white text-base">LLM Ablation Study</CardTitle>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button size="sm" variant="ghost"
                            className="h-7 px-2 text-gray-400 hover:text-white"
                            onClick={handleRun} disabled={running || loading}>
                            <Play className={`h-3 w-3 mr-1 ${running ? 'animate-spin' : ''}`} />
                            {running ? 'Running…' : 'Run (10 queries)'}
                        </Button>
                        <Button size="sm" variant="ghost"
                            className="h-7 px-2 text-gray-400 hover:text-white"
                            onClick={load} disabled={loading}>
                            <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
                        </Button>
                    </div>
                </div>
                <CardDescription className="text-gray-400 text-xs mt-1">
                    rule_only vs llm_enhanced vs llm_only — 25 flood queries, 4 scoring dimensions
                </CardDescription>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col gap-4 overflow-y-auto">
                {!data ? (
                    <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
                        {loading || running ? 'Loading…' : 'No ablation data — click Run to start.'}
                    </div>
                ) : (
                    <>
                        {/* Radar chart */}
                        {radarData.length > 0 && Object.keys(data.condition_scores).length > 0 && (
                            <div className="h-52">
                                <ResponsiveContainer width="100%" height="100%">
                                    <RadarChart data={radarData}>
                                        <PolarGrid stroke="#374151" />
                                        <PolarAngleAxis dataKey="dimension"
                                            tick={{ fill: '#9ca3af', fontSize: 11 }} />
                                        <PolarRadiusAxis angle={30} domain={[0, 100]}
                                            tick={{ fill: '#6b7280', fontSize: 9 }} />
                                        {Object.keys(data.condition_scores).map(cond => (
                                            <Radar key={cond} name={cond}
                                                dataKey={cond}
                                                stroke={CONDITION_COLORS[cond] ?? '#6b7280'}
                                                fill={CONDITION_COLORS[cond] ?? '#6b7280'}
                                                fillOpacity={0.15} />
                                        ))}
                                        <Legend wrapperStyle={{ color: '#9ca3af', fontSize: 11 }} />
                                        <Tooltip
                                            contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8 }}
                                            formatter={(v: number) => `${v}%`} />
                                    </RadarChart>
                                </ResponsiveContainer>
                            </div>
                        )}

                        {/* Condition scores table */}
                        <div className="overflow-x-auto">
                            <table className="w-full text-xs">
                                <thead>
                                    <tr className="border-b border-gray-700">
                                        <th className="pb-2 text-gray-400 font-medium text-left">Condition</th>
                                        {dimensions.map(d => (
                                            <th key={d} className="pb-2 text-gray-400 font-medium text-right">
                                                {dimLabels[d]}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {Object.entries(data.condition_scores).map(([cond, scores]) => (
                                        <tr key={cond} className="border-b border-gray-800/50">
                                            <td className="py-1.5">
                                                <span className="inline-block w-2 h-2 rounded-full mr-1.5"
                                                    style={{ background: CONDITION_COLORS[cond] ?? '#6b7280' }} />
                                                <span className="font-mono text-gray-200">
                                                    {cond.replace(/_/g, ' ')}
                                                </span>
                                            </td>
                                            {dimensions.map(d => (
                                                <td key={d} className="py-1.5 text-right">
                                                    <MetricBadge
                                                        value={scores[d as keyof AblationCondition]}
                                                        good={(scores[d as keyof AblationCondition] ?? 0) > 0.6} />
                                                </td>
                                            ))}
                                        </tr>
                                    ))}
                                    {/* Delta row */}
                                    {Object.keys(data.llm_contribution_delta).length > 0 && (
                                        <tr className="bg-green-500/5">
                                            <td className="py-1.5 text-green-400 font-mono font-medium">
                                                Δ LLM gain
                                            </td>
                                            {dimensions.map(d => {
                                                const delta = data.llm_contribution_delta[d] ?? 0
                                                return (
                                                    <td key={d} className="py-1.5 text-right font-mono"
                                                        style={{ color: delta >= 0 ? '#34d399' : '#f87171' }}>
                                                        {delta >= 0 ? '+' : ''}{delta.toFixed(3)}
                                                    </td>
                                                )
                                            })}
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>

                        {/* Interpretation */}
                        {data.interpretation?.llm_enhanced_vs_rule_only && (
                            <div className="rounded-lg bg-green-500/10 border border-green-500/20 p-3">
                                <p className="text-xs text-green-300 leading-relaxed">
                                    <strong className="text-green-200">LLM Contribution: </strong>
                                    {data.interpretation.llm_enhanced_vs_rule_only}
                                </p>
                            </div>
                        )}
                        {data.interpretation?.research_conclusion && (
                            <div className="rounded-lg bg-blue-500/10 border border-blue-500/20 p-3">
                                <p className="text-xs text-blue-300 leading-relaxed">
                                    <strong className="text-blue-200">Conclusion: </strong>
                                    {data.interpretation.research_conclusion}
                                </p>
                            </div>
                        )}
                    </>
                )}
            </CardContent>
        </Card>
    )
}

// ---------------------------------------------------------------------------
// Panel 4: Validation Metrics Table (multi-horizon)
// ---------------------------------------------------------------------------
function ValidationMetricsPanel() {
    const [data, setData] = useState<{
        comparison_tables: Record<string, ValidationRow[]>
        summary: Record<string, string | number>
        dataset: Record<string, string | number>
    } | null>(null)
    const [loading, setLoading] = useState(false)
    const [running, setRunning] = useState(false)
    const [horizon, setHorizon] = useState('24')

    const load = useCallback(async () => {
        setLoading(true)
        try {
            const report = await apiFetch<typeof data>('research/validation/report')
            setData(report)
        } catch (e) {
            console.error('validation report fetch failed:', e)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => { load() }, [load])

    const handleRunValidation = async () => {
        setRunning(true)
        try {
            await apiFetch('research/validation', { method: 'POST' })
            await load()
        } catch (e) {
            console.error('validation run failed:', e)
        } finally {
            setRunning(false)
        }
    }

    const rows: ValidationRow[] = data?.comparison_tables?.[`${horizon}h`] ?? []

    const nseChartData = rows.map(r => ({
        name: r.Model,
        NSE: Math.round((r.NSE ?? 0) * 1000) / 1000,
        F1: Math.round((r.F1 ?? 0) * 1000) / 1000,
        CSI: Math.round((r.CSI ?? 0) * 1000) / 1000,
    }))

    return (
        <Card className="bg-gray-900/60 border-gray-700/50 h-full flex flex-col">
            <CardHeader className="pb-3 flex-shrink-0">
                <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                        <BarChart3 className="h-5 w-5 text-amber-400" />
                        <CardTitle className="text-white text-base">Historical Validation</CardTitle>
                    </div>
                    <div className="flex items-center gap-2">
                        <Select value={horizon} onValueChange={setHorizon}>
                            <SelectTrigger className="w-24 h-7 text-xs bg-gray-800 border-gray-600 text-gray-200">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-gray-800 border-gray-600">
                                {HORIZON_OPTIONS.map(h => (
                                    <SelectItem key={h} value={h}
                                        className="text-gray-200 text-xs focus:bg-gray-700">
                                        {h}h horizon
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <Button size="sm" variant="ghost"
                            className="h-7 px-2 text-gray-400 hover:text-white"
                            onClick={handleRunValidation} disabled={running || loading}>
                            <Play className={`h-3 w-3 mr-1 ${running ? 'animate-spin' : ''}`} />
                            {running ? 'Validating…' : 'Run'}
                        </Button>
                        <Button size="sm" variant="ghost"
                            className="h-7 px-2 text-gray-400 hover:text-white"
                            onClick={load} disabled={loading}>
                            <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
                        </Button>
                    </div>
                </div>
                <CardDescription className="text-gray-400 text-xs mt-1">
                    {data?.dataset
                        ? `${data.dataset.name} — ${data.dataset.total_events} events, ${data.dataset.flood_events} floods`
                        : 'India flood events 2015-2024 (CWC/NDMA/IMD sources)'}
                </CardDescription>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col gap-4 overflow-y-auto">
                {loading && !data ? (
                    <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">Loading…</div>
                ) : (
                    <>
                        {/* NSE / F1 / CSI grouped chart */}
                        {nseChartData.length > 0 && (
                            <div className="h-44">
                                <p className="text-xs text-gray-400 mb-1 font-medium">
                                    NSE / F1 / CSI at {horizon}h horizon — higher is better
                                </p>
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={nseChartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                                        <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 10 }} />
                                        <YAxis domain={[0, 1]} tick={{ fill: '#9ca3af', fontSize: 10 }} />
                                        <Tooltip
                                            contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8 }}
                                            labelStyle={{ color: '#f9fafb' }}
                                            itemStyle={{ color: '#d1d5db' }} />
                                        <Legend wrapperStyle={{ color: '#9ca3af', fontSize: 11 }} />
                                        <Bar dataKey="NSE" fill="#60a5fa" radius={[3, 3, 0, 0]} />
                                        <Bar dataKey="F1" fill="#34d399" radius={[3, 3, 0, 0]} />
                                        <Bar dataKey="CSI" fill="#fbbf24" radius={[3, 3, 0, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        )}

                        {/* Metrics table */}
                        {rows.length > 0 ? (
                            <div className="overflow-x-auto">
                                <table className="w-full text-xs min-w-[520px]">
                                    <thead>
                                        <tr className="border-b border-gray-700">
                                            {['Model', 'RMSE', 'MAE', 'NSE', 'KGE', 'POD', 'FAR', 'F1'].map(h => (
                                                <th key={h}
                                                    className="pb-2 text-gray-400 font-medium text-right first:text-left">
                                                    {h}
                                                </th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {rows.map((r, i) => {
                                            const isML = ['lstm', 'gru', 'transformer', 'random_forest'].includes(r.Model)
                                            return (
                                                <tr key={i} className={`border-b border-gray-800/50 ${isML ? 'bg-blue-500/5' : ''}`}>
                                                    <td className="py-1.5">
                                                        <span className="inline-block w-2 h-2 rounded-full mr-1.5"
                                                            style={{ background: MODEL_COLORS[r.Model] ?? '#6b7280' }} />
                                                        <span className={`font-mono ${isML ? 'text-blue-300' : 'text-gray-300'}`}>
                                                            {r.Model}
                                                        </span>
                                                    </td>
                                                    <td className="py-1.5 text-right font-mono text-gray-300">
                                                        {r['RMSE (CFS)']?.toLocaleString() ?? '—'}
                                                    </td>
                                                    <td className="py-1.5 text-right font-mono text-gray-300">
                                                        {r['MAE (CFS)']?.toLocaleString() ?? '—'}
                                                    </td>
                                                    <td className="py-1.5 text-right">
                                                        <MetricBadge value={r.NSE} good={(r.NSE ?? 0) > 0.7} />
                                                    </td>
                                                    <td className="py-1.5 text-right">
                                                        <MetricBadge value={r.KGE} good={(r.KGE ?? 0) > 0.6} />
                                                    </td>
                                                    <td className="py-1.5 text-right">
                                                        <MetricBadge value={r.POD} good={(r.POD ?? 0) > 0.7} />
                                                    </td>
                                                    <td className="py-1.5 text-right">
                                                        <MetricBadge value={r.FAR} good={(r.FAR ?? 1) < 0.3} />
                                                    </td>
                                                    <td className="py-1.5 text-right">
                                                        <MetricBadge value={r.F1} good={(r.F1 ?? 0) > 0.65} />
                                                    </td>
                                                </tr>
                                            )
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        ) : (
                            <div className="text-gray-500 text-sm text-center py-4">
                                No validation data for {horizon}h — click Run to compute.
                            </div>
                        )}

                        {/* Summary */}
                        {data?.summary?.best_model_24h && (
                            <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 p-3 space-y-1">
                                <p className="text-xs text-amber-300">
                                    <strong className="text-amber-200">Best model @ 24h: </strong>
                                    <span className="font-mono">{String(data.summary.best_model_24h)}</span>
                                    {' '}(RMSE={String(data.summary.best_rmse_cfs)} CFS, NSE={String(data.summary.best_nse)})
                                </p>
                                {(data.summary as unknown as Record<string, Record<string, number>>)
                                    .improvement_over_rule_based?.rmse_reduction_pct !== undefined && (
                                    <p className="text-xs text-amber-300">
                                        <strong className="text-amber-200">vs Rule-based: </strong>
                                        {(data.summary as unknown as Record<string, Record<string, number>>)
                                            .improvement_over_rule_based.rmse_reduction_pct}% RMSE reduction,{' '}
                                        +{(data.summary as unknown as Record<string, Record<string, number>>)
                                            .improvement_over_rule_based.f1_gain} F1 gain
                                    </p>
                                )}
                            </div>
                        )}
                    </>
                )}
            </CardContent>
        </Card>
    )
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------
export default function ResearchDashboard() {
    return (
        <div className="h-full w-full overflow-y-auto p-4 space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                    <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                        <Layers className="h-5 w-5 text-blue-400" />
                        Research Dashboard
                    </h2>
                    <p className="text-xs text-gray-400 mt-0.5">
                        ML model metrics · baseline comparisons · LLM ablation · historical validation
                        — all results are reproducible and citable
                    </p>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                    <Badge className="bg-blue-500/20 text-blue-300 border border-blue-500/30 text-xs">
                        <TrendingUp className="h-3 w-3 mr-1" />
                        LSTM / GRU / Transformer / RF
                    </Badge>
                    <Badge className="bg-purple-500/20 text-purple-300 border border-purple-500/30 text-xs">
                        <GitCompare className="h-3 w-3 mr-1" />
                        5 Baselines + Wilcoxon
                    </Badge>
                    <Badge className="bg-green-500/20 text-green-300 border border-green-500/30 text-xs">
                        <FlaskConical className="h-3 w-3 mr-1" />
                        3-Condition Ablation
                    </Badge>
                    <Badge className="bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs">
                        <Clock className="h-3 w-3 mr-1" />
                        35 India Flood Events
                    </Badge>
                </div>
            </div>

            {/* 2×2 grid of panels */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" style={{ minHeight: 600 }}>
                <ModelMetricsPanel />
                <ValidationPanel />
                <AblationPanel />
                <ValidationMetricsPanel />
            </div>

            {/* Footer note */}
            <p className="text-xs text-gray-600 text-center pb-2">
                Data sources: CWC Annual Flood Reports 2015-2024 · NDMA Situation Reports · IMD Hydrometeorological Bulletins ·
                Open-Meteo GloFAS · Wilcoxon signed-rank tests with Cohen's d effect sizes
            </p>
        </div>
    )
}
