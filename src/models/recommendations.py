from typing import Literal

from pydantic import BaseModel, Field

from src.models.profile import StudentProfile


class Subject(BaseModel):
    name: str = Field(description="e.g. 'Biology 1'")
    cluster: str = Field(description="e.g. 'Science, Technology, Engineering, and Mathematics'")
    track: Literal["Academic", "TechPro"]
    hours: int = Field(description="80 or 320")
    semester: str = Field(description="1st or 2nd")
    description_snippet: str = Field(description="Brief description from DepEd curriculum")
    relevance_reason: str = Field(description="Personalized explanation for why this elective matches the student")


class ElectiveRecommendation(BaseModel):
    profile: StudentProfile
    recommendations: list[Subject] = Field(description="Ranked primary elective recommendations")
    doorway_electives: list[Subject] = Field(description="1-2 cross-track elective suggestions")
    contradictions: list[str] = Field(description="Flagged mismatches between career and profile")
    overall_confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Overall confidence in the recommendation set")
    career_pathway: str = Field(description="e.g. 'Pre-Med / Allied Health Sciences'")
