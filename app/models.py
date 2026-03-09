"""ORM 数据模型定义（教师端最小版优先）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Course(Base):
    """课程信息（教师创建）。"""

    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    subject = Column(String(100), nullable=False, default="")
    difficulty_level = Column(String(30), nullable=False, default="中等")
    teaching_objective = Column(Text, nullable=False, default="")
    target_audience = Column(String(200), nullable=False, default="")
    description = Column(Text, nullable=True)  # 兼容旧字段，最小版可不使用
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    materials = relationship("Material", back_populates="course", cascade="all, delete-orphan")
    generated_content = relationship(
        "GeneratedContent",
        back_populates="course",
        uselist=False,
        cascade="all, delete-orphan",
    )
    exercises = relationship("Exercise", back_populates="course", cascade="all, delete-orphan")


class Material(Base):
    """教师上传的教学材料。"""

    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    material_type = Column(String(50), nullable=False)  # note / ppt / question_bank
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    extracted_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    course = relationship("Course", back_populates="materials")


class GeneratedContent(Base):
    """系统自动生成的课程内容。"""

    __tablename__ = "generated_contents"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), unique=True, nullable=False)
    course_intro = Column(Text, nullable=False, default="")
    teaching_outline_json = Column(Text, nullable=False, default="[]")
    core_knowledge_points_json = Column(Text, nullable=False, default="[]")
    raw_model_output = Column(Text, nullable=True)
    outline = Column(Text, nullable=False)
    knowledge_summary = Column(Text, nullable=False)
    extra_exercises_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    course = relationship("Course", back_populates="generated_content")


class Exercise(Base):
    """题目池（上传题、系统补充题、个性化题）。"""

    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    source_type = Column(String(50), nullable=False)  # uploaded / generated / personalized
    question_type = Column(String(50), nullable=False, default="single_choice")
    question_text = Column(Text, nullable=False)
    options_json = Column(Text, nullable=False, default="[]")
    reference_answer = Column(Text, nullable=True)
    analysis = Column(Text, nullable=True)
    knowledge_point = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    course = relationship("Course", back_populates="exercises")
    submissions = relationship("Submission", back_populates="exercise", cascade="all, delete-orphan")


class Student(Base):
    """学生实体（最小版只记录姓名）。"""

    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    submissions = relationship("Submission", back_populates="student", cascade="all, delete-orphan")


class Submission(Base):
    """学生答题记录与自动评分。"""

    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    answer_text = Column(Text, nullable=False)
    score = Column(Float, nullable=False)
    feedback = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    exercise = relationship("Exercise", back_populates="submissions")
    student = relationship("Student", back_populates="submissions")


class LearningReport(Base):
    """学习评价与个性化建议。"""

    __tablename__ = "learning_reports"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    performance_level = Column(String(50), nullable=False)
    weak_points_json = Column(Text, nullable=False)
    suggestion = Column(Text, nullable=False)
    personalized_exercises_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
