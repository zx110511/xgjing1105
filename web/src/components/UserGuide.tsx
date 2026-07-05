import React, { useState, useEffect } from 'react'
import { Modal, Button, Steps, Card, Typography, Space, Switch, message } from 'antd'
import {
  HomeOutlined,
  DatabaseOutlined,
  SearchOutlined,
  SettingOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons'
import { useLocalStorage } from '../hooks/useLocalStorage'

const { Title, Paragraph, Text } = Typography
const { Step } = Steps

interface UserGuideProps {
  visible: boolean
  onClose: () => void
  onComplete?: () => void
}

interface GuideStep {
  title: string
  description: string
  icon: React.ReactNode
  content: React.ReactNode
}

const UserGuide: React.FC<UserGuideProps> = ({ visible, onClose, onComplete }) => {
  const [currentStep, setCurrentStep] = useState(0)
  const [showOnStartup, setShowOnStartup] = useLocalStorage('show-user-guide', true)
  const setCompleted = useLocalStorage('user-guide-completed', false)[1]

  const guideSteps: GuideStep[] = [
    {
      title: '欢迎',
      description: '欢迎使用天机v9.1',
      icon: <HomeOutlined />,
      content: (
        <div style={{ padding: '24px 0' }}>
          <Title level={3}>🎉 欢迎使用天机v9.1</Title>
          <Paragraph>天机v9.1是智能记忆平台，帮助您存储、检索和管理记忆信息。</Paragraph>
          <Paragraph>本向导将带您了解系统的核心功能，帮助您快速上手。</Paragraph>
          <Card style={{ marginTop: 16, background: '#f5f5f5' }}>
            <Title level={5}>系统特点</Title>
            <ul>
              <li>
                📝 <Text>ICME六层记忆架构</Text>
              </li>
              <li>
                🔍 <Text>智能语义搜索</Text>
              </li>
              <li>
                📊 <Text>知识图谱可视化</Text>
              </li>
              <li>
                🤖 <Text>LLM深度集成</Text>
              </li>
            </ul>
          </Card>
        </div>
      ),
    },
    {
      title: '记忆管理',
      description: '创建和管理记忆',
      icon: <DatabaseOutlined />,
      content: (
        <div style={{ padding: '24px 0' }}>
          <Title level={3}>📚 记忆管理</Title>
          <Paragraph>记忆管理是系统的核心功能，您可以创建、编辑、删除和搜索记忆。</Paragraph>
          <Card style={{ marginTop: 16 }}>
            <Title level={5}>核心操作</Title>
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Text strong>创建记忆:</Text>
                <Text type="secondary"> 点击"新建"按钮，填写内容、层级、优先级等信息</Text>
              </div>
              <div>
                <Text strong>编辑记忆:</Text>
                <Text type="secondary"> 点击记忆条目的"编辑"按钮进行修改</Text>
              </div>
              <div>
                <Text strong>删除记忆:</Text>
                <Text type="secondary"> 支持单个删除和批量删除</Text>
              </div>
              <div>
                <Text strong>记忆层级:</Text>
                <Text type="secondary">
                  {' '}
                  Sensory → Working → Short-term → Episodic → Semantic → Meta
                </Text>
              </div>
            </Space>
          </Card>
        </div>
      ),
    },
    {
      title: '智能搜索',
      description: '语义搜索与过滤',
      icon: <SearchOutlined />,
      content: (
        <div style={{ padding: '24px 0' }}>
          <Title level={3}>🔍 智能搜索</Title>
          <Paragraph>系统提供强大的搜索功能，支持关键词搜索、语义搜索和高级过滤。</Paragraph>
          <Card style={{ marginTop: 16 }}>
            <Title level={5}>搜索功能</Title>
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Text strong>关键词搜索:</Text>
                <Text type="secondary"> 输入关键词快速查找相关记忆</Text>
              </div>
              <div>
                <Text strong>语义搜索:</Text>
                <Text type="secondary"> 基于向量相似度的智能搜索</Text>
              </div>
              <div>
                <Text strong>高级过滤:</Text>
                <Text type="secondary"> 按层级、优先级、标签、时间等条件筛选</Text>
              </div>
              <div>
                <Text strong>搜索历史:</Text>
                <Text type="secondary"> 自动保存搜索记录，快速重复搜索</Text>
              </div>
            </Space>
          </Card>
        </div>
      ),
    },
    {
      title: '系统配置',
      description: '个性化设置',
      icon: <SettingOutlined />,
      content: (
        <div style={{ padding: '24px 0' }}>
          <Title level={3}>⚙️ 系统配置</Title>
          <Paragraph>您可以根据个人需求配置系统参数，包括API密钥、记忆策略等。</Paragraph>
          <Card style={{ marginTop: 16 }}>
            <Title level={5}>配置选项</Title>
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Text strong>API密钥管理:</Text>
                <Text type="secondary"> 配置DeepSeek、OpenAI等LLM API密钥</Text>
              </div>
              <div>
                <Text strong>记忆策略:</Text>
                <Text type="secondary"> 设置记忆保留时间、自动归档规则</Text>
              </div>
              <div>
                <Text strong>界面设置:</Text>
                <Text type="secondary"> 自定义主题、语言、布局</Text>
              </div>
              <div>
                <Text strong>快捷键:</Text>
                <Text type="secondary"> 查看和自定义快捷键</Text>
              </div>
            </Space>
          </Card>
        </div>
      ),
    },
    {
      title: '开始使用',
      description: '创建第一条记忆',
      icon: <CheckCircleOutlined />,
      content: (
        <div style={{ padding: '24px 0' }}>
          <Title level={3}>🚀 开始使用</Title>
          <Paragraph>恭喜您完成了系统介绍！现在可以开始创建您的第一条记忆了。</Paragraph>
          <Card style={{ marginTop: 16, background: '#e6f7ff', borderColor: '#1890ff' }}>
            <Title level={5}>快速入门步骤</Title>
            <Steps direction="vertical" current={-1} size="small">
              <Step title="创建记忆" description={'点击「新建」按钮，创建您的第一条记忆'} />
              <Step title="添加标签" description="为记忆添加标签，方便后续检索" />
              <Step title="搜索测试" description="使用搜索功能查找刚创建的记忆" />
              <Step title="探索功能" description="尝试知识图谱、数据统计等高级功能" />
            </Steps>
          </Card>
          <div style={{ marginTop: 24 }}>
            <Space>
              <Switch checked={showOnStartup} onChange={setShowOnStartup} />
              <Text>下次启动时显示此向导</Text>
            </Space>
          </div>
        </div>
      ),
    },
  ]

  const handleNext = () => {
    if (currentStep < guideSteps.length - 1) {
      setCurrentStep(currentStep + 1)
    }
  }

  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1)
    }
  }

  const handleFinish = () => {
    setCompleted(true)
    message.success('引导完成，开始使用天机v9.1！')
    onComplete?.()
    onClose()
  }

  const handleSkip = () => {
    Modal.confirm({
      title: '跳过引导',
      content: '确定要跳过引导吗？您可以稍后在设置中重新查看。',
      okText: '确定',
      cancelText: '取消',
      onOk: () => {
        setCompleted(true)
        onClose()
      },
    })
  }

  useEffect(() => {
    if (visible) {
      setCurrentStep(0)
    }
  }, [visible])

  return (
    <Modal
      open={visible}
      onCancel={handleSkip}
      width={720}
      footer={null}
      closable={false}
      maskClosable={false}
    >
      <Steps current={currentStep} style={{ marginBottom: 24 }}>
        {guideSteps.map((step, index) => (
          <Step key={index} title={step.title} icon={step.icon} />
        ))}
      </Steps>

      <div style={{ minHeight: 300 }}>{guideSteps[currentStep].content}</div>

      <div style={{ marginTop: 24, textAlign: 'right' }}>
        <Space>
          {currentStep > 0 && <Button onClick={handlePrev}>上一步</Button>}
          {currentStep < guideSteps.length - 1 ? (
            <>
              <Button onClick={handleSkip}>跳过</Button>
              <Button type="primary" onClick={handleNext}>
                下一步
              </Button>
            </>
          ) : (
            <Button type="primary" onClick={handleFinish}>
              开始使用
            </Button>
          )}
        </Space>
      </div>
    </Modal>
  )
}

export default UserGuide

export const useUserGuide = () => {
  const [completed] = useLocalStorage('user-guide-completed', false)
  const [showOnStartup] = useLocalStorage('show-user-guide', true)

  return {
    completed,
    showOnStartup,
    shouldShow: !completed && showOnStartup,
  }
}
