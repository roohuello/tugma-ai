from typing import Optional

from pydantic import BaseModel, Field


class StudentProfile(BaseModel):
    primary_career: str = Field(description="Student's main career aspiration")
    career_confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="How confident the student is in this career choice")
    secondary_careers: list[str] = Field(default_factory=list, description="Fallback career interests")
    academic_strengths: list[str] = Field(default_factory=list, description="e.g. Math, Science")
    academic_weaknesses: list[str] = Field(default_factory=list, description="e.g. Public Speaking")
    preferred_track: Optional[str] = Field(default=None, description="Academic, TechPro, or None if unsure")
    intended_college_course: Optional[str] = Field(default=None, description="If already planning tertiary education")
    hobbies: list[str] = Field(default_factory=list, description="e.g. Drawing, Cooking")
    extracurriculars: list[str] = Field(default_factory=list, description="e.g. Student Council, Debate Club")
    existing_skills: list[str] = Field(default_factory=list, description="e.g. Basic Python, Photo Editing")
    work_values: list[str] = Field(default_factory=list, description="e.g. Helping others, Creative freedom")
    work_environment: Optional[str] = Field(default=None, description="indoor, outdoor, or mixed")
    collaboration_style: Optional[str] = Field(default=None, description="team, solo, or mixed")
    needs_immediate_employment: bool = Field(default=False, description="Bias toward TechPro + NC II")
    financial_constraints: Optional[str] = Field(default=None, description="e.g. limited college budget")
