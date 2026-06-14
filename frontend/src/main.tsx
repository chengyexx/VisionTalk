import { createRoot } from 'react-dom/client'
import { ErrorBoundary } from './components/ErrorBoundary'
import './index.css'
import App from './App.tsx'

// React 18 StrictMode 在开发环境会导致双挂载 (mount → unmount → mount)，
// 这会触发 useWebSocket 的 cleanup 关闭连接，导致 WebSocket "closed before established"。
// 生产环境无此问题，开发期间关闭即可。
createRoot(document.getElementById('root')!).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>,
)
