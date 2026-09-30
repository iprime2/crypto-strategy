import { lazy, Suspense, type ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { Empty } from './components/kit'
import { AppProvider } from './context/AppContext'

const TradePage = lazy(() => import('./pages/TradePage').then((m) => ({ default: m.TradePage })))
const PerformancePage = lazy(() => import('./pages/PerformancePage').then((m) => ({ default: m.PerformancePage })))
const BlotterPage = lazy(() => import('./pages/BlotterPage').then((m) => ({ default: m.BlotterPage })))
const RiskPage = lazy(() => import('./pages/RiskPage').then((m) => ({ default: m.RiskPage })))
const StrategyPage = lazy(() => import('./pages/StrategyPage').then((m) => ({ default: m.StrategyPage })))

const page = (el: ReactNode) => <Suspense fallback={<Empty>Loading…</Empty>}>{el}</Suspense>

export default function App() {
  return (
    <BrowserRouter>
      <AppProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={page(<TradePage />)} />
            <Route path="performance" element={page(<PerformancePage />)} />
            <Route path="blotter" element={page(<BlotterPage />)} />
            <Route path="risk" element={page(<RiskPage />)} />
            <Route path="strategy" element={page(<StrategyPage />)} />
            {/* Old routes from the previous UI */}
            <Route path="positions" element={<Navigate to="/risk" replace />} />
            <Route path="reconcile" element={<Navigate to="/risk" replace />} />
            <Route path="orders" element={<Navigate to="/blotter" replace />} />
            <Route path="tca" element={<Navigate to="/performance" replace />} />
            <Route path="control" element={<Navigate to="/strategy" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </AppProvider>
    </BrowserRouter>
  )
}
