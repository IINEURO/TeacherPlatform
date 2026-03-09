# 1. 项目名称

AI 辅助教学系统（竞赛原型）

# 2. 项目背景

在课堂教学场景中，教师通常需要投入大量时间进行课程资料整理、题目设计与课后辅导；学生端则缺少基于作答表现的即时反馈与针对性补练。本项目面向比赛原型阶段，构建一个可运行的教学闭环系统：

- 教师侧：上传教学资料并快速生成课程结构化内容
- 学生侧：完成练习、自动判分、获取个性化补练推荐

目标是验证“AI + 教学流程”的可行性，而非生产级权限或复杂运营系统。

# 3. 核心功能

## 教师端

- 创建课程（课程名称、学科、难度、教学目标、适用对象）
- 上传教学说明文本、PPT、题目文本
- AI 生成教学大纲与核心知识点
- AI 生成补充练习题（3-5 题，优先选择题）
- 查看课程资源与 AI 生成结果

## 学生端

- 查看课程基本信息
- 查看 AI 生成教学大纲与核心知识点
- 查看练习题列表并一次性提交答案
- 选择题自动判分，返回总分与逐题对错信息
- 查看个性化补练推荐（薄弱知识点、推荐题、学习建议）

# 4. 技术架构

## 技术栈

- 后端：FastAPI
- 数据库：SQLite + SQLAlchemy
- 前端：HTML + CSS + JavaScript
- AI 接口：DeepSeek（OpenAI 兼容协议）

## 分层设计

- `routers`：接口层，负责请求入口与返回结构
- `services`：业务层，负责 AI 调用、资源解析、规则推荐
- `crud`：数据访问层，负责数据库读写
- `models/schemas`：数据模型与接口数据结构
- `templates/static`：页面与前端交互逻辑

# 5. AI 在系统中的作用

AI 在本系统中承担三类任务：

1. 教学内容结构化：基于教学目标、教学说明、PPT 文本生成课程简介、教学大纲、核心知识点
2. 练习题生成：生成可直接用于展示和自动批改的补充选择题
3. 个性化补练补充：在题库不足时，围绕薄弱知识点补充 1-2 道新题

同时保留规则驱动逻辑作为兜底，保证演示稳定性。

# 6. 项目目录结构

```text
TeacherPlatform/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── crud.py
│   ├── routers/
│   │   ├── teacher.py
│   │   └── student.py
│   ├── services/
│   │   ├── llm_client.py
│   │   ├── content_extractor.py
│   │   └── personalized_recommendation.py
│   ├── templates/
│   │   ├── index.html
│   │   ├── teacher.html
│   │   └── student.html
│   └── static/
│       ├── style.css
│       └── app.js
├── data/
│   ├── app.db
│   └── uploads/
├── requirements.txt
├── .env.example
└── README.md
```

# 7. 本地运行方法

## 1) 安装依赖

```bash
cd /home/Turtledove/TeacherPlatform
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2) 配置环境变量

```bash
export LLM_API_BASE_URL="https://api.deepseek.com/v1"
export DEEPSEEK_API_KEY="你的API_KEY"
export LLM_MODEL="deepseek-chat"
export LLM_TIMEOUT_SECONDS="30"
```

## 3) 启动服务

```bash
uvicorn app.main:app --reload --port 8000
```

## 4) 访问页面

- 首页：`http://127.0.0.1:8000/`
- 教师端：`http://127.0.0.1:8000/teacher`
- 学生端：`http://127.0.0.1:8000/student`

# 8. 演示流程

1. 教师端创建课程并填写教学目标。
2. 上传教学说明文本、PPT、题目文本。
3. 点击生成教学大纲，展示课程简介、教学大纲、核心知识点。
4. 点击生成补充练习题，展示结构化题目（题型/选项/答案/解析/知识点）。
5. 切换到学生端，加载课程并完成选择题。
6. 一次性提交答案，展示总分、每题对错、标准答案和解析。
7. 点击“个性化补练推荐”，展示薄弱知识点、推荐题与学习建议。

# 9. 后续可扩展方向

- 增加题型支持：填空题、主观题、编程题
- 增强判分策略：规则评分 + 大模型评分融合
- 引入学生进度视图：按章节跟踪长期学习曲线
- 引入教师分析面板：班级知识点掌握热力图
- 增加模型可配置能力：支持多模型切换与成本控制
- 完善工程化能力：权限体系、日志审计、自动化测试、容器化部署




cd ~/TeacherPlatform
source .venv/bin/activate

cat > .env << 'EOF'
LLM_API_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_API_KEY=你的新key
LLM_MODEL=deepseek-chat
LLM_TIMEOUT_SECONDS=180
EOF

uvicorn app.main:app --reload --port 8000

