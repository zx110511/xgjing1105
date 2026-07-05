import { Component, ReactNode } from 'react'
import { Result, Button } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[ErrorBoundary]', error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback
      return (
        <Result
          status="error"
          title="页面渲染异常"
          subTitle={this.state.error?.message || '未知错误'}
          extra={[
            <Button type="primary" icon={<ReloadOutlined />} onClick={this.handleReset} key="retry">
              重试加载
            </Button>,
            <Button key="home" onClick={() => window.location.href = '/dashboard'}>
              返回首页
            </Button>,
          ]}
        />
      )
    }
    return this.props.children
  }
}

export default ErrorBoundary
