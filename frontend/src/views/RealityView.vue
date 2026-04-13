<template>
  <div class="reality-container">
    <nav class="reality-nav">
      <router-link to="/" class="nav-brand">REALITYFISH</router-link>
      <div class="nav-phase">{{ phaseLabel }}</div>
    </nav>

    <div class="reality-content">
      <!-- Step indicators -->
      <div class="step-track">
        <div v-for="(step, i) in steps" :key="i"
             class="step-marker" :class="{ active: currentStep === i, done: currentStep > i }">
          <span class="step-num">{{ i + 1 }}</span>
          <span class="step-label">{{ step }}</span>
        </div>
      </div>

      <!-- Step 0: Thesis Upload -->
      <section v-if="currentStep === 0" class="step-panel">
        <h2>Upload Thesis</h2>
        <p class="step-desc">Provide your research question and audience profiles as a markdown file.</p>
        <div class="upload-area" @click="$refs.fileInput.click()"
             @dragover.prevent @drop.prevent="onDrop">
          <input ref="fileInput" type="file" accept=".md,.txt" @change="onFileSelect" hidden />
          <div v-if="!thesisFile" class="upload-prompt">
            <span class="upload-icon">+</span>
            <span>Drop .md file here or click to browse</span>
          </div>
          <div v-else class="upload-done">
            <span>{{ thesisFile.name }}</span>
            <button @click.stop="thesisFile = null" class="clear-btn">x</button>
          </div>
        </div>
        <button class="action-btn" :disabled="!thesisFile || uploading" @click="uploadThesis">
          {{ uploading ? 'Parsing...' : 'Parse & Continue' }}
        </button>
        <div v-if="thesisSummary" class="summary-card">
          <h3>{{ thesisSummary.research_question }}</h3>
          <div class="meta-row">
            <span class="tag" v-for="p in thesisSummary.scope.platforms" :key="p">{{ p }}</span>
            <span class="tag" v-for="k in thesisSummary.scope.keywords.slice(0, 3)" :key="k">{{ k }}</span>
          </div>
          <div v-for="a in thesisSummary.audience_profiles" :key="a.name" class="audience-item">
            <strong>{{ a.name }}</strong>: {{ a.description }}
          </div>
        </div>
      </section>

      <!-- Step 1: World Building -->
      <section v-if="currentStep === 1" class="step-panel">
        <h2>Building World</h2>
        <p class="step-desc">Scraping X and Reddit, extracting entities, building behavioral profiles...</p>
        <div v-if="worldTask" class="progress-panel">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: worldTask.progress + '%' }"></div>
          </div>
          <p class="progress-msg">{{ worldTask.message || 'Working...' }}</p>
          <p class="progress-pct">{{ worldTask.progress }}%</p>
        </div>
        <button v-if="!worldTask" class="action-btn" @click="startWorldBuild">
          Start World Build
        </button>
      </section>

      <!-- Step 2: World Review -->
      <section v-if="currentStep === 2" class="step-panel">
        <h2>Review Entity Pool</h2>
        <p class="step-desc">
          {{ entityPool.length }} entities found
          ({{ entityPool.filter(e => e.topic_aware).length }} topic-aware,
          {{ entityPool.filter(e => !e.topic_aware).length }} audience-profile)
        </p>
        <div class="entity-grid">
          <div v-for="e in entityPool" :key="e.username + e.platform" class="entity-card"
               :class="{ 'topic-aware': e.topic_aware }">
            <div class="entity-header">
              <span class="entity-platform">{{ e.platform }}</span>
              <span class="entity-name">@{{ e.username }}</span>
            </div>
            <p class="entity-summary">{{ e.personality_summary || e.relevance_reason }}</p>
            <div class="entity-meta">
              <span>{{ e.post_count }} posts</span>
              <span :class="e.topic_aware ? 'aware-badge' : 'audience-badge'">
                {{ e.topic_aware ? 'Topic Aware' : 'Audience Profile' }}
              </span>
            </div>
          </div>
        </div>
        <div class="review-actions">
          <textarea v-model="reviewFeedback" placeholder="Optional feedback..." class="feedback-input"></textarea>
          <button class="action-btn" @click="approveWorld">Approve World</button>
        </div>
      </section>

      <!-- Step 3: Existing Reality Report -->
      <section v-if="currentStep === 3" class="step-panel">
        <h2>Existing Reality Report</h2>
        <p class="step-desc">Generating report from real social data + focus group discussions...</p>
        <div v-if="reportTask" class="progress-panel">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: reportTask.progress + '%' }"></div>
          </div>
          <p class="progress-msg">{{ reportTask.message || 'Working...' }}</p>
        </div>
        <button v-if="!reportTask" class="action-btn" @click="generateRealityReport">
          Generate Report
        </button>
        <div v-if="realityReportId" class="report-ready">
          <p>Report ready!</p>
          <router-link :to="'/report/' + realityReportId" class="action-btn view-btn">
            View Report
          </router-link>
        </div>
      </section>

      <!-- Step 4: Scenario Definition -->
      <section v-if="currentStep === 4" class="step-panel">
        <h2>Define Future Scenario</h2>
        <p class="step-desc">Based on the Existing Reality report, what scenario do you want to simulate?</p>
        <textarea v-model="scenario" class="scenario-input"
                  placeholder="e.g., Google launches AI Studio Mobile app enabling vibe coding on the go..."></textarea>
        <button class="action-btn" :disabled="!scenario.trim()" @click="injectScenario">
          Set Scenario & Start Simulation
        </button>
      </section>

      <!-- Step 5: Future Simulation + Report -->
      <section v-if="currentStep === 5" class="step-panel">
        <h2>Future Prediction</h2>
        <p class="step-desc">Simulating with awareness mechanics: who notices, who cares, who stays silent...</p>
        <div v-if="futureTask" class="progress-panel">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: futureTask.progress + '%' }"></div>
          </div>
          <p class="progress-msg">{{ futureTask.message || 'Working...' }}</p>
        </div>
        <div v-if="futureReportId" class="report-ready">
          <p>Future Prediction Report ready!</p>
          <router-link :to="'/report/' + futureReportId" class="action-btn view-btn">
            View Report
          </router-link>
        </div>
      </section>

      <!-- Error display -->
      <div v-if="error" class="error-banner">{{ error }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const API = '/api/reality'

const steps = ['Thesis', 'World Build', 'Review', 'Reality Report', 'Scenario', 'Future Sim']
const currentStep = ref(0)
const error = ref('')
const projectId = ref(route.params.projectId || '')

// Step 0
const thesisFile = ref(null)
const uploading = ref(false)
const thesisSummary = ref(null)

// Step 1
const worldTask = ref(null)
const worldPollTimer = ref(null)

// Step 2
const entityPool = ref([])
const reviewFeedback = ref('')

// Step 3
const reportTask = ref(null)
const reportPollTimer = ref(null)
const realityReportId = ref(null)

// Step 4
const scenario = ref('')

// Step 5
const futureTask = ref(null)
const futurePollTimer = ref(null)
const futureReportId = ref(null)

const phaseLabel = computed(() => {
  if (currentStep.value <= 3) return 'Phase 1: Existing Reality'
  return 'Phase 2: Future Simulation'
})

function onFileSelect(e) {
  thesisFile.value = e.target.files[0] || null
}

function onDrop(e) {
  const file = e.dataTransfer.files[0]
  if (file && (file.name.endsWith('.md') || file.name.endsWith('.txt'))) {
    thesisFile.value = file
  }
}

async function uploadThesis() {
  if (!thesisFile.value) return
  uploading.value = true
  error.value = ''
  try {
    const text = await thesisFile.value.text()
    const resp = await fetch(`${API}/thesis/upload`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.error || 'Upload failed')
    projectId.value = data.project_id
    thesisSummary.value = data
    currentStep.value = 1
  } catch (e) {
    error.value = e.message
  } finally {
    uploading.value = false
  }
}

async function startWorldBuild() {
  error.value = ''
  try {
    const resp = await fetch(`${API}/world/build`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId.value }),
    })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.error || 'Build failed')
    worldTask.value = { progress: 0, message: 'Starting...' }
    pollTask(data.task_id, 'world')
  } catch (e) {
    error.value = e.message
  }
}

function pollTask(taskId, type) {
  const timer = setInterval(async () => {
    try {
      const resp = await fetch(`${API}/world/status/${taskId}`)
      const data = await resp.json()
      if (type === 'world') {
        worldTask.value = data
        if (data.status === 'completed') {
          clearInterval(timer)
          await loadEntityPool()
          currentStep.value = 2
        } else if (data.status === 'failed') {
          clearInterval(timer)
          error.value = data.error || 'World build failed'
        }
      }
    } catch (e) {
      clearInterval(timer)
      error.value = e.message
    }
  }, 3000)
  if (type === 'world') worldPollTimer.value = timer
}

async function loadEntityPool() {
  const resp = await fetch(`${API}/world/review/${projectId.value}`)
  const data = await resp.json()
  entityPool.value = data.entities || []
}

async function approveWorld() {
  error.value = ''
  try {
    await fetch(`${API}/world/approve/${projectId.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ feedback: reviewFeedback.value }),
    })
    currentStep.value = 3
  } catch (e) {
    error.value = e.message
  }
}

async function generateRealityReport() {
  error.value = ''
  try {
    const resp = await fetch(`${API}/reality/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId.value }),
    })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.error)
    reportTask.value = { progress: 0, message: 'Starting...' }
    const timer = setInterval(async () => {
      const r = await fetch(`${API}/world/status/${data.task_id}`)
      const d = await r.json()
      reportTask.value = d
      if (d.status === 'completed') {
        clearInterval(timer)
        realityReportId.value = d.result?.report_id
        currentStep.value = 4
      } else if (d.status === 'failed') {
        clearInterval(timer)
        error.value = d.error || 'Report generation failed'
      }
    }, 5000)
    reportPollTimer.value = timer
  } catch (e) {
    error.value = e.message
  }
}

async function injectScenario() {
  error.value = ''
  try {
    await fetch(`${API}/scenario/inject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId.value, scenario: scenario.value }),
    })
    currentStep.value = 5
    startFutureSimulation()
  } catch (e) {
    error.value = e.message
  }
}

async function startFutureSimulation() {
  try {
    const resp = await fetch(`${API}/future/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId.value }),
    })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.error)
    futureTask.value = { progress: 0, message: 'Starting...' }
    const timer = setInterval(async () => {
      const r = await fetch(`${API}/world/status/${data.task_id}`)
      const d = await r.json()
      futureTask.value = d
      if (d.status === 'completed') {
        clearInterval(timer)
        futureReportId.value = d.result?.report_id
      } else if (d.status === 'failed') {
        clearInterval(timer)
        error.value = d.error || 'Simulation failed'
      }
    }, 5000)
    futurePollTimer.value = timer
  } catch (e) {
    error.value = e.message
  }
}

onUnmounted(() => {
  [worldPollTimer, reportPollTimer, futurePollTimer].forEach(t => {
    if (t.value) clearInterval(t.value)
  })
})
</script>

<style scoped>
.reality-container {
  min-height: 100vh;
  background: #fafafa;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.reality-nav {
  height: 56px;
  background: #111;
  color: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 32px;
}

.nav-brand {
  font-weight: 800;
  font-size: 1rem;
  letter-spacing: 1px;
  color: #fff;
  text-decoration: none;
}

.nav-phase {
  font-size: 0.85rem;
  color: #888;
}

.reality-content {
  max-width: 960px;
  margin: 0 auto;
  padding: 40px 24px;
}

.step-track {
  display: flex;
  gap: 4px;
  margin-bottom: 40px;
}

.step-marker {
  flex: 1;
  padding: 12px 8px;
  background: #eee;
  text-align: center;
  font-size: 0.75rem;
  color: #999;
  transition: all 0.3s;
}

.step-marker.active {
  background: #111;
  color: #fff;
}

.step-marker.done {
  background: #333;
  color: #ccc;
}

.step-num {
  display: block;
  font-weight: 700;
  font-size: 1.1rem;
  margin-bottom: 2px;
}

.step-panel {
  background: #fff;
  border: 1px solid #e5e5e5;
  padding: 32px;
  margin-bottom: 24px;
}

.step-panel h2 {
  font-size: 1.5rem;
  font-weight: 600;
  margin: 0 0 8px;
}

.step-desc {
  color: #666;
  margin-bottom: 24px;
  line-height: 1.6;
}

.upload-area {
  border: 2px dashed #ddd;
  padding: 40px;
  text-align: center;
  cursor: pointer;
  margin-bottom: 20px;
  transition: border-color 0.2s;
}

.upload-area:hover {
  border-color: #999;
}

.upload-icon {
  font-size: 2rem;
  display: block;
  margin-bottom: 8px;
  color: #ccc;
}

.upload-done {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.clear-btn {
  background: none;
  border: 1px solid #ddd;
  cursor: pointer;
  padding: 2px 8px;
  color: #999;
}

.action-btn {
  display: inline-block;
  background: #111;
  color: #fff;
  border: none;
  padding: 14px 28px;
  font-weight: 600;
  font-size: 0.95rem;
  cursor: pointer;
  transition: background 0.2s;
  text-decoration: none;
}

.action-btn:hover:not(:disabled) {
  background: #ff4500;
}

.action-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.view-btn {
  margin-top: 12px;
}

.summary-card {
  margin-top: 24px;
  padding: 20px;
  background: #f8f8f8;
  border: 1px solid #eee;
}

.summary-card h3 {
  font-size: 1.1rem;
  margin: 0 0 12px;
}

.meta-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.tag {
  background: #eee;
  padding: 3px 10px;
  font-size: 0.8rem;
  color: #555;
}

.audience-item {
  font-size: 0.9rem;
  color: #555;
  margin-bottom: 4px;
}

.progress-panel {
  margin-bottom: 20px;
}

.progress-bar {
  height: 6px;
  background: #eee;
  margin-bottom: 8px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #111;
  transition: width 0.5s ease;
}

.progress-msg {
  font-size: 0.85rem;
  color: #666;
}

.progress-pct {
  font-weight: 700;
  font-size: 1.2rem;
}

.entity-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
  max-height: 500px;
  overflow-y: auto;
}

.entity-card {
  border: 1px solid #e5e5e5;
  padding: 16px;
  background: #fff;
}

.entity-card.topic-aware {
  border-left: 3px solid #111;
}

.entity-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.entity-platform {
  font-size: 0.75rem;
  color: #999;
  text-transform: uppercase;
}

.entity-name {
  font-weight: 600;
  font-size: 0.9rem;
}

.entity-summary {
  font-size: 0.85rem;
  color: #555;
  line-height: 1.5;
  margin-bottom: 8px;
}

.entity-meta {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #999;
}

.aware-badge {
  color: #111;
  font-weight: 600;
}

.audience-badge {
  color: #ff4500;
  font-weight: 600;
}

.review-actions {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.feedback-input {
  flex: 1;
  border: 1px solid #ddd;
  padding: 12px;
  font-size: 0.9rem;
  resize: vertical;
  min-height: 40px;
}

.scenario-input {
  width: 100%;
  border: 1px solid #ddd;
  padding: 16px;
  font-size: 0.95rem;
  line-height: 1.6;
  resize: vertical;
  min-height: 120px;
  margin-bottom: 16px;
  font-family: inherit;
}

.report-ready {
  text-align: center;
  padding: 24px;
  background: #f0f8f0;
  border: 1px solid #d0e8d0;
}

.error-banner {
  background: #fff0f0;
  border: 1px solid #ffcccc;
  padding: 12px 20px;
  color: #cc0000;
  margin-top: 16px;
  font-size: 0.9rem;
}
</style>
