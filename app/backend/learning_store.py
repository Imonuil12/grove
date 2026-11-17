"""Relational persistence with the existing API's dictionary response shapes.

Dictionary state is an in-memory view only; learning data lives in SQL rows.
"""
from copy import deepcopy
from datetime import date, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from curriculum import drug_content, load_catalog
import models as m


def blank_state():
    return dict(selected_drug="amoxicillin", archetype="needs more explanations", intake={}, warnings=[],
                assessment_answers={}, objective_mastery={}, lesson_queue=[], last_results=[], xp_total=0,
                streak_current=0, streak_longest=0, last_active_date=None, hearts_remaining=5,
                badges=[], current_lesson=None, review_items=[])


def as_date(value):
    return date.fromisoformat(value) if isinstance(value, str) and value else value


def get_or_create_user(db, username):
    user = db.query(m.User).filter_by(email=username).one_or_none()
    if user is None:
        user = m.User(email=username, profile_data="{}")
        db.add(user)
        db.flush()
    return user


def initialize_user(db, user, drug_key="amoxicillin"):
    row = m.UserLearningState(user_id=user.id, selected_drug_id=drug_content(db, drug_key)["drug_id"])
    db.add(row)
    db.flush()
    return row


def _course(db, user_id, drug_id):
    course = db.query(m.UserDrugProgress).filter_by(user_id=user_id, drug_id=drug_id).one_or_none()
    if course is None:
        course = m.UserDrugProgress(user_id=user_id, drug_id=drug_id)
        db.add(course)
        db.flush()
    return course


def intake_dict(db, user, row):
    if row is None:
        return {}
    fields = row.provided_fields
    excluded = {"intake_id", "user_id", "drug_id", "created_at", "provided_fields"}
    result = {column.name: getattr(row, column.name) for column in m.UserIntake.__table__.columns
              if column.name not in excluded and (column.name in fields if fields is not None else getattr(row, column.name) is not None)}
    if fields is None or "username" in fields:
        result["username"] = user.email
    if fields is None or "drug" in fields:
        result["drug"] = db.get(m.Drug, row.drug_id).generic_name if row.drug_id else "amoxicillin"
    return result


def result_rows(db, submission_id):
    if not submission_id:
        return []
    rows = (db.query(m.UserQuizResponse, m.Question, m.Lesson, m.Topic, m.Category)
            .join(m.UserQuizAttempt, m.UserQuizResponse.attempt_id == m.UserQuizAttempt.attempt_id)
            .join(m.Question, m.UserQuizResponse.question_id == m.Question.question_id)
            .join(m.Lesson, m.Question.lesson_id == m.Lesson.lesson_id)
            .join(m.Topic, m.Lesson.topic_id == m.Topic.topic_id)
            .join(m.Category, m.Topic.category_id == m.Category.category_id)
            .filter(m.UserQuizAttempt.submission_id == submission_id)
            .order_by(m.UserQuizResponse.display_order, m.UserQuizResponse.response_id).all())
    return [{"oid": response.objective_code or question.objective_code, "correct": response.is_correct, "message": response.feedback_text,
             "question": response.question_text if response.question_text is not None else question.question_text,
             "category": response.category_label if response.category_label is not None else category.name}
            for response, question, lesson, topic, category in rows]


def _ensure_user(db, username):
    """A new user's first page load fires several requests at once, and each one
    tries to create the same rows. The loser of that race rolls back and reads
    the rows the winner committed instead of failing with a 500."""
    for attempt in range(2):
        try:
            user = get_or_create_user(db, username)
            preferences = db.get(m.UserLearningState, user.id) or initialize_user(db, user)
            return user, preferences
        except IntegrityError:
            if attempt:
                raise
            db.rollback()


def get_state(username, db: Session, drug=None):
    user, preferences = _ensure_user(db, username)
    selected = db.get(m.Drug, preferences.selected_drug_id).generic_name
    scope = (drug or selected).lower()
    curriculum = drug_content(db, scope)
    state = blank_state()
    state.update(selected_drug=selected, archetype=preferences.archetype, experience_level=preferences.experience_level,
                 xp_total=preferences.xp_total, streak_current=preferences.streak_current,
                 streak_longest=preferences.streak_longest, hearts_remaining=preferences.hearts_remaining,
                 last_active_date=preferences.last_active_date.isoformat() if preferences.last_active_date else None)
    intake = db.get(m.UserIntake, preferences.latest_intake_id) if preferences.latest_intake_id else None
    state["intake"] = intake_dict(db, user, intake)
    state["warnings"] = [row.warning_text for row in db.query(m.UserWarning).filter_by(user_id=user.id, intake_id=preferences.latest_intake_id).order_by(m.UserWarning.warning_id)]
    state["badges"] = [row.badge_code for row in db.query(m.UserBadge).filter_by(user_id=user.id).order_by(m.UserBadge.display_order)]
    objective_by_lesson = {obj.lesson_id: obj for obj in curriculum["objectives"]}
    for record in db.query(m.UserObjectiveMastery).filter_by(user_id=user.id).filter(m.UserObjectiveMastery.lesson_id.in_(objective_by_lesson)):
        # The current API identifies objectives by code within a drug.
        state["objective_mastery"][record.objective_code] = {
            "level": record.mastery_label, "correct_streak": record.correct_streak, "crown_level": record.crown_level,
            "last_practiced": record.last_practiced.isoformat() if record.last_practiced else None}
    for item in db.query(m.UserLearningQueue).filter_by(user_id=user.id, drug_id=curriculum["drug_id"]).order_by(m.UserLearningQueue.display_order):
        obj = objective_by_lesson.get(item.lesson_id)
        if obj is None:
            continue
        if item.kind == "plan":
            state["lesson_queue"].append(obj.oid)
        else:
            state["review_items"].append({"oid": obj.oid, "question": item.question_text or obj.question,
                                           "remediation": item.remediation_text or obj.remediation_lesson,
                                           "category": item.category_label or obj.category})
    course = db.query(m.UserDrugProgress).filter_by(user_id=user.id, drug_id=curriculum["drug_id"]).one_or_none()
    state["last_results"] = result_rows(db, course.last_submission_id if course else None)
    if preferences.active_run_id:
        run = db.get(m.UserLessonRun, preferences.active_run_id)
        run_drug = db.get(m.Drug, run.drug_id).generic_name
        all_lessons = {row.lesson_id: row for row in db.query(m.Lesson).all()}
        items = db.query(m.UserLessonRunItem).filter_by(run_id=run.run_id).order_by(m.UserLessonRunItem.position).all()
        state["current_lesson"] = dict(drug=run_drug, category=run.category,
            oids=[all_lessons[item.lesson_id].objective_code for item in items], index=run.position,
            hearts=run.hearts, combo=run.combo, xp_earned=run.xp_earned, total=run.total, correct_count=run.correct_count)
        missed = [all_lessons[item.lesson_id].objective_code for item in items if item.missed]
        if missed:
            state["current_lesson"]["missed_oids"] = missed
    state["_drug"] = scope
    state["_version"] = preferences.version_id
    state["_original"] = deepcopy(state)
    return state


def _replace_queue(db, user_id, drug_id, kind, entries, objectives):
    db.query(m.UserLearningQueue).filter_by(user_id=user_id, drug_id=drug_id, kind=kind).delete(synchronize_session=False)
    for position, value in enumerate(entries):
        code = value if isinstance(value, str) else value["oid"]
        if code not in objectives:
            raise ValueError(f"Unknown queued objective {code!r}")
        data = {} if isinstance(value, str) else dict(question_text=value.get("question"), remediation_text=value.get("remediation"), category_label=value.get("category"))
        db.add(m.UserLearningQueue(user_id=user_id, drug_id=drug_id, lesson_id=objectives[code].lesson_id,
                                  kind=kind, display_order=position, **data))


def _save_run(db, user_id, preferences, value):
    if value is None:
        if preferences.active_run_id:
            db.get(m.UserLessonRun, preferences.active_run_id).completed_at = datetime.utcnow()
        preferences.active_run_id = None
        return
    curriculum = drug_content(db, value["drug"])
    objectives = {obj.oid: obj for obj in curriculum["objectives"]}
    run = db.get(m.UserLessonRun, preferences.active_run_id) if preferences.active_run_id else None
    old_items = db.query(m.UserLessonRunItem).filter_by(run_id=run.run_id).order_by(m.UserLessonRunItem.position).all() if run else []
    new_lessons = [objectives[code].lesson_id for code in value["oids"]]
    if run is None or run.drug_id != curriculum["drug_id"] or run.category != value["category"] or [item.lesson_id for item in old_items] != new_lessons:
        if run:
            run.completed_at = datetime.utcnow()
        run = m.UserLessonRun(user_id=user_id, drug_id=curriculum["drug_id"], category=value["category"], total=value["total"])
        db.add(run)
        db.flush()
        preferences.active_run_id = run.run_id
        old_items = []
        for position, lesson_id in enumerate(new_lessons):
            item = m.UserLessonRunItem(run_id=run.run_id, lesson_id=lesson_id, position=position)
            db.add(item)
            old_items.append(item)
    for attribute, key in (("position", "index"), ("hearts", "hearts"), ("combo", "combo"), ("xp_earned", "xp_earned"), ("correct_count", "correct_count"), ("total", "total")):
        setattr(run, attribute, value.get(key, 0))
    for item, code in zip(old_items, value["oids"]):
        item.missed = code in value.get("missed_oids", [])


def save_state(username, state, db: Session, commit=True):
    user = get_or_create_user(db, username)
    preferences = db.get(m.UserLearningState, user.id)
    scope = state.get("_drug", state.get("selected_drug", "amoxicillin"))
    if state.get("_version", preferences.version_id) != preferences.version_id:
        raise StaleDataError("Learning state was updated by another request")
    # Version every write, including updates which only affect child rows.
    # SQLAlchemy rejects concurrent saves based on an older state snapshot.
    preferences.version_id += 1
    curriculum = drug_content(db, scope)
    objectives = {obj.oid: obj for obj in curriculum["objectives"]}
    old = state.get("_original", {})
    for field in ("archetype", "experience_level", "xp_total", "streak_current", "streak_longest", "hearts_remaining"):
        if field in state and state[field] != old.get(field):
            setattr(preferences, field, state[field])
    if state.get("selected_drug") != old.get("selected_drug"):
        preferences.selected_drug_id = drug_content(db, state["selected_drug"])["drug_id"]
    if state.get("last_active_date") != old.get("last_active_date"):
        preferences.last_active_date = as_date(state.get("last_active_date"))
    if state.get("intake", {}) != old.get("intake", {}):
        payload = state.get("intake", {})
        allowed = {column.name for column in m.UserIntake.__table__.columns} - {"intake_id", "user_id", "drug_id", "created_at", "provided_fields"}
        snapshot = m.UserIntake(user_id=user.id, drug_id=drug_content(db, payload.get("drug", scope))["drug_id"],
                                provided_fields=list(payload), **{key: value for key, value in payload.items() if key in allowed})
        db.add(snapshot)
        db.flush()
        preferences.latest_intake_id = snapshot.intake_id
        preferences.experience_level = payload.get("experience_level", preferences.experience_level)
        for warning in state.get("warnings", []):
            db.add(m.UserWarning(user_id=user.id, intake_id=snapshot.intake_id, warning_text=warning))
    elif state.get("warnings", []) != old.get("warnings", []):
        db.query(m.UserWarning).filter_by(user_id=user.id, intake_id=preferences.latest_intake_id).delete(synchronize_session=False)
        for warning in state.get("warnings", []):
            db.add(m.UserWarning(user_id=user.id, intake_id=preferences.latest_intake_id, warning_text=warning))
    if state.get("badges", []) != old.get("badges", []):
        existing = {row.badge_code for row in db.query(m.UserBadge).filter_by(user_id=user.id)}
        for position, code in enumerate(state.get("badges", [])):
            if code not in existing:
                db.add(m.UserBadge(user_id=user.id, badge_code=code, display_order=position))
    if state.get("objective_mastery", {}) != old.get("objective_mastery", {}):
        existing = {(row.lesson_id, row.objective_code): row for row in db.query(m.UserObjectiveMastery).filter_by(user_id=user.id)}
        for code, value in state.get("objective_mastery", {}).items():
            if code not in objectives:
                raise ValueError(f"Unknown mastery objective {code!r} for {scope}")
            obj = objectives[code]
            row = existing.get((obj.lesson_id, code))
            if row is None:
                row = m.UserObjectiveMastery(user_id=user.id, lesson_id=obj.lesson_id, objective_code=code)
                db.add(row)
            if value != old.get("objective_mastery", {}).get(code):
                row.mastery_label = value.get("level", "Unknown")
                row.correct_streak = value.get("correct_streak", 0)
                row.crown_level = value.get("crown_level", 0)
                row.last_practiced = as_date(value.get("last_practiced"))
                row.last_assessed_at = datetime.utcnow()
                progress = db.query(m.UserLessonProgress).filter_by(user_id=user.id, lesson_id=obj.lesson_id).one_or_none()
                if progress is None:
                    progress = m.UserLessonProgress(user_id=user.id, lesson_id=obj.lesson_id)
                    db.add(progress)
                progress.status = "completed" if row.mastery_label == "Known" else "in_progress" if row.last_practiced else "not_started"
                progress.percent_complete = 100 if row.mastery_label == "Known" else 0
                if progress.status == "completed":
                    progress.completed_at = datetime.utcnow()
        db.flush()
        for topic_id in {obj.topic_id for obj in objectives.values()}:
            codes = [obj.oid for obj in objectives.values() if obj.topic_id == topic_id]
            known = sum(state.get("objective_mastery", {}).get(code, {}).get("level") == "Known" for code in codes)
            mastery = db.query(m.UserTopicMastery).filter_by(user_id=user.id, topic_id=topic_id).one_or_none()
            if mastery is None:
                mastery = m.UserTopicMastery(user_id=user.id, topic_id=topic_id)
                db.add(mastery)
            mastery.mastery_score = 100.0 * known / len(codes)
            mastery.mastery_level = round(mastery.mastery_score)
            mastery.evidence_source = "objective_mastery"
            mastery.last_assessed_at = datetime.utcnow()
    for key, kind in (("lesson_queue", "plan"), ("review_items", "review")):
        if state.get(key, []) != old.get(key, []):
            _replace_queue(db, user.id, curriculum["drug_id"], kind, state.get(key, []), objectives)
    if state.get("current_lesson") != old.get("current_lesson"):
        _save_run(db, user.id, preferences, state.get("current_lesson"))
    if commit:
        db.commit()


def record_assessment(username, drug, kind, answers, results, db, imported=False, make_latest=True):
    user = get_or_create_user(db, username)
    content = drug_content(db, drug)
    objectives = {obj.oid: obj for obj in content["objectives"]}
    submission = m.AssessmentSubmission(user_id=user.id, drug_id=content["drug_id"], kind=kind, imported=imported)
    db.add(submission)
    db.flush()
    attempts = {}
    for position, result in enumerate(results):
        obj = objectives.get(result["oid"])
        if obj is None:
            raise ValueError(f"Unknown assessment objective {result['oid']!r}")
        question = obj.questions.get(kind if kind in ("initial", "checkpoint") else "lesson")
        if question is None:
            raise ValueError("Curriculum question missing for assessment")
        if question.quiz_id not in attempts:
            attempt = m.UserQuizAttempt(user_id=user.id, quiz_id=question.quiz_id, attempt_type=kind, submission_id=submission.submission_id)
            db.add(attempt)
            db.flush()
            attempts[question.quiz_id] = (attempt, [])
        attempt, marks = attempts[question.quiz_id]
        marks.append(bool(result["correct"]))
        db.add(m.UserQuizResponse(attempt_id=attempt.attempt_id, question_id=question.question_id,
                                 user_answer=answers.get(obj.oid), is_correct=result["correct"],
                                 feedback_text=result["message"], display_order=position,
                                 question_text=result.get("question", question.question_text),
                                 objective_code=result["oid"], category_label=result.get("category", obj.category)))
    for attempt, marks in attempts.values():
        attempt.score = round(100 * sum(marks) / len(marks))
        attempt.passed = attempt.score >= db.get(m.Quiz, attempt.quiz_id).passing_score
    if make_latest:
        _course(db, user.id, content["drug_id"]).last_submission_id = submission.submission_id
    return submission
