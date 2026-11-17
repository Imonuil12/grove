"""Seed the version-controlled starter curriculum and read content from SQL."""
from dataclasses import dataclass
from collections import defaultdict
import json
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models as m

KINDS = ("initial", "checkpoint", "lesson")
DEFAULT_UNITS = ("Facts", "Dosage", "Procedures", "Rationales")


@dataclass
class CurriculumObjective:
    oid: str
    category: str
    objective_text: str
    lesson_text: object
    question: str
    accepted_keyword_sets: list
    remediation_lesson: str
    lesson_id: int
    topic_id: int
    questions: dict
    keyword_sets_by_kind: dict


def seed_curriculum(db: Session):
    # Only the seed operation imports this file. Runtime requests read SQL.
    from learning_data import DRUG_DATABASE, TOPIC_LESSONS

    for key, source in DRUG_DATABASE.items():
        drug = db.query(m.Drug).filter_by(generic_name=key).one_or_none()
        if drug is None:
            drug = m.Drug(generic_name=key, display_name=source["display_name"])
            db.add(drug)
            db.flush()
        for position, obj in enumerate(source["objectives"], 1):
            category = db.query(m.Category).filter_by(name=obj.category, domain="drug").one_or_none()
            if category is None:
                order = DEFAULT_UNITS.index(obj.category) if obj.category in DEFAULT_UNITS else len(DEFAULT_UNITS)
                category = m.Category(name=obj.category, domain="drug", display_order=order)
                db.add(category)
                db.flush()
            topic_code = f"{key}:{obj.category.lower()}"
            topic = db.query(m.Topic).filter_by(topic_code=topic_code).one_or_none()
            if topic is None:
                topic = m.Topic(category_id=category.category_id, title=f"{drug.display_name}: {obj.category}", topic_code=topic_code, topic_type="drug")
                db.add(topic)
                db.flush()
            if db.get(m.TopicDrug, (topic.topic_id, drug.drug_id)) is None:
                db.add(m.TopicDrug(topic_id=topic.topic_id, drug_id=drug.drug_id, relationship_type="education"))
            lesson = seed_lesson(db, topic, obj, position)
            for kind in KINDS:
                quiz = db.query(m.Quiz).filter_by(topic_id=topic.topic_id, quiz_type=kind).one_or_none()
                if quiz is None:
                    quiz = m.Quiz(topic_id=topic.topic_id, title=f"{topic.title}: {kind}", quiz_type=kind)
                    db.add(quiz)
                    db.flush()
                seed_question(db, quiz, lesson, obj, position)
    seed_topic_outlines(db)
    for code, objectives in TOPIC_LESSONS.items():
        topic = db.query(m.Topic).filter_by(topic_code=code).one()
        for position, obj in enumerate(objectives, 1):
            quiz = db.query(m.Quiz).filter_by(topic_id=topic.topic_id, quiz_type="lesson", title=obj.category).one_or_none()
            if quiz is None:
                quiz = m.Quiz(topic_id=topic.topic_id, quiz_type="lesson", title=obj.category)
                db.add(quiz)
                db.flush()
            seed_question(db, quiz, seed_lesson(db, topic, obj, position), obj, position)
    db.flush()
    db.info.pop("curriculum", None)


def seed_lesson(db, topic, obj, position):
    lesson = db.query(m.Lesson).filter_by(topic_id=topic.topic_id, objective_code=obj.oid).one_or_none()
    if lesson is None:
        variants = obj.lesson_text if isinstance(obj.lesson_text, dict) else {}
        base = variants.get("beginner", next(iter(variants.values()), "")) if variants else obj.lesson_text
        lesson = m.Lesson(topic_id=topic.topic_id, title=obj.objective_text, objective_code=obj.oid,
                          objective_text=obj.objective_text, content_or_url=base,
                          category_label=obj.category, remediation_text=obj.remediation_lesson, display_order=position)
        db.add(lesson)
        db.flush()
        for level, content in variants.items():
            db.add(m.LessonContent(lesson_id=lesson.lesson_id, experience_level=level, content=content))
    if obj.hint and not db.query(m.LessonContent).filter_by(lesson_id=lesson.lesson_id, experience_level="hint").first():
        db.add(m.LessonContent(lesson_id=lesson.lesson_id, experience_level="hint", content=obj.hint))
    return lesson


def seed_question(db, quiz, lesson, obj, position):
    question = db.query(m.Question).filter_by(quiz_id=quiz.quiz_id, lesson_id=lesson.lesson_id, objective_code=obj.oid).one_or_none()
    if question is not None:
        return
    question = m.Question(quiz_id=quiz.quiz_id, lesson_id=lesson.lesson_id, objective_code=obj.oid,
                          question_text=obj.question, explanation_text=obj.remediation_lesson, display_order=position)
    db.add(question)
    db.flush()
    for order, keywords in enumerate(obj.accepted_keyword_sets, 1):
        if not keywords or any(not word or "," in word for word in keywords):
            raise ValueError("Seed keyword groups must contain nonempty comma-free keywords")
        db.add(m.AcceptedKeywordSet(question_id=question.question_id, set_order=order, keywords_csv=",".join(keywords)))


def seed_topic_outlines(db: Session):
    """Seed the same category and topic names used by the outline pages."""
    catalog_path = Path(__file__).resolve().parents[1] / "frontend" / "learning-catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    for order, source in enumerate(catalog.values()):
        domain = source["domain"]
        # Drug rows and their linked skill units are seeded from learning_data.py.
        if domain == "drug":
            continue
        category = db.query(m.Category).filter_by(name=source["name"], domain=domain).one_or_none()
        if category is None:
            category = m.Category(name=source["name"], domain=domain, display_order=order)
            db.add(category)
            db.flush()

        for entry in source["topics"]:
            topic = db.query(m.Topic).filter_by(topic_code=entry["topic_code"]).one_or_none()
            if topic is None:
                topic = m.Topic(category_id=category.category_id, topic_code=entry["topic_code"],
                                title=entry["title"], topic_type="general" if domain == "mixed" else domain)
                db.add(topic)
                db.flush()

            if "condition" in entry:
                condition = db.query(m.Condition).filter_by(name=entry["condition"]).one_or_none()
                if condition is None:
                    condition = m.Condition(name=entry["condition"])
                    db.add(condition)
                    db.flush()
                if db.get(m.TopicCondition, (topic.topic_id, condition.condition_id)) is None:
                    db.add(m.TopicCondition(topic_id=topic.topic_id, condition_id=condition.condition_id,
                                            relationship_type="primary_focus"))


def load_catalog(db: Session):
    if "curriculum" in db.info:
        return db.info["curriculum"]
    topics = {row.topic_id: row for row in db.query(m.Topic).all()}
    categories = {row.category_id: row for row in db.query(m.Category).all()}
    lessons = {row.lesson_id: row for row in db.query(m.Lesson).all()}
    variants = defaultdict(dict)
    for content in db.query(m.LessonContent).all():
        variants[content.lesson_id][content.experience_level] = content.content
    quizzes = {row.quiz_id: row for row in db.query(m.Quiz).all()}
    questions = defaultdict(dict)
    for question in db.query(m.Question).order_by(m.Question.question_id).all():
        if question.lesson_id:
            if quizzes[question.quiz_id].topic_id != lessons[question.lesson_id].topic_id:
                raise RuntimeError("Question and lesson must belong to the same topic")
            questions[question.lesson_id][quizzes[question.quiz_id].quiz_type] = question
    keywords = defaultdict(list)
    for group in db.query(m.AcceptedKeywordSet).order_by(m.AcceptedKeywordSet.set_order).all():
        keywords[group.question_id].append([word.strip() for word in group.keywords_csv.split(",") if word.strip()])
    links = defaultdict(list)
    for link in db.query(m.TopicDrug).all():
        links[link.drug_id].append(link.topic_id)
    catalog = {}
    for drug in db.query(m.Drug).order_by(m.Drug.drug_id).all():
        objectives = []
        for lesson in sorted(lessons.values(), key=lambda row: (categories[topics[row.topic_id].category_id].display_order, row.display_order, row.lesson_id)):
            if lesson.topic_id not in links[drug.drug_id] or not lesson.objective_code:
                continue
            question = questions[lesson.lesson_id].get("lesson")
            if question is None:
                continue
            category = categories[topics[lesson.topic_id].category_id]
            objectives.append(CurriculumObjective(
                lesson.objective_code, category.name, lesson.objective_text or lesson.title,
                variants[lesson.lesson_id] or lesson.content_or_url, question.question_text,
                keywords[question.question_id], lesson.remediation_text or question.explanation_text or "",
                lesson.lesson_id, lesson.topic_id, questions[lesson.lesson_id],
                {kind: keywords[q.question_id] for kind, q in questions[lesson.lesson_id].items()},
            ))
        codes = [obj.oid for obj in objectives]
        if len(codes) != len(set(codes)):
            raise RuntimeError(f"Duplicate objective codes within curriculum for {drug.generic_name}")
        catalog[drug.generic_name] = {"drug_id": drug.drug_id, "display_name": drug.display_name, "objectives": objectives,
                                      "unit_order": list(dict.fromkeys(obj.category for obj in objectives))}
    db.info["curriculum"] = catalog
    return catalog


def drug_content(db, key):
    content = load_catalog(db).get(key.lower())
    if content is None:
        raise HTTPException(status_code=404, detail="Drug not found. Run manage_db.py upgrade if curriculum has not been seeded.")
    return content
