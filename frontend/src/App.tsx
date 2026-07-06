import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { GoalNew } from '@/pages/GoalNew'
import { GoalDetail } from '@/pages/GoalDetail'

const queryClient = new QueryClient()

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <Link to="/goals/new" className="text-base font-semibold">
            NexTrade
          </Link>
          <span className="text-xs text-muted-foreground">Financial Advisor</span>
        </div>
      </header>
      {children}
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Navigate to="/goals/new" replace />} />
            <Route path="/goals/new" element={<GoalNew />} />
            <Route path="/goals/:id" element={<GoalDetail />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
