<script setup lang="ts">
import { onMounted, onUnmounted, ref, shallowRef } from 'vue'
import AMapLoader from '@amap/amap-jsapi-loader'
import type { Attraction,Hotel } from '../types'

const props = defineProps<{ 
  attractions: Attraction[],
  hotels?:Hotel[]
 }>()

const mapContainer = ref<HTMLDivElement | null>(null)
const errorMsg = ref<string | null>(null)
// 用 shallowRef 避免 Vue 深度代理大对象（AMap 地图实例非常大，深度代理会卡）
const mapInstance = shallowRef<any>(null)

onMounted(async () => {
  try {
    const AMap = await AMapLoader.load({
      key: import.meta.env.VITE_AMAP_KEY,
      version: '2.0',
      plugins: ['AMap.Polyline'],
    })

    if (!mapContainer.value) return

    const map = new AMap.Map(mapContainer.value, {
      zoom: 11,
      viewMode: '2D',
    })
    mapInstance.value = map

    // 创建编号 Marker
    const attractionMarkers = props.attractions.map((a, idx) => {
      const num = idx + 1
      return new AMap.Marker({
        position: [a.longitude, a.latitude],
        content: `<div class="amap-num-marker">${num}</div>`,
        offset: new AMap.Pixel(-14, -14),
        title: a.name,
      })
    })

    // 景点连线
    const polyline = new AMap.Polyline({
      path: props.attractions.map((a) => [a.longitude, a.latitude]),
      strokeColor: '#4a5fdc',
      strokeWeight: 4,
      strokeOpacity: 0.7,
      lineJoin: 'round',
    })

    // 酒店 Marker（红色 H 编号，和景点区分）
    const hotelMarkers = (props.hotels ?? [])
    .filter((h)=> h.longitude && h.latitude)
    .map((h,idx)=>{
      return new AMap.Marker({
        position: [h.longitude, h.latitude],
        content: `<div class="amap-hotel-marker">H${idx + 1}</div>`,
        offset: new AMap.Pixel(-14, -14),
        title: `${h.name}  ⭐${h.rating}  ${h.price_range}`,   // 鼠标悬停显示
      })
    })

    map.add([...attractionMarkers, ...hotelMarkers, polyline])
    map.setFitView()
  } catch (e: any) {
    errorMsg.value = `地图加载失败：${e.message || '未知错误'}`
    console.error('[AttractionMap]', e)
  }
})

onUnmounted(() => {
  mapInstance.value?.destroy?.()
})
</script>

<template>
  <div class="map-card">
    <div class="card-header">📍 景点地图</div>
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
  background: #4a5fdc;
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
  background: #ef4444;            /* 红色，区分景点的蓝 */
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
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}
.card-header {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  padding: 14px 20px;
  font-size: 16px;
  font-weight: 600;
}
.map-body {
  padding: 16px;
}
.map-container {
  width: 100%;
  height: 400px;
  border-radius: 8px;
  overflow: hidden;
}
.error {
  padding: 40px;
  text-align: center;
  color: #c33;
  background: #fff5f5;
  border-radius: 8px;
}
</style>
