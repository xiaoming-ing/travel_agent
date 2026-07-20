<script setup lang="ts">
import { onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import AMapLoader from '@amap/amap-jsapi-loader'
import type { Attraction, Hotel } from '../../types'

const props = defineProps<{
  attractions: Attraction[]
  hotels?: Hotel[]
}>()

const mapContainer = ref<HTMLDivElement | null>(null)
const errorMsg = ref<string | null>(null)
const mapInstance = shallowRef<any>(null)
const amapRef = shallowRef<any>(null)     // 存 AMap 命名空间，drawOverlays 里用

// 绘制覆盖物：marker + polyline。抽出来供 onMounted 和 watch 复用
function drawOverlays() {
  const map = mapInstance.value
  const AMap = amapRef.value
  if (!map || !AMap) return

  map.clearMap()

  // 景点 markers：过滤掉无坐标的，但编号保持和原 attractions 数组一致
  const attractionMarkers = props.attractions
    .map((a, idx) => ({ a, idx }))
    .filter(({ a }) => a.longitude && a.latitude)   // ← 过滤 (0,0)
    .map(({ a, idx }) => {
      return new AMap.Marker({
        position: [a.longitude, a.latitude],
        content: `<div class="amap-num-marker">${idx + 1}</div>`,
        offset: new AMap.Pixel(-14, -14),
        title: a.name,
      })
    })

  // 路径连线：同样过滤无坐标的点
  const validPath = props.attractions
    .filter((a) => a.longitude && a.latitude)
    .map((a) => [a.longitude, a.latitude])
  const polyline = new AMap.Polyline({
    path: validPath,
    strokeColor: '#1f6f78',
    strokeWeight: 4,
    strokeOpacity: 0.7,
    lineJoin: 'round',
  })

  // 酒店 markers：原本就有 filter，保持
  const hotelMarkers = (props.hotels ?? [])
    .filter((h) => h.longitude && h.latitude)
    .map((h, idx) => {
      return new AMap.Marker({
        position: [h.longitude, h.latitude],
        content: `<div class="amap-hotel-marker">H${idx + 1}</div>`,
        offset: new AMap.Pixel(-14, -14),
        title: `${h.name}  ${h.rating}  ${h.price_range}`,
      })
    })

  map.add([...attractionMarkers, ...hotelMarkers, polyline])
  map.setFitView()
}


onMounted(async () => {
  try {
    const AMap = await AMapLoader.load({
      key: import.meta.env.VITE_AMAP_KEY,
      version: '2.0',
      plugins: ['AMap.Polyline'],
    })
    amapRef.value = AMap

    if (!mapContainer.value) return
    const map = new AMap.Map(mapContainer.value, { zoom: 11, viewMode: '2D' })
    mapInstance.value = map

    drawOverlays()
  } catch (e: any) {
    errorMsg.value = `地图加载失败：${e.message || '未知错误'}`
    console.error('[AttractionMap]', e)
  }
})

// 关键：props 变化时重绘地图
watch(
  () => [props.attractions, props.hotels],
  () => drawOverlays(),
  { deep: true },
)

onUnmounted(() => {
  mapInstance.value?.destroy?.()
})
</script>


<template>
  <div class="map-card">
    <div class="card-header">景点地图</div>
    <div class="map-body">
      <div v-if="errorMsg" class="error">{{ errorMsg }}</div>
      <div v-else ref="mapContainer" class="map-container"></div>
    </div>
  </div>
</template>

<!-- 编号 marker 用的样式必须是全局的，不能用 scoped，因为 AMap 在外部 DOM 里渲染 content -->
<style>
.amap-num-marker {
  width: 28px;
  height: 28px;
  line-height: 28px;
  border-radius: 50%;
  background: #1f6f78;
  color: #fff;
  text-align: center;
  font-weight: 700;
  font-size: 14px;
  border: 2px solid #fff;
  box-shadow: 0 2px 6px rgba(0,0,0,0.3);
}

.amap-hotel-marker {
  width: 28px;
  height: 28px;
  line-height: 28px;
  border-radius: 50%;
  background: #c44e2d;
  color: #fff;
  text-align: center;
  font-weight: 700;
  font-size: 13px;
  border: 2px solid #fff;
  box-shadow: 0 2px 6px rgba(0,0,0,0.3);
}

</style>

<style scoped>
.map-card {
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  overflow: hidden;
  box-shadow: var(--shadow-soft);
}
.card-header {
  color: var(--color-ink);
  padding: 16px 20px 12px;
  font-size: 18px;
  font-weight: 750;
  border-bottom: 1px solid var(--color-border);
}
.map-body {
  padding: 16px;
}
.map-container {
  width: 100%;
  height: 400px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--color-border);
}
.error {
  padding: 40px;
  text-align: center;
  color: var(--color-signal);
  background: #f8e7e0;
  border-radius: 8px;
}
</style>
