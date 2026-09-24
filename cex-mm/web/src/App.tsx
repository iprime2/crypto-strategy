import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Toaster } from '@/components/ui/toaster'
import { Layout } from './components/Layout'
import { StrategyProvider } from './context/StrategyContext'
import { ControlPage } from './pages/ControlPage'
import { OrdersPage } from './pages/OrdersPage'
import { OverviewPage } from './pages/OverviewPage'
import { PositionsPage } from './pages/PositionsPage'
import { ReconcilePage } from './pages/ReconcilePage'
import { TcaPage } from './pages/TcaPage'

export default function App() {
  return (
    <BrowserRouter>
      <StrategyProvider>
        <Toaster />
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<OverviewPage />} />
            <Route path="positions" element={<PositionsPage />} />
            <Route path="orders" element={<OrdersPage />} />
            <Route path="reconcile" element={<ReconcilePage />} />
            <Route path="tca" element={<TcaPage />} />
            <Route path="control" element={<ControlPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </StrategyProvider>
    </BrowserRouter>
  )
}
