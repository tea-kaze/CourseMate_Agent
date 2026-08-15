"""出题与批改的结构化输出 Schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class QuestionItem(BaseModel):
    qtype: str = Field(description="题型：single 单选 / multiple 多选 / short 简答")
    topic: str = Field(default="", description="所属知识点")
    stem: str = Field(description="题干")
    options: list[str] = Field(
        default_factory=list,
        description="选择题选项（简答题为空列表）",
    )
    answer: str = Field(description="参考答案（选择题为正确选项内容或选项字母）")
    explanation: str = Field(default="", description="解析")


class QuestionSet(BaseModel):
    questions: list[QuestionItem] = Field(description="生成的题目列表")


class GradeResult(BaseModel):
    is_correct: bool = Field(description="作答是否正确")
    score: float = Field(ge=0, le=100, description="0-100 分")
    feedback: str = Field(description="批改反馈与错误原因")
    knowledge_point: str = Field(default="", description="涉及的知识点/建议复习内容")
