<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  uploadKnowledge, listKnowledge, deleteKnowledge,
  type KnowledgeUpload,
} from '../api/knowledge'

const router = useRouter()

// 表单
const city = ref('')
const source = ref('')
const content = ref('')
const submitting = ref(false)
const message = ref('')

// 列表
const uploads = ref<KnowledgeUpload[]>([])

// 拉取列表
async function load() {
  uploads.value = await listKnowledge()
}

// 上传
async function submit() {
  if (!city.value.trim() || !content.value.trim()) {
    message.value = '城市和内容不能为空'
    return
  }
  submitting.value = true
  message.value = ''
  try {
    const res = await uploadKnowledge(city.value.trim(), source.value.trim(), content.value)
    message.value = `上传成功,切分为 ${res.chunk_count} 段`
    content.value = ''       // 清空正文,城市保留方便连续传
    source.value = ''
    await load()             // 刷新列表
  } catch (e: any) {
    message.value = e.message || '上传失败'
  } finally {
    submitting.value = false
  }
}

// 删除
async function remove(uploadId: string) {
  if (!confirm('确定删除这批攻略?')) return
  await deleteKnowledge(uploadId)
  await load()
}

onMounted(load)
</script>

<template>
  <div class="kb-page">
    <header class="kb-header">
      <button class="back-btn" @click="router.push('/')">← 返回</button>
      <h2>我的攻略库</h2>
    </header>

    <p class="kb-hint">
      上传你收集的城市景点攻略/游记文本,系统会自动切分并向量化。
      之后生成该城市行程时,会自动检索这些资料来丰富景点描述。
    </p>

    <!-- 上传表单 -->
    <section class="kb-form">
      <input v-model="city" placeholder="城市(如:南京)" />
      <input v-model="source" placeholder="来源/标题(可选,如:小红书攻略)" />
      <textarea v-model="content" rows="8" placeholder="粘贴攻略正文..."></textarea>
      <div class="kb-actions">
        <button :disabled="submitting" @click="submit">
          {{ submitting ? '上传中...' : '上传' }}
        </button>
        <span class="kb-msg">{{ message }}</span>
      </div>
    </section>

    <!-- 已上传列表 -->
    <section class="kb-list">
      <h3>已上传({{ uploads.length }})</h3>
      <p v-if="uploads.length === 0" class="kb-empty">还没有上传任何攻略</p>
      <ul>
        <li v-for="u in uploads" :key="u.upload_id">
          <div class="kb-item-info">
            <span class="kb-city">{{ u.city }}</span>
            <span class="kb-source">{{ u.source || '(无标题)' }}</span>
            <span class="kb-count">{{ u.chunk_count }} 段</span>
          </div>
          <button class="kb-del" @click="remove(u.upload_id)">删除</button>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped lang="less">
.kb-page { max-width: 720px; margin: 0 auto; padding: 24px; }
.kb-header { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.back-btn { border: none; background: #f1f5f9; padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.kb-hint { color: #64748b; font-size: 14px; line-height: 1.6; margin-bottom: 20px; }

.kb-form { display: flex; flex-direction: column; gap: 10px; margin-bottom: 28px; }
.kb-form input, .kb-form textarea {
  padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 14px;
  font-family: inherit;
}
.kb-actions { display: flex; align-items: center; gap: 12px; }
.kb-actions button {
  padding: 8px 20px; border: none; border-radius: 8px; background: #3b82f6; color: #fff;
  cursor: pointer;
}
.kb-actions button:disabled { opacity: .6; cursor: not-allowed; }
.kb-msg { color: #059669; font-size: 13px; }

.kb-list h3 { font-size: 15px; margin-bottom: 12px; }
.kb-empty { color: #94a3b8; }
.kb-list ul { list-style: none; padding: 0; }
.kb-list li {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px; border: 1px solid #f1f5f9; border-radius: 8px; margin-bottom: 8px;
}
.kb-item-info { display: flex; gap: 12px; align-items: center; }
.kb-city { font-weight: 600; }
.kb-source { color: #64748b; font-size: 13px; }
.kb-count { color: #94a3b8; font-size: 12px; }
.kb-del { border: none; background: #fef2f2; color: #ef4444; padding: 6px 12px; border-radius: 6px; cursor: pointer; }
</style>
