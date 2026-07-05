import { Input, Select, Button, Space } from 'antd'
import { SearchOutlined, LoadingOutlined } from '@ant-design/icons'

interface KGSearchBarProps {
  searchQuery: string
  searchType: string | undefined
  searching: boolean
  onSearchChange: (value: string) => void
  onTypeChange: (value: string | undefined) => void
  onSearch: () => void
}

export function KGSearchBar({
  searchQuery,
  searchType,
  searching,
  onSearchChange,
  onTypeChange,
  onSearch,
}: KGSearchBarProps) {
  return (
    <Space.Compact style={{ width: '100%' }}>
      <Input
        placeholder="搜索实体/关系/路径..."
        value={searchQuery}
        onChange={(e) => onSearchChange(e.target.value)}
        onPressEnter={onSearch}
        allowClear
        style={{ flex: 1 }}
      />
      <Select
        value={searchType}
        onChange={onTypeChange}
        style={{ width: 120 }}
        placeholder="类型"
        allowClear
        options={[
          { value: 'node', label: '实体' },
          { value: 'edge', label: '关系' },
          { value: 'path', label: '路径' },
          { value: 'community', label: '社区' },
        ]}
      />
      <Button
        type="primary"
        icon={searching ? <LoadingOutlined /> : <SearchOutlined />}
        onClick={onSearch}
        loading={searching}
      >
        搜索
      </Button>
    </Space.Compact>
  )
}