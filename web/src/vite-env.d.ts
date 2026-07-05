/// <reference types="vite/client" />

// [FIX-TS-001] 解决 import.meta.env 类型缺失 (api.config.ts/api.ts/error-handler.ts)
interface ImportMetaEnv {
    readonly DEV: boolean
    readonly PROD: boolean
    readonly MODE: string
    readonly BASE_URL: string
    readonly SSR: boolean
    readonly VITE_API_BASE_URL?: string
    readonly VITE_API_TIMEOUT?: string
    readonly VITE_WS_BASE_URL?: string
}

interface ImportMeta {
    readonly env: ImportMetaEnv
}

// [FIX-TS-002] 解决 __TAURI_INTERNALS__ 类型缺失 (api.config.ts)
interface Window {
    __TAURI_INTERNALS__?: {
        convertFileSrc: (filePath: string, protocol?: string) => string
        invoke: <T = unknown>(cmd: string, args?: Record<string, unknown>) => Promise<T>
    }
}

// [FIX-TS-003] 解决 echarts 模块缺失 (Chart.tsx 使用 @ant-design/charts 内部依赖)
declare module 'echarts' {
    export interface EChartsOption {
        [key: string]: any
    }
    // [FIX-TS-016] 提供完整 ECharts 实例方法签名, 解决 chart.setOption/resize/dispose 报错
    export interface ECharts {
        setOption(option: EChartsOption, notMerge?: boolean): void
        resize(): void
        dispose(): void
        getOption(): EChartsOption
        showLoading(type?: string, opts?: any): void
        hideLoading(): void
    }
    export const init: (el: HTMLElement, theme?: string, opts?: any) => ECharts
    export const connect: (group: string | ECharts[]) => void
    export const disposeAll: () => void
    const _default: { init: typeof init; connect: typeof connect }
    export default _default
}
