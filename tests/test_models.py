import pytest
from pydantic import ValidationError

from src.models.profile import StudentProfile
from src.models.recommendations import ElectiveRecommendation, Subject


def test_student_profile_defaults():
    profile = StudentProfile(primary_career="Engineer")
    assert profile.career_confidence == 0.5
    assert profile.secondary_careers == []
    assert profile.academic_strengths == []
    assert profile.needs_immediate_employment is False


def test_student_profile_requires_primary_career():
    with pytest.raises(ValidationError):
        StudentProfile()


def test_student_profile_full(sample_profile):
    assert sample_profile.primary_career == "Nurse"
    assert sample_profile.career_confidence == 0.8
    assert len(sample_profile.academic_strengths) == 2
    assert len(sample_profile.work_values) == 2


def test_subject_track_literal():
    subject = Subject(
        name="Biology 1",
        cluster="Science, Technology, Engineering, and Mathematics",
        track="Academic",
        hours=80,
        semester="1st",
        description_snippet="Introduction to biology",
        relevance_reason="Matches nursing career",
    )
    assert subject.track == "Academic"

    with pytest.raises(ValidationError):
        Subject(
            name="Welding",
            cluster="Industrial Technologies",
            track="InvalidTrack",
            hours=320,
            semester="1st",
            description_snippet="...",
            relevance_reason="...",
        )


def test_elective_recommendation_structure(sample_profile):
    rec = ElectiveRecommendation(
        profile=sample_profile,
        recommendations=[
            Subject(
                name="Biology 1",
                cluster="STEM",
                track="Academic",
                hours=80,
                semester="1st",
                description_snippet="Cell biology fundamentals",
                relevance_reason="Essential for nursing",
            )
        ],
        doorway_electives=[],
        contradictions=[],
        career_pathway="Pre-Med / Allied Health",
        overall_confidence=0.85,
    )
    assert len(rec.recommendations) == 1
    assert rec.overall_confidence == 0.85
    assert rec.career_pathway == "Pre-Med / Allied Health"


def test_recommendation_default_confidence():
    rec = ElectiveRecommendation(
        profile=StudentProfile(primary_career="Chef"),
        recommendations=[],
        doorway_electives=[],
        contradictions=[],
        career_pathway="Culinary Arts",
    )
    assert rec.overall_confidence == 0.5
