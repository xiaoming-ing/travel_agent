declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  // 用 any 放宽三个泛型参数，覆盖 <script setup> 下的组件
  const component: DefineComponent<
    Record<string, any>,
    Record<string, any>,
    any
  >
  export default component
}

