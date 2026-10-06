import type { Level } from '@/components/kit'

/** Typed confirmation the OEMS requires to start a real-money (mainnet) strategy. */
export const MAINNET_CONFIRM = 'START REAL'

/**
 * DISM pilot gate, from the shadow test (cex-mm/artifacts/research/2026-10-05-dism-gate-six-coins.md):
 * ADA at fair ±5 bps netted +1.90 bps per fill at 60 s after fees over 4,117 simulated fills.
 * Live uses the same rule as the shadow gate: judge after 300 fills, stop below zero.
 */
export const PILOT = {
  shadowNet60Bps: 1.9,
  gateFills: 300,
  passBps: 0.5,
} as const

export type PilotVerdict = { level: Level; label: string; detail: string }

export function pilotVerdict(fills: number, net60Bps: number | null | undefined): PilotVerdict {
  if (fills < PILOT.gateFills || net60Bps === null || net60Bps === undefined) {
    return { level: 'idle', label: 'Collecting', detail: `${fills} of ${PILOT.gateFills} fills scored` }
  }
  const net = `${net60Bps >= 0 ? '+' : ''}${net60Bps.toFixed(2)} bps`
  if (net60Bps < 0) return { level: 'bad', label: 'Stop', detail: `${net} per fill after ${fills} fills: below zero` }
  if (net60Bps >= PILOT.passBps) return { level: 'ok', label: 'Pass', detail: `${net} per fill after ${fills} fills` }
  return { level: 'warn', label: 'Inconclusive', detail: `${net} per fill: positive but under +${PILOT.passBps} bps` }
}
