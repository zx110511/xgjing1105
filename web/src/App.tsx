import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { Layout, Spin } from 'antd'
import MainLayout from './layouts/MainLayout'
import ErrorBoundary from './components/ErrorBoundary'
import './App.css'

const { Content } = Layout

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Chat = lazy(() => import('./pages/Chat'))
const MemoryManagement = lazy(() => import('./pages/MemoryManagement'))
const KnowledgeGraph = lazy(() => import('./pages/KnowledgeGraph'))
const SystemConfig = lazy(() => import('./pages/SystemConfig'))
const Monitoring = lazy(() => import('./pages/Monitoring'))
const MCPTools = lazy(() => import('./pages/MCPTools'))
const SSSAuditPanel = lazy(() => import('./pages/SSSAuditPanel'))
const StandardsCompliance = lazy(() => import('./pages/StandardsCompliance'))
const PipelineOrchestrator = lazy(() => import('./pages/PipelineOrchestrator'))
const DeepSeekDashboard = lazy(() => import('./pages/DeepSeekDashboard'))
const AuditDashboard = lazy(() => import('./pages/AuditDashboard'))

const PageLoading = () => (
  <div style={{ textAlign: 'center', padding: '100px 0' }}>
    <Spin size="large">
      <div style={{ padding: 20 }}>页面加载中...</div>
    </Spin>
  </div>
)

function App() {
  return (
    <ErrorBoundary>
      <Router>
        <MainLayout>
          <Content style={{ margin: '16px' }}>
            <ErrorBoundary>
              <Suspense fallback={<PageLoading />}>
                <Routes>
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/chat" element={<Chat />} />
                  <Route path="/memory" element={<MemoryManagement />} />
                  <Route path="/knowledge-graph" element={<KnowledgeGraph />} />
                  <Route path="/config" element={<SystemConfig />} />
                  <Route path="/monitoring" element={<Monitoring />} />
                  <Route path="/mcp-tools" element={<MCPTools />} />
                  <Route path="/sss-audit" element={<SSSAuditPanel />} />
                  <Route path="/standards" element={<StandardsCompliance />} />
                  <Route path="/orchestrator" element={<PipelineOrchestrator />} />
                  <Route path="/audit" element={<AuditDashboard />} />
                  <Route path="/deepseek" element={<DeepSeekDashboard />} />
                </Routes>
              </Suspense>
            </ErrorBoundary>
          </Content>
        </MainLayout>
      </Router>
    </ErrorBoundary>
  )
}

export default App
