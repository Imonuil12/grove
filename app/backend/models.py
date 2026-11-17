from __future__ import annotations

from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, Text, Float, ForeignKey, UniqueConstraint, CheckConstraint, JSON
from datetime import datetime
from database import Base
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)   # identity comes from Cognito
    profile_data = Column(String, default="{}")        # unused legacy column
    created_at = Column(DateTime, default=datetime.utcnow)

    username = Column(String, unique=True, nullable=True, index=True)
    external_id = Column(String, unique=True, nullable=True)
    display_name = Column(String, nullable=True)

    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    intakes_legacy = relationship("IntakeForm", back_populates="user", cascade="all, delete-orphan")
    mastery_records_legacy = relationship("MasteryRecord", back_populates="user", cascade="all, delete-orphan")
    assessment_queue_legacy = relationship("AssessmentQueue", back_populates="user", cascade="all, delete-orphan")

    user_intakes = relationship("UserIntake", back_populates="user", cascade="all, delete-orphan")
    user_warnings = relationship("UserWarning", back_populates="user", cascade="all, delete-orphan")
    lesson_progress = relationship("UserLessonProgress", back_populates="user", cascade="all, delete-orphan")
    quiz_attempts = relationship("UserQuizAttempt", back_populates="user", cascade="all, delete-orphan")
    topic_mastery = relationship("UserTopicMastery", back_populates="user", cascade="all, delete-orphan")
    objective_mastery = relationship("UserObjectiveMastery", back_populates="user", cascade="all, delete-orphan")

class LocalCredential(Base):
    """Email/password login for built-in accounts (used when Cognito is off)."""
    __tablename__ = "local_credentials"

    credential_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", name="fk_local_credential_user"), nullable=False, unique=True)
    email = Column(String(254), nullable=False, unique=True, index=True)
    password_hash = Column(String(300), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)


class UserSession(Base):
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String, unique=True, index=True) # E.g., username or email
    topic = Column(String, default="Amoxicillin") # Current topic
    archetype = Column(String, default="The Skeptic")
    has_done_intake = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sessions")

class IntakeForm(Base):
    __tablename__ = "intakes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String, index=True)
    penicillin_allergy = Column(Boolean, default=False)
    anaphylaxis_history = Column(Boolean, default=False)
    mono_suspected = Column(Boolean, default=False)
    kidney_disease = Column(Boolean, default=False)
    breastfeeding = Column(Boolean, default=False)
    pregnancy_status = Column(String)
    meds_text = Column(String)

    user = relationship("User", back_populates="intakes_legacy")

class MasteryRecord(Base):
    __tablename__ = "mastery_records"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String, index=True)
    topic = Column(String, index=True) # "Amoxicillin" or "Ibuprofen"
    objective_id = Column(String, index=True) # e.g. "A-F1"
    status = Column(String, default="Unknown") # "Unknown" or "Known"

    user = relationship("User", back_populates="mastery_records_legacy")
    
class AssessmentQueue(Base):
    __tablename__ = "assessment_queue"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String, index=True)
    objective_id = Column(String)
    order_index = Column(Integer)
    is_current = Column(Boolean, default=False)

    user = relationship("User", back_populates="assessment_queue_legacy")

# =========================
# NEW GENERALIZED CONTENT MODELS
# For drugs, conditions, risk factors, prevention, lessons, quizzes
# =========================

class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name", "domain", name="uq_category_name_domain"),)

    category_id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    domain = Column(String(50), nullable=False)  # drug, condition, prevention, risk_factor, mixed
    display_order = Column(Integer, nullable=False, default=0, server_default="0")

    topics = relationship("Topic", back_populates="category")


class Topic(Base, TimestampMixin):
    __tablename__ = "topics"

    topic_id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.category_id"), nullable=False)

    title = Column(String(200), nullable=False)
    description = Column(Text)
    difficulty_level = Column(String(50))
    topic_code = Column(String(50), unique=True)
    topic_type = Column(String(50), nullable=True)  # drug, condition, risk_factor, prevention, general

    category = relationship("Category", back_populates="topics")
    lessons = relationship("Lesson", back_populates="topic", cascade="all, delete-orphan")
    quizzes = relationship("Quiz", back_populates="topic", cascade="all, delete-orphan")
    condition_links = relationship("TopicCondition", back_populates="topic", cascade="all, delete-orphan")
    drug_links = relationship("TopicDrug", back_populates="topic", cascade="all, delete-orphan")
    mastery_records = relationship("UserTopicMastery", back_populates="topic", cascade="all, delete-orphan")


class Lesson(Base, TimestampMixin):
    __tablename__ = "lessons"
    __table_args__ = (
        UniqueConstraint("topic_id", "objective_code", name="uq_lesson_topic_objective"),
        CheckConstraint("display_order >= 1", name="ck_lesson_order"),
    )

    lesson_id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.topic_id"), nullable=False)

    lesson_type = Column(String(50), default="interactive")
    title = Column(String(200), nullable=False)
    content_or_url = Column(Text, nullable=False)
    est_minutes = Column(Integer)
    objective_code = Column(String(20), index=True)
    objective_text = Column(Text)
    category_label = Column(String(50))
    remediation_text = Column(Text)
    display_order = Column(Integer, default=1)

    topic = relationship("Topic", back_populates="lessons")
    contents = relationship("LessonContent", back_populates="lesson", cascade="all, delete-orphan")
    progress_records = relationship("UserLessonProgress", back_populates="lesson", passive_deletes="all")
    objective_mastery = relationship("UserObjectiveMastery", back_populates="lesson", passive_deletes="all")


class LessonContent(Base):
    """A lesson's explanation for one experience level, preserving text variants."""
    __tablename__ = "lesson_contents"
    __table_args__ = (UniqueConstraint("lesson_id", "experience_level", name="uq_lesson_content_level"),)

    content_id = Column(Integer, primary_key=True)
    lesson_id = Column(Integer, ForeignKey("lessons.lesson_id", name="fk_lesson_contents_lesson_id_lessons"), nullable=False)
    experience_level = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    lesson = relationship("Lesson", back_populates="contents")


class Quiz(Base, TimestampMixin):
    __tablename__ = "quizzes"
    __table_args__ = (CheckConstraint("passing_score BETWEEN 0 AND 100", name="ck_quiz_passing_score"),)

    quiz_id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.topic_id"), nullable=False)

    title = Column(String(200), nullable=False)
    passing_score = Column(Integer, default=70)
    quiz_type = Column(String(30), default="checkpoint")  # pretest, checkpoint, final

    topic = relationship("Topic", back_populates="quizzes")
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")
    attempts = relationship("UserQuizAttempt", back_populates="quiz", passive_deletes="all")


class Question(Base, TimestampMixin):
    __tablename__ = "questions"
    __table_args__ = (CheckConstraint("display_order >= 1", name="ck_question_order"),)

    question_id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.quiz_id"), nullable=False)

    question_text = Column(Text, nullable=False)
    question_type = Column(String(30), default="short_text")  # short_text, mcq, multi_select
    objective_code = Column(String(20), index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.lesson_id", name="fk_questions_lesson_id_lessons"), nullable=True, index=True)
    explanation_text = Column(Text)
    display_order = Column(Integer, default=1)

    quiz = relationship("Quiz", back_populates="questions")
    lesson = relationship("Lesson")
    answer_choices = relationship("AnswerChoice", back_populates="question", cascade="all, delete-orphan")
    keyword_sets = relationship("AcceptedKeywordSet", back_populates="question", cascade="all, delete-orphan")
    responses = relationship("UserQuizResponse", back_populates="question", passive_deletes="all")


class AnswerChoice(Base):
    __tablename__ = "answer_choices"

    choice_id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.question_id"), nullable=False)

    choice_text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False)

    question = relationship("Question", back_populates="answer_choices")


class AcceptedKeywordSet(Base):
    __tablename__ = "accepted_keyword_sets"
    __table_args__ = (
        UniqueConstraint("question_id", "set_order", name="uq_question_keyword_order"),
        CheckConstraint("set_order >= 1", name="ck_keyword_order"),
        CheckConstraint("length(trim(keywords_csv)) > 0", name="ck_keyword_nonempty"),
    )

    keyword_set_id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.question_id"), nullable=False)

    set_order = Column(Integer, default=1, nullable=False)
    keywords_csv = Column(Text, nullable=False)  # example: "trouble,breathing"

    question = relationship("Question", back_populates="keyword_sets")


# =========================
# DOMAIN TABLES
# =========================

class DrugClass(Base):
    __tablename__ = "drug_classes"

    drug_class_id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True)
    description_short = Column(Text)

    drugs = relationship("Drug", back_populates="drug_class")


class Drug(Base, TimestampMixin):
    __tablename__ = "drugs"

    drug_id = Column(Integer, primary_key=True)
    drug_class_id = Column(Integer, ForeignKey("drug_classes.drug_class_id"), nullable=True)

    generic_name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(100), unique=True, nullable=False)
    brand_names = Column(Text)
    description_short = Column(Text)
    warnings = Column(Text)

    drug_class = relationship("DrugClass", back_populates="drugs")
    aliases = relationship("DrugAlias", back_populates="drug", cascade="all, delete-orphan")
    topic_links = relationship("TopicDrug", back_populates="drug", cascade="all, delete-orphan")
    intakes = relationship("UserIntake", back_populates="drug", passive_deletes="all")


class DrugAlias(Base):
    __tablename__ = "drug_aliases"

    alias_id = Column(Integer, primary_key=True)
    drug_id = Column(Integer, ForeignKey("drugs.drug_id"), nullable=False)

    alias_text = Column(String(100), nullable=False)
    alias_type = Column(String(50))

    drug = relationship("Drug", back_populates="aliases")


class Condition(Base, TimestampMixin):
    __tablename__ = "conditions"

    condition_id = Column(Integer, primary_key=True)
    name = Column(String(150), unique=True, nullable=False)
    description_short = Column(Text)
    body_system = Column(String(50))
    severity_classification = Column(String(50))
    is_chronic = Column(Boolean)
    is_preventable = Column(Boolean)

    aliases = relationship("ConditionAlias", back_populates="condition", cascade="all, delete-orphan")
    topic_links = relationship("TopicCondition", back_populates="condition", cascade="all, delete-orphan")
    risk_factor_links = relationship("ConditionRiskFactor", back_populates="condition", cascade="all, delete-orphan")


class ConditionAlias(Base):
    __tablename__ = "condition_aliases"

    alias_id = Column(Integer, primary_key=True)
    condition_id = Column(Integer, ForeignKey("conditions.condition_id"), nullable=False)

    alias_text = Column(String(150), nullable=False)
    alias_type = Column(String(50))
    language = Column(String(50), default="english")
    created_at = Column(DateTime, default=datetime.utcnow)

    condition = relationship("Condition", back_populates="aliases")


class TopicCondition(Base):
    __tablename__ = "topic_conditions"

    topic_id = Column(Integer, ForeignKey("topics.topic_id"), primary_key=True)
    condition_id = Column(Integer, ForeignKey("conditions.condition_id"), primary_key=True)
    relationship_type = Column(String(50))

    topic = relationship("Topic", back_populates="condition_links")
    condition = relationship("Condition", back_populates="topic_links")


class TopicDrug(Base):
    __tablename__ = "topic_drugs"

    topic_id = Column(Integer, ForeignKey("topics.topic_id"), primary_key=True)
    drug_id = Column(Integer, ForeignKey("drugs.drug_id"), primary_key=True)
    relationship_type = Column(String(50))

    topic = relationship("Topic", back_populates="drug_links")
    drug = relationship("Drug", back_populates="topic_links")


class RiskFactor(Base):
    __tablename__ = "risk_factors"

    risk_factor_id = Column(Integer, primary_key=True)
    name = Column(String(150), unique=True, nullable=False)
    type = Column(String(50))
    description_short = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    condition_links = relationship("ConditionRiskFactor", back_populates="risk_factor", cascade="all, delete-orphan")
    strategy_links = relationship("RiskFactorStrategy", back_populates="risk_factor", cascade="all, delete-orphan")


class ConditionRiskFactor(Base):
    __tablename__ = "condition_risk_factors"

    condition_id = Column(Integer, ForeignKey("conditions.condition_id"), primary_key=True)
    risk_factor_id = Column(Integer, ForeignKey("risk_factors.risk_factor_id"), primary_key=True)

    relationship_type = Column(String(50))
    strength_level = Column(String(50))

    condition = relationship("Condition", back_populates="risk_factor_links")
    risk_factor = relationship("RiskFactor", back_populates="condition_links")


class PreventionStrategy(Base):
    __tablename__ = "prevention_strategies"

    strategy_id = Column(Integer, primary_key=True)
    name = Column(String(150), unique=True, nullable=False)
    prevention_type = Column(String(50))
    description_short = Column(Text)
    effort_level = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    risk_factor_links = relationship("RiskFactorStrategy", back_populates="strategy", cascade="all, delete-orphan")


class RiskFactorStrategy(Base):
    __tablename__ = "risk_factor_strategies"

    risk_factor_id = Column(Integer, ForeignKey("risk_factors.risk_factor_id"), primary_key=True)
    strategy_id = Column(Integer, ForeignKey("prevention_strategies.strategy_id"), primary_key=True)

    risk_factor = relationship("RiskFactor", back_populates="strategy_links")
    strategy = relationship("PreventionStrategy", back_populates="risk_factor_links")


# =========================
# NEW USER LEARNING TABLES
# =========================

class UserIntake(Base):
    __tablename__ = "user_intakes"

    intake_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    drug_id = Column(Integer, ForeignKey("drugs.drug_id"), nullable=True)

    penicillin_allergy = Column(Boolean, default=False)
    anaphylaxis_history = Column(Boolean, default=False)
    mono_suspected = Column(Boolean, default=False)
    kidney_disease = Column(Boolean, default=False)
    breastfeeding = Column(Boolean, default=False)
    pregnancy_status = Column(String(30), default="Unknown")
    meds_text = Column(Text, default="")
    # Snapshot all fields currently accepted by IntakeRequest. Repeated intake
    # submissions are historical rows rather than edits to one user JSON blob.
    dob = Column(String(10))
    gender = Column(String(50))
    archetype = Column(String(100))
    experience_level = Column(String(50))
    alcohol_drinks_per_week = Column(Integer)
    cigarette_use = Column(String(50))
    cigarette_years = Column(Integer)
    meals_per_day = Column(String(50))
    skips_meals = Column(String(50))
    water_cups = Column(Integer)
    fruit_veg_servings = Column(Integer)
    diet_type = Column(String(100))
    calorie_restrict = Column(String(50))
    caffeine = Column(String(50))
    sleep_hours = Column(Integer)
    sleep_quality = Column(String(50))
    trouble_falling_asleep = Column(Boolean)
    waking_night = Column(Boolean)
    waking_early = Column(Boolean)
    stress_level = Column(Integer)
    mood = Column(String(50))
    stress_practices = Column(JSON)
    exercise_days = Column(Integer)
    activity_types = Column(JSON)
    sedentary_level = Column(String(50))
    chronic_pain = Column(Boolean)
    limited_mobility = Column(Boolean)
    fall_risk = Column(Boolean)
    polypharmacy = Column(Boolean)
    renal_decline = Column(Boolean)
    provided_fields = Column(JSON)  # Field names only, for exact legacy response compatibility.
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="user_intakes")
    drug = relationship("Drug", back_populates="intakes")
    warnings = relationship("UserWarning", back_populates="intake", cascade="all, delete-orphan")


class UserWarning(Base):
    __tablename__ = "user_warnings"

    warning_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    intake_id = Column(Integer, ForeignKey("user_intakes.intake_id"), nullable=True)

    warning_text = Column(Text, nullable=False)
    warning_type = Column(String(50), default="safety")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="user_warnings")
    intake = relationship("UserIntake", back_populates="warnings")


class UserLessonProgress(Base):
    __tablename__ = "user_lesson_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_user_lesson"),
        CheckConstraint("percent_complete BETWEEN 0 AND 100", name="ck_lesson_percent"),
        CheckConstraint("status IN ('not_started', 'in_progress', 'completed')", name="ck_lesson_status"),
    )

    progress_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.lesson_id"), nullable=False)

    status = Column(String(30), default="not_started")
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    percent_complete = Column(Integer, default=0)
    last_updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="lesson_progress")
    lesson = relationship("Lesson", back_populates="progress_records")


class UserQuizAttempt(Base):
    __tablename__ = "user_quiz_attempts"
    __table_args__ = (CheckConstraint("score BETWEEN 0 AND 100", name="ck_attempt_score"),)

    attempt_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    quiz_id = Column(Integer, ForeignKey("quizzes.quiz_id"), nullable=False)

    attempt_type = Column(String(20), default="pre")
    score = Column(Integer, default=0)
    passed = Column(Boolean, default=False)
    completed_at = Column(DateTime, default=datetime.utcnow)
    submission_id = Column(Integer, ForeignKey("assessment_submissions.submission_id", name="fk_attempt_submission"), index=True)

    user = relationship("User", back_populates="quiz_attempts")
    quiz = relationship("Quiz", back_populates="attempts")
    responses = relationship("UserQuizResponse", back_populates="attempt", cascade="all, delete-orphan")


class UserQuizResponse(Base):
    __tablename__ = "user_quiz_responses"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question"),)

    response_id = Column(Integer, primary_key=True)
    attempt_id = Column(Integer, ForeignKey("user_quiz_attempts.attempt_id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.question_id"), nullable=False)

    user_answer = Column(Text, default="")
    is_correct = Column(Boolean, default=False)
    feedback_text = Column(Text)
    display_order = Column(Integer, default=0, server_default="0", nullable=False)
    question_text = Column(Text)
    objective_code = Column(String(20))
    category_label = Column(String(100))

    attempt = relationship("UserQuizAttempt", back_populates="responses")
    question = relationship("Question", back_populates="responses")


class UserTopicMastery(Base):
    __tablename__ = "user_topic_mastery"
    __table_args__ = (UniqueConstraint("user_id", "topic_id", name="uq_user_topic_mastery"),)

    mastery_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.topic_id"), nullable=False)

    mastery_level = Column(Integer, default=0)
    mastery_score = Column(Float, default=0.0)
    last_assessed_at = Column(DateTime, default=datetime.utcnow)
    evidence_source = Column(String(100))
    notes = Column(Text)

    user = relationship("User", back_populates="topic_mastery")
    topic = relationship("Topic", back_populates="mastery_records")


class UserObjectiveMastery(Base):
    __tablename__ = "user_objective_mastery"
    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", "objective_code", name="uq_user_objective_mastery"),
        CheckConstraint("length(trim(objective_code)) > 0", name="ck_objective_code"),
        CheckConstraint("mastery_label IN ('Known', 'Unknown')", name="ck_objective_mastery_label"),
        CheckConstraint("correct_streak >= 0", name="ck_objective_correct_streak"),
        CheckConstraint("crown_level BETWEEN 0 AND 5", name="ck_objective_crown"),
    )

    objective_mastery_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.lesson_id"), nullable=False)

    objective_code = Column(String(20), nullable=False)
    mastery_label = Column(String(20), default="Unknown", nullable=False)
    correct_streak = Column(Integer, default=0, nullable=False)
    crown_level = Column(Integer, default=0, server_default="0", nullable=False)
    last_practiced = Column(Date)
    last_assessed_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="objective_mastery")
    lesson = relationship("Lesson", back_populates="objective_mastery")

# Conversation history used by the current chatbot API.
class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, unique=True, index=True)
    username = Column(String, index=True)
    title = Column(String, default="New Conversation")
    drug = Column(String, default="amoxicillin")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    conversation_id = Column(String, index=True, nullable=True)
    sender = Column(String)  # "user" or "bot"
    message = Column(String)
    drug = Column(String, default="amoxicillin")
    archetype = Column(String, default="Needs more explanations")
    has_safety_warning = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow)


class UserLearningState(Base):
    """User-wide preferences and gamification stored in relational columns."""
    __tablename__ = "user_learning_state"
    __table_args__ = (
        CheckConstraint("hearts_remaining BETWEEN 0 AND 5", name="ck_state_hearts"),
        CheckConstraint("xp_total >= 0 AND streak_current >= 0 AND streak_longest >= 0", name="ck_state_counters"),
    )
    user_id = Column(Integer, ForeignKey("users.id", name="fk_learning_state_user"), primary_key=True)
    selected_drug_id = Column(Integer, ForeignKey("drugs.drug_id", name="fk_learning_state_drug"), nullable=False)
    archetype = Column(String(100), nullable=False, default="needs more explanations")
    experience_level = Column(String(50))
    latest_intake_id = Column(Integer, ForeignKey("user_intakes.intake_id", name="fk_learning_state_intake"))
    active_run_id = Column(Integer, ForeignKey("user_lesson_runs.run_id", name="fk_learning_state_run"))
    xp_total = Column(Integer, nullable=False, default=0)
    streak_current = Column(Integer, nullable=False, default=0)
    streak_longest = Column(Integer, nullable=False, default=0)
    last_active_date = Column(Date)
    hearts_remaining = Column(Integer, nullable=False, default=5)
    migrated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    version_id = Column(Integer, nullable=False, default=1, server_default="1")
    __mapper_args__ = {"version_id_col": version_id}


class UserBadge(Base):
    __tablename__ = "user_badges"
    __table_args__ = (UniqueConstraint("user_id", "badge_code", name="uq_user_badge"),)
    badge_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", name="fk_badge_user"), nullable=False, index=True)
    badge_code = Column(String(100), nullable=False)
    display_order = Column(Integer, nullable=False)
    awarded_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AssessmentSubmission(Base):
    """Groups category-specific quiz attempts into one submitted assessment."""
    __tablename__ = "assessment_submissions"
    submission_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", name="fk_submission_user"), nullable=False, index=True)
    drug_id = Column(Integer, ForeignKey("drugs.drug_id", name="fk_submission_drug"), nullable=False)
    kind = Column(String(30), nullable=False)  # initial, checkpoint, lesson, legacy_results
    imported = Column(Boolean, nullable=False, default=False)
    submitted_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class UserDrugProgress(Base):
    __tablename__ = "user_drug_progress"
    __table_args__ = (UniqueConstraint("user_id", "drug_id", name="uq_user_drug_progress"),)
    progress_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", name="fk_drug_progress_user"), nullable=False)
    drug_id = Column(Integer, ForeignKey("drugs.drug_id", name="fk_drug_progress_drug"), nullable=False)
    last_submission_id = Column(Integer, ForeignKey("assessment_submissions.submission_id", name="fk_drug_progress_submission"))


class UserLearningQueue(Base):
    __tablename__ = "user_learning_queue"
    __table_args__ = (
        UniqueConstraint("user_id", "drug_id", "kind", "lesson_id", name="uq_learning_queue_item"),
        CheckConstraint("kind IN ('plan', 'review')", name="ck_learning_queue_kind"),
    )
    queue_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", name="fk_queue_user"), nullable=False)
    drug_id = Column(Integer, ForeignKey("drugs.drug_id", name="fk_queue_drug"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.lesson_id", name="fk_queue_lesson"), nullable=False)
    kind = Column(String(20), nullable=False)
    display_order = Column(Integer, nullable=False)
    question_text = Column(Text)
    remediation_text = Column(Text)
    category_label = Column(String(100))


class UserLessonRun(Base):
    __tablename__ = "user_lesson_runs"
    __table_args__ = (
        CheckConstraint("hearts BETWEEN 0 AND 5", name="ck_run_hearts"),
        CheckConstraint("position >= 0 AND combo >= 0 AND xp_earned >= 0 AND correct_count >= 0", name="ck_run_counters"),
    )
    run_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", name="fk_run_user"), nullable=False, index=True)
    drug_id = Column(Integer, ForeignKey("drugs.drug_id", name="fk_run_drug"), nullable=False)
    category = Column(String(100), nullable=False)
    position = Column(Integer, nullable=False, default=0)
    hearts = Column(Integer, nullable=False, default=5)
    combo = Column(Integer, nullable=False, default=0)
    xp_earned = Column(Integer, nullable=False, default=0)
    correct_count = Column(Integer, nullable=False, default=0)
    total = Column(Integer, nullable=False)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)


class UserLessonRunItem(Base):
    __tablename__ = "user_lesson_run_items"
    __table_args__ = (UniqueConstraint("run_id", "position", name="uq_run_position"),)
    item_id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("user_lesson_runs.run_id", name="fk_run_item_run"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.lesson_id", name="fk_run_item_lesson"), nullable=False)
    position = Column(Integer, nullable=False)
    missed = Column(Boolean, nullable=False, default=False)
