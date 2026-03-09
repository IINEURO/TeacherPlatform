/**
 * 教师端 + 学生端页面交互脚本（展示优化版）。
 * 保持原有 API 与业务流程不变，增强教师端 UI 交互体验。
 */

async function apiFetch(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `请求失败: ${response.status}`);
  }
  return response.json();
}

function pretty(data) {
  return JSON.stringify(data, null, 2);
}

function escapeHtml(input) {
  const text = String(input ?? '');
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function setStatus(element, message, tone = 'info') {
  if (!element) return;
  element.textContent = message;
  element.classList.remove('status-ok', 'status-error');
  if (tone === 'ok') {
    element.classList.add('status-ok');
  }
  if (tone === 'error') {
    element.classList.add('status-error');
  }
}

function setBoxLoading(element, text) {
  if (!element) return;
  element.innerHTML = `
    <div class="loading-inline">
      <span class="spinner"></span>
      <span>${escapeHtml(text)}</span>
      <span class="loading-dots"><i></i><i></i><i></i></span>
    </div>
  `;
}

function setSkeleton(element, lines = 4) {
  if (!element) return;
  const widths = ['100%', '88%', '76%', '92%', '70%'];
  const rows = Array.from({ length: lines })
    .map(
      (_, idx) =>
        `<span class="skeleton-line" style="width:${widths[idx % widths.length]};"></span>`
    )
    .join('');
  element.innerHTML = `<div class="skeleton-block">${rows}</div>`;
}

function initUiMotionFeedback() {
  document.addEventListener('click', (event) => {
    const btn = event.target.closest('.btn');
    if (!btn) return;
    btn.classList.add('is-pressed');
    setTimeout(() => btn.classList.remove('is-pressed'), 160);
  });

  const cards = document.querySelectorAll('.card, .course-card, .upload-card, .exercise-item, .ai-module');
  cards.forEach((card, index) => {
    card.classList.add('animate-in');
    card.style.animationDelay = `${Math.min(index * 35, 360)}ms`;
  });
}

function formatDateTime(raw) {
  if (!raw) return '-';
  const value = new Date(raw);
  if (Number.isNaN(value.getTime())) return raw;
  return value.toLocaleString('zh-CN', { hour12: false });
}

function renderTags(items = []) {
  if (!items.length) {
    return '<span class="tag">暂无数据</span>';
  }
  return items.map((item) => `<span class="tag">${escapeHtml(item)}</span>`).join('');
}

function renderMaterialList(materials = [], emptyText = '暂无') {
  if (!materials.length) {
    return `<p class="mono">${escapeHtml(emptyText)}</p>`;
  }

  const lines = materials
    .map(
      (item) =>
        `<li>#${item.id} · ${escapeHtml(item.file_name)} <span class="mono">(${escapeHtml(formatDateTime(item.created_at))})</span></li>`
    )
    .join('');

  return `<ul class="outline-list">${lines}</ul>`;
}

function renderResourcePanel(payload) {
  const notes = payload.teaching_notes || [];
  const ppts = payload.ppts || [];
  const videos = payload.videos || [];
  const questions = payload.question_texts || [];

  return `
    <div class="metrics">
      <article class="metric-item"><span>教学说明</span><strong>${notes.length}</strong></article>
      <article class="metric-item"><span>PPT 文件</span><strong>${ppts.length}</strong></article>
      <article class="metric-item"><span>视频文件</span><strong>${videos.length}</strong></article>
      <article class="metric-item"><span>题目文本</span><strong>${questions.length}</strong></article>
    </div>
    <h4>教学说明</h4>
    ${renderMaterialList(notes, '暂无教学说明')}
    <h4>PPT 文件</h4>
    ${renderMaterialList(ppts, '暂无 PPT')}
    <h4>视频文件</h4>
    ${renderMaterialList(videos, '暂无视频')}
    <h4>题目文本</h4>
    ${renderMaterialList(questions, '暂无题目文本')}
  `;
}

function renderOutlinePanel(payload) {
  const outlineItems = (payload.teaching_outline || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join('');

  return `
    <p><strong>课程简介：</strong>${escapeHtml(payload.course_intro || '暂无课程简介')}</p>
    <h4>教学大纲条目</h4>
    <ol class="outline-list">${outlineItems || '<li>暂无教学大纲</li>'}</ol>
  `;
}

function renderKnowledgePanel(payload) {
  return `
    <p><strong>核心知识点数量：</strong>${(payload.core_knowledge_points || []).length}</p>
    <div class="tag-list">${renderTags(payload.core_knowledge_points || [])}</div>
  `;
}

function renderExerciseBatch(payload) {
  const exercises = payload.exercises || [];
  if (!exercises.length) {
    return '<p>当前课程暂无补充练习题。</p>';
  }

  const items = exercises
    .map((item, index) => {
      const options = (item.options || [])
        .map((opt) => `<li>${escapeHtml(opt)}</li>`)
        .join('');

      return `
        <li>
          <strong>第 ${index + 1} 题（${escapeHtml(item.question_type)}）</strong>
          <p>${escapeHtml(item.question_text)}</p>
          <p><span class="tag">知识点：${escapeHtml(item.knowledge_point || '未标注')}</span></p>
          ${options ? `<ol class="outline-list">${options}</ol>` : ''}
          <p>答案：<strong>${escapeHtml(item.answer || '无')}</strong></p>
          <p>解析：${escapeHtml(item.analysis || '暂无解析')}</p>
        </li>
      `;
    })
    .join('');

  return `
    <div class="metrics">
      <article class="metric-item"><span>课程 ID</span><strong>${escapeHtml(payload.course_id)}</strong></article>
      <article class="metric-item"><span>题目数量</span><strong>${escapeHtml(payload.count)}</strong></article>
    </div>
    <ol class="exercise-list">${items}</ol>
  `;
}

function renderLearningEvaluation(payload) {
  const weakPoints = (payload.weak_knowledge_points || [])
    .map((item) => `${item.knowledge_point}（${item.accuracy}%）`)
    .join('、');

  const exercises = (payload.recommended_exercises || [])
    .map(
      (item, index) =>
        `<li><strong>推荐 ${index + 1}：</strong>${escapeHtml(item.question_text)} <span class="tag">来源：${escapeHtml(
          item.source || 'AI'
        )}</span></li>`
    )
    .join('');

  return `
    <p><strong>学生：</strong>${escapeHtml(payload.student_name)}</p>
    <p><strong>薄弱知识点：</strong>${escapeHtml(weakPoints || '暂无明显薄弱点')}</p>
    <h4>学习评价</h4>
    <p>${escapeHtml(payload.learning_comment || '暂无学习评价')}</p>
    <h4>推荐补练题</h4>
    ${exercises ? `<ol class="outline-list">${exercises}</ol>` : '<p>暂无推荐补练题。</p>'}
  `;
}

// ------------------------ 教师端逻辑 ------------------------
const teacherState = {
  courses: [],
  selectedCourseId: null,
};

function getSelectedCourseId() {
  return document.getElementById('teacher-course-select').value;
}

function setSelectedCourseId(courseId) {
  const select = document.getElementById('teacher-course-select');
  if (!select || !courseId) return;

  select.value = String(courseId);
  teacherState.selectedCourseId = String(courseId);
  renderTeacherCourseCards();
  updateTeacherCourseHeader();
  const evalBox = document.getElementById('learning-eval-box');
  if (evalBox) {
    evalBox.textContent = '输入学生姓名并点击“加载学习评价”后显示';
  }
}

function updateTeacherCourseHeader() {
  const selectedId = getSelectedCourseId();
  const titleEl = document.getElementById('selected-course-title');
  const selected = teacherState.courses.find((item) => String(item.id) === String(selectedId));
  if (!titleEl) return;
  if (!selected) {
    titleEl.textContent = '未选择';
    return;
  }
  titleEl.textContent = `${selected.title}（${selected.subject}）`;
}

function renderTeacherCourseCards() {
  const container = document.getElementById('teacher-course-list');
  const selectedId = getSelectedCourseId();

  if (!container) return;
  container.innerHTML = '';

  if (!teacherState.courses.length) {
    container.innerHTML = '<p class="mono">暂无课程，请先创建课程。</p>';
    return;
  }

  for (const course of teacherState.courses) {
    const card = document.createElement('article');
    card.className = 'course-card';
    if (String(course.id) === String(selectedId)) {
      card.classList.add('is-selected');
    }

    card.innerHTML = `
      <h4>${escapeHtml(course.title)}</h4>
      <p>学科：${escapeHtml(course.subject)}</p>
      <p class="mono">创建时间：${escapeHtml(formatDateTime(course.created_at))}</p>
      <div class="button-row">
        <button class="btn btn-secondary" type="button" data-action="select">${
          String(course.id) === String(selectedId) ? '当前课程' : '选择课程'
        }</button>
      </div>
    `;

    const selectBtn = card.querySelector('[data-action="select"]');
    selectBtn.addEventListener('click', async () => {
      setSelectedCourseId(course.id);
      await refreshResources();
      await refreshGeneratedOutline();
      await refreshGeneratedExercises();
    });

    container.appendChild(card);
  }
}

function updateResourceStat(payload) {
  const el = document.getElementById('selected-course-resource-stat');
  if (!el) return;
  const count =
    (payload.teaching_notes || []).length +
    (payload.ppts || []).length +
    (payload.videos || []).length +
    (payload.question_texts || []).length;
  el.textContent = `${count} 份资源`;
}

function updateAiStat({ outline = false, exercises = null } = {}) {
  const el = document.getElementById('selected-course-ai-stat');
  if (!el) return;

  const parts = [];
  if (outline) {
    parts.push('大纲已生成');
  }
  if (typeof exercises === 'number') {
    parts.push(`补充题 ${exercises} 道`);
  }
  el.textContent = parts.length ? parts.join(' / ') : '待生成';
}

async function loadCourses(preferredId = null) {
  const courses = await apiFetch('/api/teacher/courses');
  const select = document.getElementById('teacher-course-select');

  teacherState.courses = courses;
  select.innerHTML = '';

  if (courses.length === 0) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = '暂无课程';
    select.appendChild(opt);
    renderTeacherCourseCards();
    updateTeacherCourseHeader();
    return;
  }

  for (const course of courses) {
    const opt = document.createElement('option');
    opt.value = String(course.id);
    opt.textContent = `${course.id} - ${course.title}`;
    select.appendChild(opt);
  }

  const current = preferredId || teacherState.selectedCourseId || courses[0].id;
  setSelectedCourseId(String(current));
}

async function refreshResources() {
  const messageBox = document.getElementById('teacher-message');
  const resourceBox = document.getElementById('resource-box');
  const courseId = getSelectedCourseId();

  if (!courseId) {
    setStatus(messageBox, '请先创建并选择课程', 'error');
    return;
  }

  try {
    setBoxLoading(resourceBox, '正在加载课程资源...');
    const payload = await apiFetch(`/api/teacher/courses/${courseId}/resources`);
    resourceBox.innerHTML = renderResourcePanel(payload);
    updateResourceStat(payload);
    setStatus(messageBox, '资源列表已刷新', 'ok');
  } catch (error) {
    resourceBox.textContent = error.message;
    setStatus(messageBox, error.message, 'error');
  }
}

async function refreshGeneratedOutline() {
  const messageBox = document.getElementById('teacher-message');
  const outlineBox = document.getElementById('outline-box');
  const knowledgeBox = document.getElementById('knowledge-box');
  const courseId = getSelectedCourseId();

  if (!courseId) {
    setStatus(messageBox, '请先创建并选择课程', 'error');
    return;
  }

  try {
    setBoxLoading(outlineBox, '正在读取教学大纲...');
    setBoxLoading(knowledgeBox, '正在读取知识点总结...');
    const payload = await apiFetch(`/api/teacher/courses/${courseId}/generated-outline`);
    outlineBox.innerHTML = renderOutlinePanel(payload);
    knowledgeBox.innerHTML = renderKnowledgePanel(payload);
    updateAiStat({ outline: true });
    setStatus(messageBox, '已读取 AI 生成教学大纲', 'ok');
  } catch (error) {
    outlineBox.textContent = error.message;
    knowledgeBox.textContent = error.message;
    updateAiStat({ outline: false });
    setStatus(messageBox, error.message, 'error');
  }
}

async function refreshGeneratedExercises() {
  const messageBox = document.getElementById('teacher-message');
  const box = document.getElementById('generated-exercises-box');
  const courseId = getSelectedCourseId();

  if (!courseId) {
    setStatus(messageBox, '请先创建并选择课程', 'error');
    return;
  }

  try {
    setBoxLoading(box, '正在读取补充练习题...');
    const payload = await apiFetch(`/api/teacher/courses/${courseId}/generated-exercises`);
    box.innerHTML = renderExerciseBatch(payload);
    updateAiStat({ outline: true, exercises: payload.count });
    setStatus(messageBox, `已读取 ${payload.count} 道补充练习题`, 'ok');
  } catch (error) {
    box.textContent = error.message;
    updateAiStat({ outline: true, exercises: 0 });
    setStatus(messageBox, error.message, 'error');
  }
}

async function loadTeacherLearningEvaluation() {
  const messageBox = document.getElementById('teacher-message');
  const box = document.getElementById('learning-eval-box');
  const courseId = getSelectedCourseId();
  const studentName = document.getElementById('evaluation-student-name')?.value.trim() || '';

  if (!courseId) {
    setStatus(messageBox, '请先选择课程', 'error');
    return;
  }
  if (!studentName) {
    setStatus(messageBox, '请先输入学生姓名', 'error');
    return;
  }

  try {
    setBoxLoading(box, 'AI 正在读取学习评价...');
    const payload = await apiFetch(
      `/api/student/courses/${courseId}/recommendation/${encodeURIComponent(studentName)}`
    );
    box.innerHTML = renderLearningEvaluation(payload);
    setStatus(messageBox, '已加载学习评价', 'ok');
  } catch (error) {
    box.textContent = error.message;
    setStatus(messageBox, error.message, 'error');
  }
}

function bindTeacherUploadForms() {
  const messageBox = document.getElementById('teacher-message');
  const uploadNoteForm = document.getElementById('upload-note-form');
  const uploadPptForm = document.getElementById('upload-ppt-form');
  const uploadVideoForm = document.getElementById('upload-video-form');
  const uploadQuestionForm = document.getElementById('upload-question-form');

  uploadNoteForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const courseId = getSelectedCourseId();
    if (!courseId) {
      setStatus(messageBox, '请先选择课程', 'error');
      return;
    }

    try {
      const form = new FormData(uploadNoteForm);
      const payload = new URLSearchParams();
      payload.append('note_text', form.get('note_text'));

      const result = await apiFetch(`/api/teacher/courses/${courseId}/teaching-note`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: payload.toString(),
      });

      setStatus(messageBox, result.message, 'ok');
      uploadNoteForm.reset();
      await refreshResources();
    } catch (error) {
      setStatus(messageBox, error.message, 'error');
    }
  });

  uploadPptForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const courseId = getSelectedCourseId();
    if (!courseId) {
      setStatus(messageBox, '请先选择课程', 'error');
      return;
    }

    try {
      const formData = new FormData(uploadPptForm);
      const result = await apiFetch(`/api/teacher/courses/${courseId}/ppt`, {
        method: 'POST',
        body: formData,
      });

      setStatus(
        messageBox,
        `${result.message}，提取文本长度: ${(result.extracted_preview || '').length}`,
        'ok'
      );
      uploadPptForm.reset();
      await refreshResources();
    } catch (error) {
      setStatus(messageBox, error.message, 'error');
    }
  });

  uploadVideoForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const courseId = getSelectedCourseId();
    if (!courseId) {
      setStatus(messageBox, '请先选择课程', 'error');
      return;
    }

    try {
      const formData = new FormData(uploadVideoForm);
      const result = await apiFetch(`/api/teacher/courses/${courseId}/video`, {
        method: 'POST',
        body: formData,
      });

      setStatus(messageBox, result.message, 'ok');
      uploadVideoForm.reset();
      await refreshResources();
    } catch (error) {
      setStatus(messageBox, error.message, 'error');
    }
  });

  uploadQuestionForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const courseId = getSelectedCourseId();
    if (!courseId) {
      setStatus(messageBox, '请先选择课程', 'error');
      return;
    }

    try {
      const form = new FormData(uploadQuestionForm);
      const payload = new URLSearchParams();
      payload.append('question_text', form.get('question_text'));

      const result = await apiFetch(`/api/teacher/courses/${courseId}/question-text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: payload.toString(),
      });

      setStatus(messageBox, result.message, 'ok');
      uploadQuestionForm.reset();
      await refreshResources();
    } catch (error) {
      setStatus(messageBox, error.message, 'error');
    }
  });
}

function initTeacherPage() {
  const createCourseForm = document.getElementById('create-course-form');
  const refreshResourcesBtn = document.getElementById('refresh-resources-btn');
  const generateOutlineBtn = document.getElementById('generate-outline-btn');
  const refreshOutlineBtn = document.getElementById('refresh-outline-btn');
  const generateExercisesBtn = document.getElementById('generate-exercises-btn');
  const refreshExercisesBtn = document.getElementById('refresh-exercises-btn');
  const loadEvaluationBtn = document.getElementById('load-evaluation-btn');
  const messageBox = document.getElementById('teacher-message');

  setSkeleton(document.getElementById('resource-box'), 5);
  setSkeleton(document.getElementById('outline-box'), 4);
  setSkeleton(document.getElementById('knowledge-box'), 3);
  setSkeleton(document.getElementById('generated-exercises-box'), 5);
  setSkeleton(document.getElementById('learning-eval-box'), 4);

  bindTeacherUploadForms();

  createCourseForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const form = new FormData(createCourseForm);
    const payload = {
      title: form.get('title'),
      subject: form.get('subject'),
      difficulty_level: form.get('difficulty_level'),
      teaching_objective: form.get('teaching_objective'),
      target_audience: form.get('target_audience'),
    };

    try {
      const created = await apiFetch('/api/teacher/courses', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      setStatus(messageBox, `课程创建成功: ${created.title}`, 'ok');
      createCourseForm.reset();
      await loadCourses(created.id);
      await refreshResources();
    } catch (error) {
      setStatus(messageBox, error.message, 'error');
    }
  });

  refreshResourcesBtn.addEventListener('click', refreshResources);
  refreshOutlineBtn.addEventListener('click', refreshGeneratedOutline);
  refreshExercisesBtn.addEventListener('click', refreshGeneratedExercises);
  if (loadEvaluationBtn) {
    loadEvaluationBtn.addEventListener('click', loadTeacherLearningEvaluation);
  }

  generateOutlineBtn.addEventListener('click', async () => {
    const courseId = getSelectedCourseId();
    const outlineBox = document.getElementById('outline-box');
    const knowledgeBox = document.getElementById('knowledge-box');

    if (!courseId) {
      setStatus(messageBox, '请先选择课程', 'error');
      return;
    }

    try {
      setStatus(messageBox, '正在调用模型生成教学大纲...', 'info');
      setBoxLoading(outlineBox, 'AI 正在生成教学大纲...');
      setBoxLoading(knowledgeBox, 'AI 正在整理知识点总结...');
      const result = await apiFetch(`/api/teacher/courses/${courseId}/generate-outline`, {
        method: 'POST',
      });
      outlineBox.innerHTML = renderOutlinePanel(result);
      knowledgeBox.innerHTML = renderKnowledgePanel(result);
      updateAiStat({ outline: true });
      setStatus(messageBox, '教学大纲生成成功', 'ok');
    } catch (error) {
      outlineBox.textContent = error.message;
      knowledgeBox.textContent = error.message;
      setStatus(messageBox, error.message, 'error');
    }
  });

  generateExercisesBtn.addEventListener('click', async () => {
    const courseId = getSelectedCourseId();
    const box = document.getElementById('generated-exercises-box');

    if (!courseId) {
      setStatus(messageBox, '请先选择课程', 'error');
      return;
    }

    try {
      setStatus(messageBox, '正在调用模型生成补充练习题...', 'info');
      setBoxLoading(box, 'AI 正在生成补充练习题...');
      const result = await apiFetch(`/api/teacher/courses/${courseId}/generate-supplement-exercises`, {
        method: 'POST',
      });
      box.innerHTML = renderExerciseBatch(result);
      updateAiStat({ outline: true, exercises: result.count });
      setStatus(messageBox, `补充练习题生成成功，共 ${result.count} 题`, 'ok');
    } catch (error) {
      box.textContent = error.message;
      setStatus(messageBox, error.message, 'error');
    }
  });

  loadCourses()
    .then(async () => {
      await refreshResources();
      await refreshGeneratedOutline();
      await refreshGeneratedExercises();
    })
    .catch((error) => {
      setStatus(messageBox, error.message, 'error');
    });
}

if (document.body.dataset.page === 'teacher') {
  initTeacherPage();
}

// ------------------------ 学生端逻辑 ------------------------
const studentState = {
  courseId: null,
  exercises: [],
  videos: [],
};

async function loadStudentCourses() {
  const select = document.getElementById('student-course-select');
  const courses = await apiFetch('/api/student/courses');

  select.innerHTML = '';
  if (courses.length === 0) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = '暂无课程';
    select.appendChild(opt);
    return;
  }

  for (const course of courses) {
    const opt = document.createElement('option');
    opt.value = String(course.id);
    opt.textContent = `${course.id} - ${course.title}`;
    select.appendChild(opt);
  }
}

function initStudentTabs() {
  const tabButtons = document.querySelectorAll('.student-tab-btn');
  const tabPanels = document.querySelectorAll('.student-tab-panel');

  tabButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tabTarget;
      tabButtons.forEach((item) => item.classList.remove('is-active'));
      tabPanels.forEach((panel) => panel.classList.remove('is-active'));
      btn.classList.add('is-active');
      const panel = document.querySelector(`.student-tab-panel[data-tab-panel="${target}"]`);
      if (panel) panel.classList.add('is-active');
    });
  });
}

function switchStudentTab(tabName) {
  const btn = document.querySelector(`.student-tab-btn[data-tab-target="${tabName}"]`);
  if (btn) btn.click();
}

function updateLearningProgress() {
  const total = studentState.exercises.length;
  const fill = document.getElementById('learning-progress-fill');
  const text = document.getElementById('learning-progress-text');

  if (!fill || !text) return;
  if (total === 0) {
    fill.style.width = '0%';
    text.textContent = '0%';
    return;
  }

  const answered = studentState.exercises.filter((item) =>
    document.querySelector(`input[name="exercise_${item.id}"]:checked`)
  ).length;
  const progress = Math.round((answered / total) * 100);

  fill.style.width = `${progress}%`;
  text.textContent = `${progress}%`;
}

function renderVideoPanel(videos) {
  const player = document.getElementById('student-video-player');
  const listBox = document.getElementById('student-video-list');
  if (!player || !listBox) return;

  listBox.innerHTML = '';
  if (!videos.length) {
    player.removeAttribute('src');
    player.load();
    listBox.innerHTML = '<span class="tag">暂无视频资源</span>';
    return;
  }

  const setActiveVideo = (index) => {
    const selected = videos[index];
    player.src = selected.url;
    player.dataset.videoId = String(selected.id);
    player.load();

    listBox.querySelectorAll('.video-select-btn').forEach((item) => item.classList.remove('is-active'));
    const active = listBox.querySelector(`.video-select-btn[data-video-index="${index}"]`);
    if (active) active.classList.add('is-active');
  };

  videos.forEach((video, index) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'video-select-btn';
    btn.dataset.videoIndex = String(index);
    btn.textContent = `${index + 1}. ${video.file_name}`;
    btn.addEventListener('click', () => setActiveVideo(index));
    listBox.appendChild(btn);
  });

  setActiveVideo(0);
}

function renderStudentExercises(exercises) {
  const container = document.getElementById('student-exercise-container');
  container.innerHTML = '';

  if (!exercises.length) {
    container.innerHTML = '<p>当前课程暂无可作答的选择题。</p>';
    updateLearningProgress();
    return;
  }

  for (const exercise of exercises) {
    const item = document.createElement('div');
    item.className = 'exercise-item';

    const optionsHtml = (exercise.options || [])
      .map((opt, index) => {
        const optionLabel = String.fromCharCode(65 + index);
        return `
          <label class="option-line">
            <input type="radio" name="exercise_${exercise.id}" value="${optionLabel}" />
            <span>${escapeHtml(opt)}</span>
          </label>
        `;
      })
      .join('');

    item.innerHTML = `
      <h3>题目 #${exercise.id}（${escapeHtml(exercise.question_type)}）</h3>
      <p>${escapeHtml(exercise.question_text)}</p>
      <div class="option-group">${optionsHtml}</div>
      <div class="tag-list"><span class="tag">知识点：${escapeHtml(exercise.knowledge_point || '未标注')}</span></div>
      <div class="exercise-item-footer">
        <span class="question-status" id="question-status-${exercise.id}">未作答</span>
        <button type="button" class="btn btn-secondary" data-action="save-question" data-question-id="${exercise.id}">提交本题</button>
      </div>
    `;

    item.querySelectorAll(`input[name="exercise_${exercise.id}"]`).forEach((radio) => {
      radio.addEventListener('change', () => {
        const status = item.querySelector(`#question-status-${exercise.id}`);
        if (status) {
          status.textContent = '已选择答案';
        }
        updateLearningProgress();
      });
    });

    const saveBtn = item.querySelector('[data-action="save-question"]');
    if (saveBtn) {
      saveBtn.addEventListener('click', () => {
        const selected = item.querySelector(`input[name="exercise_${exercise.id}"]:checked`);
        const status = item.querySelector(`#question-status-${exercise.id}`);
        if (!status) return;
        if (!selected) {
          status.textContent = '请先选择一个选项';
          status.classList.remove('is-done');
          return;
        }
        status.textContent = `本题已提交：${selected.value}`;
        status.classList.add('is-done');
      });
    }

    container.appendChild(item);
  }

  updateLearningProgress();
}

function renderStudentCoursePanel(course) {
  return `
    <div class="metrics">
      <article class="metric-item"><span>课程名称</span><strong>${escapeHtml(course.title)}</strong></article>
      <article class="metric-item"><span>学科</span><strong>${escapeHtml(course.subject)}</strong></article>
      <article class="metric-item"><span>难度</span><strong>${escapeHtml(course.difficulty_level)}</strong></article>
      <article class="metric-item"><span>适用对象</span><strong>${escapeHtml(course.target_audience)}</strong></article>
    </div>
  `;
}

function renderStudentLearningPanel(payload) {
  const outlineItems = (payload.teaching_outline || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join('');
  return `
    <h4>课程简介</h4>
    <p>${escapeHtml(payload.course_intro || '暂无课程简介')}</p>
    <h4>教学大纲</h4>
    <ol class="outline-list">${outlineItems || '<li>暂无教学大纲</li>'}</ol>
    <h4>核心知识点</h4>
    <div class="tag-list">${renderTags(payload.core_knowledge_points || [])}</div>
  `;
}

function renderStudentKnowledgePanel(payload) {
  const points = payload.core_knowledge_points || [];
  const summary =
    points.length > 0
      ? `本节课核心关注 ${points.length} 个知识点，建议按照“概念 -> 例题 -> 练习”的顺序学习。`
      : '暂无知识点总结。';
  return `
    <p>${escapeHtml(summary)}</p>
    <div class="tag-list">${renderTags(points)}</div>
  `;
}

async function loadStudentLearningContent() {
  const messageBox = document.getElementById('student-message');
  const courseBox = document.getElementById('student-course-box');
  const outlineBox = document.getElementById('student-outline-box');
  const knowledgeBox = document.getElementById('student-knowledge-box');
  const courseId = document.getElementById('student-course-select').value;

  if (!courseId) {
    setStatus(messageBox, '请先选择课程', 'error');
    return;
  }

  try {
    const payload = await apiFetch(`/api/student/courses/${courseId}/learning`);
    studentState.courseId = courseId;
    studentState.exercises = payload.exercises;
    studentState.videos = payload.videos || [];

    courseBox.innerHTML = renderStudentCoursePanel(payload.course);
    outlineBox.innerHTML = renderStudentLearningPanel(payload);
    if (knowledgeBox) {
      knowledgeBox.innerHTML = renderStudentKnowledgePanel(payload);
    }

    renderVideoPanel(studentState.videos);

    renderStudentExercises(payload.exercises);
    setStatus(messageBox, `已加载课程，当前可作答 ${payload.exercises.length} 道题`, 'ok');
    switchStudentTab('learning');
  } catch (error) {
    setStatus(messageBox, error.message, 'error');
  }
}

function collectStudentAnswers() {
  const answers = [];
  for (const exercise of studentState.exercises) {
    const selected = document.querySelector(`input[name="exercise_${exercise.id}"]:checked`);
    if (!selected) {
      return { ok: false, detail: `题目 ${exercise.id} 尚未作答` };
    }
    answers.push({
      exercise_id: exercise.id,
      selected_option: selected.value,
    });
  }
  return { ok: true, answers };
}

function renderStudentResult(payload) {
  const box = document.getElementById('student-result-box');
  const wrongItems = payload.results.filter((item) => !item.is_correct);

  const wrongHtml = wrongItems.length
    ? `<ol class="wrong-list">${wrongItems
        .map(
          (item) => `
            <li>
              <strong>题目 #${item.exercise_id}</strong>：${escapeHtml(item.question_text)}<br />
              你的答案：${escapeHtml(item.selected_option)} ｜ 标准答案：${escapeHtml(item.correct_answer)}<br />
              解析：${escapeHtml(item.analysis || '暂无解析')} ｜ 知识点：${escapeHtml(item.knowledge_point || '未标注')}
            </li>
          `
        )
        .join('')}</ol>`
    : '<p>本次无错题，表现优秀。</p>';

  box.innerHTML = `
    <div class="metrics">
      <article class="metric-item"><span>课程名</span><strong>${escapeHtml(payload.course_title)}</strong></article>
      <article class="metric-item"><span>学生</span><strong>${escapeHtml(payload.student_name)}</strong></article>
      <article class="metric-item"><span>总分</span><strong>${escapeHtml(payload.total_score)} / ${escapeHtml(payload.max_score)}</strong></article>
      <article class="metric-item"><span>正确率</span><strong>${escapeHtml(payload.accuracy)}%</strong></article>
    </div>
    <h4>错题详情</h4>
    ${wrongHtml}
  `;
}

function renderRecommendation(payload) {
  const weakHtml = (payload.weak_knowledge_points || []).length
    ? `<div class="tag-list">${(payload.weak_knowledge_points || [])
        .map(
          (item) =>
            `<span class="tag">${escapeHtml(item.knowledge_point)} · ${escapeHtml(item.accuracy)}% (${escapeHtml(item.total_answered)}次)</span>`
        )
        .join('')}</div>`
    : '<p>暂无明显薄弱知识点。</p>';

  const exercisesHtml = (payload.recommended_exercises || []).length
    ? `<ol class="reco-list">${payload.recommended_exercises
        .map(
          (item, idx) => `
            <li>
              <strong>推荐题 ${idx + 1}</strong>（${escapeHtml(item.source)}）<br />
              题干：${escapeHtml(item.question_text)}<br />
              选项：${escapeHtml((item.options || []).join(' / ') || '无')}<br />
              标准答案：${escapeHtml(item.answer || '无')} ｜ 知识点：${escapeHtml(item.knowledge_point || '未标注')}
            </li>
          `
        )
        .join('')}</ol>`
    : '<p>暂无推荐补练题。</p>';

  return `
    <h4>薄弱知识点</h4>
    ${weakHtml}
    <h4>推荐练习题</h4>
    ${exercisesHtml}
    <h4>学习评价</h4>
    <p>${escapeHtml(payload.learning_comment || '暂无学习评价')}</p>
  `;
}

async function loadPersonalizedRecommendation() {
  const messageBox = document.getElementById('student-message');
  const recommendationBox = document.getElementById('student-recommendation-box');
  const studentName = document.getElementById('student-name').value.trim();

  if (!studentName) {
    setStatus(messageBox, '请先输入学生姓名', 'error');
    return;
  }
  if (!studentState.courseId) {
    setStatus(messageBox, '请先加载课程内容', 'error');
    return;
  }

  try {
    const payload = await apiFetch(
      `/api/student/courses/${studentState.courseId}/recommendation/${encodeURIComponent(studentName)}`
    );
    recommendationBox.innerHTML = renderRecommendation(payload);
    setStatus(messageBox, '个性化推荐已生成', 'ok');
  } catch (error) {
    recommendationBox.textContent = error.message;
    setStatus(messageBox, error.message, 'error');
  }
}

async function submitStudentAnswers() {
  const messageBox = document.getElementById('student-message');
  const studentName = document.getElementById('student-name').value.trim();

  if (!studentName) {
    setStatus(messageBox, '请先输入学生姓名', 'error');
    return;
  }
  if (!studentState.courseId) {
    setStatus(messageBox, '请先加载课程内容', 'error');
    return;
  }
  if (!studentState.exercises.length) {
    setStatus(messageBox, '当前没有可提交的题目', 'error');
    return;
  }

  const collected = collectStudentAnswers();
  if (!collected.ok) {
    setStatus(messageBox, collected.detail, 'error');
    return;
  }

  try {
    setStatus(messageBox, '正在提交并自动判分...', 'info');
    const result = await apiFetch(`/api/student/courses/${studentState.courseId}/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        student_name: studentName,
        answers: collected.answers,
      }),
    });
    renderStudentResult(result);
    setStatus(messageBox, `提交完成：${result.total_score}/${result.max_score}（正确率 ${result.accuracy}%）`, 'ok');
    await loadPersonalizedRecommendation();
    switchStudentTab('result');
  } catch (error) {
    setStatus(messageBox, error.message, 'error');
  }
}

function initStudentPage() {
  const loadBtn = document.getElementById('load-student-content-btn');
  const submitBtn = document.getElementById('submit-all-btn');
  const recommendationBtn = document.getElementById('load-recommendation-btn');
  const messageBox = document.getElementById('student-message');

  setSkeleton(document.getElementById('student-course-box'), 3);
  setSkeleton(document.getElementById('student-outline-box'), 4);
  setSkeleton(document.getElementById('student-knowledge-box'), 3);
  setSkeleton(document.getElementById('student-exercise-container'), 6);
  setSkeleton(document.getElementById('student-result-box'), 4);
  setSkeleton(document.getElementById('student-recommendation-box'), 4);

  loadBtn.addEventListener('click', loadStudentLearningContent);
  submitBtn.addEventListener('click', submitStudentAnswers);
  recommendationBtn.addEventListener('click', loadPersonalizedRecommendation);
  initStudentTabs();

  loadStudentCourses().catch((error) => {
    setStatus(messageBox, error.message, 'error');
  });
}

if (document.body.dataset.page === 'student') {
  initStudentPage();
}

initUiMotionFeedback();
