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
    message.value = `上传成功，切分为 ${res.chunk_count} 段`
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
  if (!confirm('确定删除这批攻略？')) return
  await deleteKnowledge(uploadId)
  await load()
}

onMounted(load)
</script>

<template>
  <div class="kb-page">
    <header class="kb-header">
      <button class="back-btn" @click="router.push('/')">返回</button>
      <h2>我的攻略库</h2>
    </header>

    <p class="kb-hint">
      上传你收集的城市景点攻略/游记文本，系统会切分并建立检索索引。
      之后生成该城市行程时，会优先参考这些资料补充景点说明。
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
.kb-page { max-width: 820px; margin: 0 auto; padding: 32px 24px; }
.kb-header { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.kb-header h2 { color: var(--color-ink); font-size: 24px; }
.back-btn { border: 1px solid var(--color-border); background: #fff; padding: 7px 12px; border-radius: 8px; cursor: pointer; color: var(--color-ink); }
.back-btn:hover { background: var(--color-soft); }
.kb-hint { color: var(--color-note); font-size: 14px; line-height: 1.7; margin-bottom: 20px; }

.kb-form {
  display: flex; flex-direction: column; gap: 10px; margin-bottom: 28px;
  background: #fff; border: 1px solid var(--color-border); border-radius: var(--radius-card);
  padding: 18px; box-shadow: var(--shadow-soft);
}
.kb-form input, .kb-form textarea {
  padding: 10px 12px; border: 1px solid var(--color-border); border-radius: 8px; font-size: 14px;
  font-family: inherit;
}
.kb-form input:focus, .kb-form textarea:focus {
  outline: none; border-color: var(--color-route); box-shadow: 0 0 0 3px rgba(31, 111, 120, 0.12);
}
.kb-actions { display: flex; align-items: center; gap: 12px; }
.kb-actions button {
  padding: 8px 20px; border: none; border-radius: 8px; background: var(--color-signal); color: #fff;
  cursor: pointer; font-weight: 750;
}
.kb-actions button:hover { background: var(--color-signal-dark); }
.kb-actions button:disabled { opacity: .6; cursor: not-allowed; }
.kb-msg { color: var(--color-route); font-size: 13px; }

.kb-list h3 { font-size: 16px; margin-bottom: 12px; color: var(--color-ink); }
.kb-empty { color: var(--color-muted); }
.kb-list ul { list-style: none; padding: 0; }
.kb-list li {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px; border: 1px solid var(--color-border); border-radius: 8px; margin-bottom: 8px;
  background: #fff;
}
.kb-item-info { display: flex; gap: 12px; align-items: center; }
.kb-city { font-weight: 750; color: var(--color-ink); }
.kb-source { color: var(--color-note); font-size: 13px; }
.kb-count { color: var(--color-muted); font-size: 12px; }
.kb-del { border: none; background: #f8e7e0; color: var(--color-signal); padding: 6px 12px; border-radius: 6px; cursor: pointer; }
</style>
