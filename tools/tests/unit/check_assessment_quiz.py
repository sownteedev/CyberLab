#!/usr/bin/env python3
"""Isolated Results/Goals and preparation Quiz regression checks."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from dataclasses import replace
import json
import tempfile
from types import SimpleNamespace
import unittest

from tools.tests.unit.check_workstations import definition, validate_lab, LabValidationError, Engine, MemoryRuntime, PracticeStore, RuntimePolicy, SessionState
from cyberlab.assessment_checks import check_result
from cyberlab.assessment_goals import check_goal
from cyberlab.lab.models import QuizQuestion
from cyberlab.quiz import evaluate_quiz, pre_start_answers, public_questions, QuizRequired, QuizRevisionChanged


class AssessmentQuizChecks(unittest.TestCase):
    def engine(self):
        temporary = tempfile.TemporaryDirectory(prefix="cyberlab-quiz-check-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        document = definition()
        document["nodes"][0].update(image="busybox:1.37.0")
        del document["nodes"][0]["user"]
        document["quizzes"] = [{"id": "intro", "pre_start": True, "items": [
            {"id": "first", "type": "choice", "question": "Choose", "options": ["Yes", "No"], "answer": 0},
            {"id": "second", "type": "choice", "question": "Choose again", "options": ["Yes", "No"], "answer": 1}
        ]}]
        package = root / "fixture"
        package.mkdir()
        (package / "lab.yaml").write_text(json.dumps(document))
        return Engine(root, RuntimePolicy(frozenset({"busybox:1.37.0"})), MemoryRuntime(),
                      PracticeStore(root / "practice.sqlite3"))

    def test_start_waits_for_answers_not_a_passing_score(self):
        engine = self.engine()
        quiz = engine.lab_quiz("fixture", 1234)
        with self.assertRaises(QuizRequired):
            engine.start("fixture", 1234)
        self.assertFalse(engine.runtime.active)
        engine.submit_lab_quiz("fixture", quiz["lab_digest"], {"first": 1}, 1234)
        with self.assertRaises(QuizRequired):
            engine.start("fixture", 1234)
        self.assertFalse(engine.runtime.active)
        report = engine.submit_lab_quiz("fixture", quiz["lab_digest"], {"first": 1, "second": 0}, 1234)
        self.assertFalse(report["passed"])
        session = engine.start("fixture", 1234)
        self.assertEqual(session.state, SessionState.RUNNING)
        self.assertEqual(engine.runtime.active, {session.id})

    def test_attempts_stay_owner_and_revision_scoped(self):
        engine = self.engine()
        digest = engine.lab_quiz("fixture", 1234)["lab_digest"]
        engine.submit_lab_quiz("fixture", digest, {"first": 1, "second": 0}, 1234)
        self.assertIsNone(engine.lab_quiz("fixture", 5678)["attempt"])
        with self.assertRaises(QuizRequired):
            engine.start("fixture", 5678)
        with self.assertRaises(QuizRevisionChanged):
            engine.submit_lab_quiz("fixture", "0" * 64, {"first": 1, "second": 0}, 1234)
        path = engine.catalog / "fixture" / "lab.yaml"
        document = json.loads(path.read_text())
        document["metadata"]["version"] = "1.0.1"
        path.write_text(json.dumps(document))
        self.assertIsNone(engine.lab_quiz("fixture", 1234)["attempt"])
        with self.assertRaises(QuizRequired):
            engine.start("fixture", 1234)
        self.assertFalse(engine.runtime.active)

    def test_saved_legacy_attempt_gets_correct_answer_review(self):
        engine = self.engine()
        digest = engine.lab_quiz("fixture", 1234)["lab_digest"]
        report = engine.submit_lab_quiz("fixture", digest, {"first": 1, "second": 0}, 1234)
        for question in report["questions"]:
            question.pop("correct_answer", None)
        engine.practice_store.lab_quizzes.save("fixture", 1234, digest, report)
        reviewed = engine.lab_quiz("fixture", 1234)["attempt"]
        self.assertEqual([item["correct_answer"] for item in reviewed["questions"]], [0, 1])

    def extraction_lab(self, **changes):
        document = definition()
        result = dict(id="fileview", node="client", path="answer.txt", operator="extract",
                      field_type="token", field_id=4, line_type="starts_with", line_id="My string is:")
        result.update(changes)
        document["assessment"] = dict(results=[result], goals=[dict(
            id="answer", type="compare", result="fileview", operator="string_equal", expected="hello")])
        return validate_lab(document)

    def test_extraction_feeds_goal_without_expected_on_result(self):
        lab = self.extraction_lab()
        entries = {"client": {"answer.txt": SimpleNamespace(kind="file", data=b"My string is: hello\n")}}
        result = check_result(lab.assessment.results[0], entries, {})
        self.assertEqual((result["status"], result["value"]), ("PASS", "hello"))
        self.assertEqual(check_goal(lab.assessment.goals[0], {"fileview": result})["status"], "PASS")
        wrong = {**result, "value": "other"}
        self.assertEqual(check_goal(lab.assessment.goals[0], {"fileview": wrong})["status"], "FAIL")

    def test_missing_field_and_oversize_text_do_not_pass(self):
        result = self.extraction_lab().assessment.results[0]
        for content, expected in [(b"unrelated", "FAIL"), (b"x" * 65537, "ERROR")]:
            entries = {"client": {"answer.txt": SimpleNamespace(kind="file", data=content)}}
            self.assertEqual(check_result(result, entries, {})["status"], expected)
        self.assertEqual(check_result(result, {"client": {}}, {})["status"], "FAIL")

    def test_extraction_requires_valid_workspace_and_selectors(self):
        for changes in [dict(path="/var/log/auth.log"), dict(path="../outside"),
                        dict(field_id=0), dict(line_id=3), dict(field_type="group"),
                        dict(expected="not-an-extraction")]:
            with self.subTest(changes=changes), self.assertRaises(LabValidationError):
                self.extraction_lab(**changes)

    def questions(self):
        return (QuizQuestion("first", "Choose", ("Yes", "No"), answer=0,
                             explanation="Because", pre_start=True),
                QuizQuestion("second", "Choose again", ("Yes", "No"), answer=1, pre_start=True))

    def test_wrong_answers_complete_preparation_and_reveal_correct_choices(self):
        items = self.questions()
        answers = {"first": 1, "second": 0}
        report = evaluate_quiz(items, answers)
        self.assertFalse(report["passed"])
        self.assertTrue(report["pre_start_completed"])
        self.assertEqual(pre_start_answers(items, report), answers)
        self.assertEqual([item["correct_answer"] for item in report["questions"]], [0, 1])
        self.assertEqual(report["questions"][0]["explanation"], "Because")

    def test_public_questions_and_unanswered_items_hide_correct_choices(self):
        items = self.questions()
        for item in public_questions(items):
            self.assertNotIn("answer", item)
            self.assertNotIn("correct_answer", item)
            self.assertNotIn("explanation", item)
        report = evaluate_quiz(items, {"first": 1})
        self.assertNotIn("correct_answer", report["questions"][1])
        with self.assertRaises(QuizRequired):
            pre_start_answers(items, report)

    def test_existing_conditional_and_optional_questions_remain_supported(self):
        first, second = self.questions()
        second = replace(second, prerequisite="first")
        report = evaluate_quiz((first, second), {"first": 0})
        self.assertTrue(report["pre_start_completed"])
        self.assertEqual(report["questions"][1]["status"], "SKIPPED")
        self.assertNotIn("correct_answer", report["questions"][1])
        self.assertIsNone(pre_start_answers((replace(first, pre_start=False),), None))


if __name__ == "__main__":
    unittest.main()
