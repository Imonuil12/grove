"""Quiz rounds and progress for topics that have no medication scope."""
from collections import Counter
from datetime import date, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, null
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

import models as m
from learning_store import get_or_create_user

ACTIVE = "topic_active"
COMPLETE = "topic_lesson"
MAX_HEARTS = 5
XP_PER_CORRECT = 10


class TopicLearning:
    def __init__(self, db, username, code, guest=None):
        self.db = db
        self.username = username
        self.topic = db.query(m.Topic).filter_by(topic_code=code).filter(m.Topic.topic_type != "drug").one_or_none()
        if self.topic is None:
            raise HTTPException(404, "Topic not found.")
        quizzes = (
            db.query(m.Quiz).filter_by(topic_id=self.topic.topic_id, quiz_type="lesson")
            .options(selectinload(m.Quiz.questions)).order_by(m.Quiz.quiz_id)
        )
        self.quizzes = {quiz.title: quiz for quiz in quizzes if quiz.questions}
        if not self.quizzes:
            raise HTTPException(404, "Lessons for this topic are not available yet.")
        self.guest = None if guest is None else guest.setdefault("topic_progress", {}).setdefault(
            code, {"correct": Counter(), "completed": set(), "run": None}
        )

    def attempts(self):
        return (
            self.db.query(m.UserQuizAttempt).join(m.User)
            .filter(m.User.email == self.username,
                    m.UserQuizAttempt.quiz_id.in_(q.quiz_id for q in self.quizzes.values()),
                    m.UserQuizAttempt.attempt_type.in_((ACTIVE, COMPLETE)))
        )

    def correct_counts(self):
        if self.guest is not None:
            return self.guest["correct"]
        attempt_ids = self.attempts().with_entities(m.UserQuizAttempt.attempt_id)
        rows = (
            self.db.query(m.UserQuizResponse.question_id, func.count())
            .filter(m.UserQuizResponse.attempt_id.in_(attempt_ids), m.UserQuizResponse.is_correct.is_(True))
            .group_by(m.UserQuizResponse.question_id)
        )
        return Counter(dict(rows.all()))

    def streak(self):
        if self.guest is not None:
            completed = self.guest["completed"]
        else:
            completed = {
                stamp.date() for stamp, in self.attempts().filter(m.UserQuizAttempt.attempt_type == COMPLETE)
                .with_entities(m.UserQuizAttempt.completed_at)
                if stamp is not None
            }
        day = date.today()
        if day not in completed:
            day -= timedelta(days=1)
        count = 0
        while day in completed:
            count += 1
            day -= timedelta(days=1)
        return count

    def path(self):
        correct = self.correct_counts()
        units = []
        for name, quiz in self.quizzes.items():
            crowns = [min(5, correct[q.question_id]) for q in quiz.questions]
            units.append({
                "category": name, "unlocked": not units or units[-1]["min_crown"] >= 1,
                "min_crown": min(crowns), "max_crown": max(crowns), "objective_count": len(crowns),
            })
        return {
            "topic": self.topic.title, "units": units,
            "xp_total": sum(correct.values()) * XP_PER_CORRECT,
            "streak_current": self.streak(), "hearts_remaining": MAX_HEARTS, "review_items": [],
        }

    def content(self):
        return {
            "topic": self.topic.title,
            "topic_chat": True,
            "categories": {
                name: [{"oid": q.objective_code} for q in self.questions(quiz)]
                for name, quiz in self.quizzes.items()
            },
        }

    @staticmethod
    def questions(quiz):
        return sorted(quiz.questions, key=lambda q: (q.display_order, q.question_id))

    @staticmethod
    def question_payload(quiz, question):
        return {"oid": question.objective_code, "question": question.question_text, "category": quiz.title}

    def start(self, unit):
        quiz = self.quizzes.get(unit)
        if quiz is None:
            raise HTTPException(404, "Skill not found.")
        if not next(row["unlocked"] for row in self.path()["units"] if row["category"] == unit):
            raise HTTPException(400, "Complete the previous skill first.")
        run = m.UserQuizAttempt(quiz_id=quiz.quiz_id, attempt_type=ACTIVE)
        if self.guest is None:
            try:
                with self.db.begin_nested():
                    user = get_or_create_user(self.db, self.username)
            except IntegrityError:
                user = self.db.query(m.User).filter_by(email=self.username).one()
            run.user_id = user.id
            run.completed_at = null()
            self.db.add(run)
            self.db.flush()
            run_id = str(run.attempt_id)
        else:
            run_id = uuid4().hex
            self.guest["run"] = (run_id, run)
        questions = self.questions(quiz)
        return {
            "attempt_id": run_id, "total_questions": len(questions), "hearts": MAX_HEARTS,
            "question": self.question_payload(quiz, questions[0]),
        }

    def get_run(self, run_id):
        if self.guest is not None:
            entry = self.guest["run"]
            run = entry[1] if entry and entry[0] == run_id else None
        elif run_id.isascii() and run_id.isdecimal() and len(run_id) <= 18:
            run = self.attempts().filter(m.UserQuizAttempt.attempt_id == int(run_id)).one_or_none()
        else:
            run = None
        if run is None:
            raise HTTPException(404, "Lesson attempt not found. Start the skill again.")
        quiz = next(q for q in self.quizzes.values() if q.quiz_id == run.quiz_id)
        return run, quiz, sorted(run.responses, key=lambda r: r.display_order)

    @staticmethod
    def hearts(responses):
        return max(0, MAX_HEARTS - sum(not row.is_correct for row in responses))

    def current_question(self, run, quiz, responses):
        questions = self.questions(quiz)
        index = len(responses)
        if run.attempt_type != ACTIVE or not self.hearts(responses) or index >= len(questions):
            return None
        return questions[index]

    @staticmethod
    def question_hint(question):
        contents = question.lesson.contents if question.lesson is not None else ()
        hint = next((entry.content for entry in contents if entry.experience_level == "hint"), None)
        return hint or "Read the question again and think about the main idea it asks for."

    def hint(self, run_id, oid):
        question = self.current_question(*self.get_run(run_id))
        if question is None or question.objective_code != oid:
            raise HTTPException(409, "This question is no longer active.")
        return {"response": self.question_hint(question)}

    def quiz_chat_context(self, run_id, oid=None):
        run, quiz, responses = self.get_run(run_id)
        current = self.current_question(run, quiz, responses)
        if oid is not None and (current is None or current.objective_code != oid):
            raise HTTPException(409, "This question is no longer active.")
        hint = self.question_hint(current) if current is not None else None
        # Include the course notes, but substitute the authored hint for the active answer's explanation.
        notes = [
            (skill.title, hint if q == current else q.lesson.content_or_url)
            for skill in self.quizzes.values() for q in self.questions(skill)
            if q.lesson is not None
        ]
        return {
            "topic": self.topic.title, "unit": quiz.title, "notes": notes,
            "quiz_question": current.question_text if current is not None else None, "hint": hint,
        }

    def answer(self, run_id, oid, answer, grade):
        run, quiz, responses = self.get_run(run_id)
        questions = self.questions(quiz)
        index = len(responses)
        replay = next((r for r in responses if r.objective_code == oid and r.user_answer == answer), None)
        if replay is not None:
            index = replay.display_order
            responses = responses[:index + 1]
            correct = replay.is_correct
        else:
            if (run.attempt_type != ACTIVE or not self.hearts(responses) or index >= len(questions)
                    or questions[index].objective_code != oid):
                raise HTTPException(409, "This question is no longer active.")
            question = questions[index]
            correct = grade(answer, [group.keywords_csv.split(",") for group in question.keyword_sets])
            response = m.UserQuizResponse(
                question_id=question.question_id, user_answer=answer, is_correct=correct,
                display_order=index, question_text=question.question_text,
                objective_code=oid, category_label=quiz.title,
            )
            run.responses.append(response)
            responses.append(response)
            if self.guest is not None and correct:
                self.guest["correct"][question.question_id] += 1
            if self.guest is None:
                try:
                    self.db.flush()
                except IntegrityError as error:
                    self.db.rollback()
                    raise HTTPException(409, "This answer was already submitted. Try again to recover the result.") from error

        question = questions[index]
        hearts = self.hearts(responses)
        done = not hearts or index + 1 == len(questions)
        return {
            "correct": correct,
            "feedback": "That's right." if correct else "Review the explanation and try again next round.",
            "detail": question.lesson.content_or_url if correct else question.explanation_text,
            "hearts": hearts, "xp_gained": XP_PER_CORRECT if correct else 0, "combo": 0,
            "session_over": done,
            "next_question": None if done else self.question_payload(quiz, questions[index + 1]),
        }

    def complete(self, run_id):
        run, quiz, responses = self.get_run(run_id)
        questions = self.questions(quiz)
        hearts = self.hearts(responses)
        if hearts and len(responses) < len(questions):
            raise HTTPException(409, "Finish the questions before completing this lesson.")
        correct = sum(r.is_correct for r in responses)
        if run.attempt_type == ACTIVE:
            run.attempt_type = COMPLETE
            run.completed_at = datetime.now()
            run.score = round(correct * 100 / len(questions))
            run.passed = run.score >= quiz.passing_score
            if self.guest is not None:
                self.guest["completed"].add(run.completed_at.date())
            else:
                self.db.flush()
        return {
            "questions_answered": len(responses), "questions_correct": correct, "total_questions": len(questions),
            "xp_earned": correct * XP_PER_CORRECT, "hearts_remaining": hearts, "streak_current": self.streak(),
            "ran_out_of_hearts": not hearts,
            "review_items": [
                {"question": questions[r.display_order].question_text, "remediation": questions[r.display_order].explanation_text}
                for r in responses if not r.is_correct
            ],
        }
