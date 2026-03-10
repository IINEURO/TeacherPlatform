"""Pydantic 数据结构（教师端最小功能）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CourseCreate(BaseModel):
    """创建课程请求。"""

    title: str = Field(..., min_length=1, max_length=200)
    subject: str = Field(..., min_length=1, max_length=100)
    difficulty_level: str = Field(default="中等", min_length=1, max_length=30)
    teaching_objective: str = Field(..., min_length=1, max_length=5000)
    target_audience: str = Field(..., min_length=1, max_length=200)


class CourseOut(BaseModel):
    """课程响应。"""

    id: int
    title: str
    subject: str
    difficulty_level: str
    teaching_objective: str
    target_audience: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MaterialOut(BaseModel):
    """已上传资源响应。"""

    id: int
    course_id: int
    material_type: str
    file_name: str
    file_path: str
    extracted_text: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class CourseResourcesOut(BaseModel):
    """课程资源聚合响应。"""

    course: CourseOut
    teaching_notes: list[MaterialOut]
    ppts: list[MaterialOut]
    videos: list[MaterialOut]
    question_texts: list[MaterialOut]


class GeneratedOutlineOut(BaseModel):
    """AI 生成教学大纲响应。"""

    course_id: int
    course_intro: str
    teaching_outline: list[str]
    core_knowledge_points: list[str]
    created_at: datetime
    updated_at: datetime


class KnowledgeNodeOut(BaseModel):
    """知识图谱节点。"""

    id: int
    node_key: str
    node_name: str
    node_type: str
    description: str | None
    level: int
    order_index: int
    mastery_rate: float | None = None


class KnowledgeEdgeOut(BaseModel):
    """知识图谱边。"""

    id: int
    source_node_id: int
    target_node_id: int
    relation_type: str
    weight: float
    source_node_key: str
    source_node_name: str
    target_node_key: str
    target_node_name: str


class KnowledgeGraphOut(BaseModel):
    """知识图谱响应。"""

    course_id: int
    course_title: str
    node_count: int
    edge_count: int
    nodes: list[KnowledgeNodeOut]
    edges: list[KnowledgeEdgeOut]


class KnowledgeGraphVisualNodeOut(BaseModel):
    """可视化节点结构。"""

    id: int
    name: str
    mastery_rate: float | None = None
    color: str
    node_type: str


class KnowledgeGraphVisualLinkOut(BaseModel):
    """可视化连线结构。"""

    source: int
    target: int
    relation: str


class KnowledgeGraphVisualOut(BaseModel):
    """ECharts 图谱接口结构。"""

    nodes: list[KnowledgeGraphVisualNodeOut]
    links: list[KnowledgeGraphVisualLinkOut]


class SupplementExerciseOut(BaseModel):
    """补充练习题响应结构。"""

    id: int
    course_id: int
    source_type: str
    question_type: str
    question_text: str
    options: list[str]
    answer: str | None
    analysis: str | None
    knowledge_point: str | None


class SupplementExerciseBatchOut(BaseModel):
    """补充练习题批次响应。"""

    course_id: int
    count: int
    exercises: list[SupplementExerciseOut]


class StudentVideoOut(BaseModel):
    """学生端视频资源。"""

    id: int
    file_name: str
    url: str
    created_at: datetime


class StudentLearningContentOut(BaseModel):
    """学生端学习页数据。"""

    course: CourseOut
    course_intro: str
    teaching_outline: list[str]
    core_knowledge_points: list[str]
    videos: list[StudentVideoOut]
    exercises: list[SupplementExerciseOut]


class StudentAnswerItem(BaseModel):
    """学生单题作答。"""

    exercise_id: int
    selected_option: str = Field(..., min_length=1, max_length=10)


class StudentSubmitRequest(BaseModel):
    """学生一次性提交请求。"""

    student_name: str = Field(..., min_length=1, max_length=100)
    answers: list[StudentAnswerItem]


class QuestionResultOut(BaseModel):
    """单题判分结果。"""

    exercise_id: int
    question_text: str
    selected_option: str
    correct_answer: str
    is_correct: bool
    score: float
    analysis: str | None
    knowledge_point: str | None


class StudentSubmitResultOut(BaseModel):
    """学生提交后的总结果。"""

    course_id: int
    course_title: str
    student_name: str
    total_score: float
    max_score: float
    accuracy: float
    correct_count: int
    wrong_count: int
    results: list[QuestionResultOut]


class WeakKnowledgePointOut(BaseModel):
    """薄弱知识点统计结果。"""

    knowledge_point: str
    accuracy: float
    total_answered: int


class RecommendedPracticeOut(BaseModel):
    """推荐补练题。"""

    source: str
    question_type: str
    question_text: str
    options: list[str]
    answer: str | None
    analysis: str | None
    knowledge_point: str


class PersonalizedRecommendationOut(BaseModel):
    """个性化补练推荐结果。"""

    course_id: int
    course_title: str
    student_name: str
    weak_knowledge_points: list[WeakKnowledgePointOut]
    recommended_exercises: list[RecommendedPracticeOut]
    learning_comment: str


# ---- 兼容旧模块（当前教师端最小版不会使用） ----
class ExerciseOut(BaseModel):
    id: int
    course_id: int
    source_type: str
    question_type: str | None = None
    question_text: str
    options_json: str | None = None
    reference_answer: str | None
    analysis: str | None = None
    knowledge_point: str | None

    class Config:
        from_attributes = True


class GeneratedContentOut(BaseModel):
    course_id: int
    outline: str
    knowledge_summary: str
    extra_exercises: list[dict]


class SubmitAnswerRequest(BaseModel):
    student_name: str = Field(..., min_length=1, max_length=100)
    exercise_id: int
    answer_text: str = Field(..., min_length=1)


class SubmissionOut(BaseModel):
    exercise_id: int
    score: float
    feedback: str


class LearningReportOut(BaseModel):
    student_name: str
    course_id: int
    performance_level: str
    weak_points: list[str]
    suggestion: str
    personalized_exercises: list[dict[str, str]]


class CourseContentOut(BaseModel):
    course: CourseOut
    generated: GeneratedContentOut | None
    exercises: list[ExerciseOut]
