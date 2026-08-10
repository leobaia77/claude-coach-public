import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useSession } from './authClient'
import { getMe } from './coachApi'
import { Login, Signup } from './pages/Auth'
import { Onboarding } from './pages/Onboarding'
import { Dashboard } from './pages/Dashboard'
import { Settings } from './pages/Settings'
import { Admin } from './pages/Admin'

// Gate authed routes on the session; route unonboarded users into the wizard.
function Protected({ children, requireOnboarded = true }: { children: React.ReactNode; requireOnboarded?: boolean }) {
  const { data: session, isPending } = useSession()
  const loc = useLocation()
  const [stage, setStage] = useState<string | null>(null)
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    if (session?.user) {
      getMe().then((m) => setStage(m.user.onboardingStage)).catch(() => setStage(null)).finally(() => setChecked(true))
    } else if (!isPending) {
      setChecked(true)
    }
  }, [session, isPending])

  if (isPending || !checked) return <div className="page"><p>Loading…</p></div>
  if (!session?.user) return <Navigate to="/login" state={{ from: loc }} replace />
  if (requireOnboarded && stage && stage !== 'done') return <Navigate to="/onboarding" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/onboarding" element={<Protected requireOnboarded={false}><Onboarding /></Protected>} />
        <Route path="/settings" element={<Protected requireOnboarded={false}><Settings /></Protected>} />
        <Route path="/admin" element={<Protected requireOnboarded={false}><Admin /></Protected>} />
        <Route path="/" element={<Protected><Dashboard /></Protected>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
