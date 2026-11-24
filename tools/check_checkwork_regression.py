#!/usr/bin/env python3
"""Checkwork regressions using temporary stores and MemoryRuntime only."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from check_workstations import definition, validate_lab, LabValidationError
from cyberlab.assessment import evaluate
from cyberlab.assessment_checks import combined_status
from cyberlab.assessment_goals import check_goal
from cyberlab.lab.models import AssessmentGoal
from cyberlab.policy import RuntimePolicy
from cyberlab.runtime import RuntimeFailure
from cyberlab.service import Engine
from cyberlab.session import Session, SessionState
from cyberlab.session.persistence import PracticeStore
from cyberlab.session.reports import report_summary
from cyberlab.submission import html_report, public_report, submission_archive
from cyberlab.submission_review import review_submissions
from cyberlab.workspace import Entry
from cyberlabd.testing import MemoryRuntime


def result_definition():
    return dict(id="answer", node="client", path="answer.txt", operator="equals",
                expected="correct")


def lab_document(results=(), goals=(), artifacts=()):
    document = definition()
    document["nodes"][0].update(image="busybox:1.37.0")
    document["nodes"][0].pop("user")
    document["settings"] = {"checkwork": True}
    document["assessment"] = dict(results=list(results), goals=list(goals), artifacts=list(artifacts))
    return document


def session_for(document):
    return Session("a" * 32, validate_lab(document), 1234, SessionState.RUNNING, "now", "now")


def workspace(contents):
    return {"client": () if contents is None else (Entry("answer.txt", "file", contents),)}


class EvaluationChecks(unittest.TestCase):
    def test_result_without_goal_grades_correct_bad_and_missing_data(self):
        session = session_for(lab_document([result_definition()]))
        for contents, expected in [(b"correct", "PASS"), (b"wrong", "FAIL"), (None, "FAIL")]:
            with self.subTest(contents=contents):
                report = evaluate(session, workspace(contents))
                self.assertEqual(report["status"], expected)
                self.assertEqual(report["results"][0]["status"], expected)
                self.assertEqual(report["goals"], [])

    def test_collection_without_goal_is_not_a_passing_grade(self):
        result = dict(id="answer", node="client", path="answer.txt", operator="collect", field_type="size")
        session = session_for(lab_document([result]))
        report = evaluate(session, workspace(b"wrong"))
        self.assertEqual(report["status"], "COLLECTED")
        self.assertEqual(report["results"][0]["value"], 5)
        self.assertEqual(evaluate(session, workspace(None))["status"], "FAIL")
        self.assertEqual(evaluate(session, {}, {"client": "capture failed"})["status"], "ERROR")

    def test_collection_does_not_hide_graded_result(self):
        collected = dict(id="size", node="client", path="answer.txt", operator="collect", field_type="size")
        session = session_for(lab_document([collected, result_definition()]))
        for contents, expected in [(b"correct", "PASS"), (b"wrong", "FAIL"), (b"\xff", "ERROR")]:
            with self.subTest(expected=expected):
                report = evaluate(session, workspace(contents))
                self.assertEqual(report["results"][0]["status"], "COLLECTED")
                self.assertEqual(report["status"], expected)

    def test_no_criteria_and_artifact_readiness_are_separate(self):
        self.assertEqual(evaluate(session_for(lab_document()), {})["status"], "NO_CRITERIA")
        artifact = dict(id="evidence", node="client", path="answer.txt")
        for required in (True, False):
            session = session_for(lab_document(artifacts=[dict(artifact, required=required)]))
            for contents in (b"evidence", None):
                with self.subTest(required=required, contents=contents):
                    report = evaluate(session, workspace(contents))
                    self.assertEqual(report["status"], "NO_CRITERIA")
                    self.assertEqual(report["submission_ready"], contents is not None or not required)
                    self.assertEqual(report["artifacts"][0]["status"], "COLLECTED" if contents is not None
                                     else "MISSING" if required else "OPTIONAL_MISSING")
            report = evaluate(session, {}, {"client": "capture failed"})
            self.assertEqual(report["artifacts"][0]["status"], "ERROR")
            self.assertFalse(report["submission_ready"])

    def test_assess_false_does_not_evaluate_or_expose_criteria(self):
        artifact = dict(id="evidence", node="client", path="answer.txt")
        session = session_for(lab_document([result_definition()], [dict(id="goal", results=["answer"])], [artifact]))
        with patch("cyberlab.assessment.check_result", side_effect=AssertionError("must not grade")):
            report = evaluate(session, workspace(b"wrong"), assess=False)
        self.assertEqual((report["status"], report["results"], report["goals"]), ("NO_CRITERIA", [], []))
        self.assertTrue(report["submission_ready"])

    def test_comparison_uses_collected_value_not_capture_success(self):
        result = dict(id="answer", node="client", path="answer.txt", operator="collect",
                      field_type="token", field_id=2, line_type="none")
        goal = dict(id="goal", type="compare", result="answer", operator="string_equal", expected="correct")
        session = session_for(lab_document([result], [goal]))
        for contents, expected in [(b"value correct", "PASS"), (b"value wrong", "FAIL"),
                                   (b"value", "FAIL"), (None, "FAIL"), (b"\xff", "ERROR")]:
            with self.subTest(contents=contents):
                report = evaluate(session, workspace(contents))
                self.assertEqual(report["goals"][0]["status"], expected)
                self.assertEqual(report["status"], expected)

    def test_comparison_can_use_value_from_independently_failed_result(self):
        goal = dict(id="goal", type="compare", result="answer", operator="string_equal", expected="wrong")
        report = evaluate(session_for(lab_document([result_definition()], [goal])), workspace(b"wrong"))
        self.assertEqual(report["results"][0]["status"], "FAIL")
        self.assertEqual(report["status"], "PASS")

    def test_integer_comparison_rejects_bad_and_out_of_range_evidence(self):
        result = dict(id="answer", node="client", path="answer.txt", operator="collect",
                      field_type="token", field_id="ALL", line_type="none")
        goal = dict(id="goal", type="compare", result="answer", operator="integer_equal", expected="42")
        session = session_for(lab_document([result], [goal]))
        for contents, expected in [(b"42", "PASS"), (b"+42\n", "PASS"), (b"41", "FAIL"),
                                   (b"42.0", "FAIL"), (b"true", "FAIL"), (b"9223372036854775808", "FAIL")]:
            with self.subTest(contents=contents):
                self.assertEqual(evaluate(session, workspace(contents))["status"], expected)

    def test_capture_and_validation_errors_are_not_missing_evidence(self):
        session = session_for(lab_document([result_definition()], [dict(id="goal", results=["answer"])]))
        for entries, errors in [({}, {}), (workspace(b"correct"), {"client": "runtime unavailable"}),
                                ({"client": (Entry("../answer.txt", "file", b"correct"),)}, {}),
                                ({"client": (Entry("answer.txt", "file", b"correct"),) * 2}, {})]:
            with self.subTest(entries=entries, errors=errors):
                report = evaluate(session, entries, errors)
                self.assertEqual(report["status"], "ERROR")
                self.assertEqual(report["results"][0]["status"], "ERROR")
                self.assertEqual(report["goals"][0]["status"], "ERROR")
        report = evaluate(session, workspace(b"correct"), {"client": "runtime unavailable"})
        self.assertEqual(report["results"][0]["message"], "runtime unavailable")

    def test_unsafe_binary_and_oversize_evidence_is_error(self):
        session = session_for(lab_document([result_definition()]))
        for entry in [Entry("answer.txt", "symlink"), Entry("answer.txt", "directory"),
                      Entry("answer.txt", "file", b"\xff"), Entry("answer.txt", "file", b"x" * 65537)]:
            with self.subTest(kind=entry.kind, size=entry.size):
                self.assertEqual(evaluate(session, {"client": (entry,)})["status"], "ERROR")

    def test_regex_evaluation_failure_reaches_goal_and_report(self):
        result = dict(id="answer", node="client", path="answer.txt", operator="regex", expected="(")
        session = session_for(lab_document([result], [dict(id="goal", results=["answer"])]))
        self.assertEqual(evaluate(session, workspace(b"correct"))["status"], "ERROR")

    def test_group_and_count_resolve_earlier_goal_dependencies(self):
        for kind in ("group", "count"):
            dependent = dict(id="dependent", type=kind, results=["first"])
            if kind == "count":
                dependent.update(operator="count_greater", threshold=0)
            session = session_for(lab_document([result_definition()], [
                dict(id="first", results=["answer"]), dependent,
                dict(id="last", type="boolean", expression="dependent")]))
            for contents, expected in [(b"correct", "PASS"), (b"wrong", "FAIL"), (b"\xff", "ERROR")]:
                with self.subTest(kind=kind, expected=expected):
                    report = evaluate(session, workspace(contents))
                    self.assertEqual([goal["status"] for goal in report["goals"]], [expected] * 3)
                    self.assertEqual(report["status"], expected)
                    if kind == "count":
                        self.assertEqual(report["goals"][1]["value"], int(expected == "PASS"))

    def test_mixed_result_and_goal_dependencies(self):
        session = session_for(lab_document([result_definition()], [
            dict(id="first", results=["answer"]),
            dict(id="either", mode="any", results=["first", "answer"]),
            dict(id="both", type="count", operator="count_greater", threshold=1,
                 results=["first", "answer"])]))
        for contents, expected, count in [(b"correct", "PASS", 2), (b"wrong", "FAIL", 0), (b"\xff", "ERROR", 0)]:
            with self.subTest(expected=expected):
                report = evaluate(session, workspace(contents))
                self.assertEqual([goal["status"] for goal in report["goals"]], [expected] * 3)
                self.assertEqual(report["goals"][2]["value"], count)

    def test_boolean_dependencies_use_three_valued_logic(self):
        for expression, expected in [("first and true", "ERROR"), ("first or false", "ERROR"),
                                     ("not first", "ERROR"), ("first and false", "FAIL"),
                                     ("first or true", "PASS"), ("true and_not first", "ERROR"),
                                     ("false or_not first", "ERROR")]:
            with self.subTest(expression=expression):
                session = session_for(lab_document([result_definition()], [
                    dict(id="first", results=["answer"]),
                    dict(id="dependent", type="boolean", expression=expression)]))
                report = evaluate(session, {}, {"client": "capture failed"})
                self.assertEqual(report["goals"][1]["status"], expected)

    def test_group_and_count_preserve_decisive_status_with_unknowns(self):
        for statuses, mode, expected in [(["PASS", "ERROR"], "all", "ERROR"),
                                         (["FAIL", "ERROR"], "all", "FAIL"),
                                         (["FAIL", "ERROR"], "any", "ERROR"),
                                         (["PASS", "ERROR"], "any", "PASS"),
                                         (["COLLECTED"], "all", "ERROR")]:
            with self.subTest(statuses=statuses, mode=mode):
                self.assertEqual(combined_status(statuses, mode), expected)
        results = {"known": {"status": "PASS"}, "unknown": {"status": "ERROR"}}
        for threshold, expected in [(0, "PASS"), (1, "ERROR"), (2, "FAIL")]:
            with self.subTest(threshold=threshold):
                goal = AssessmentGoal("count", tuple(results), goal_type="count",
                                      operator="count_greater", threshold=threshold)
                self.assertEqual(check_goal(goal, results)["status"], expected)

    def test_unknown_and_cyclic_goal_dependencies_are_rejected(self):
        for goals in [[dict(id="goal", results=["unknown"])],
                      [dict(id="goal", type="boolean", expression="goal")],
                      [dict(id="first", type="boolean", expression="second"),
                       dict(id="second", type="boolean", expression="first")]]:
            with self.subTest(goals=goals), self.assertRaises(LabValidationError):
                session_for(lab_document([result_definition()], goals))

    def test_repeat_evaluation_is_fresh_and_does_not_mutate_inputs_or_old_reports(self):
        session = session_for(lab_document([result_definition()], [dict(id="goal", results=["answer"])]))
        entries = workspace(b"wrong")
        errors = {"client": "temporary capture failure"}
        original_entries, original_errors = deepcopy(entries), dict(errors)
        failed = evaluate(session, entries, errors)
        frozen = deepcopy(failed)
        self.assertEqual(entries, original_entries)
        self.assertEqual(errors, original_errors)
        errors.clear()
        self.assertEqual(evaluate(session, entries, errors)["status"], "FAIL")
        entries.update(workspace(b"correct"))
        correct = evaluate(session, entries, errors)
        self.assertEqual(correct["status"], "PASS")
        self.assertEqual(evaluate(session, entries, errors), correct)
        entries.update(workspace(None))
        self.assertEqual(evaluate(session, entries, errors)["status"], "FAIL")
        self.assertEqual(failed, frozen)
        self.assertEqual(correct["status"], "PASS")

    def test_all_report_statuses_survive_summary_export_and_review(self):
        collected = dict(id="answer", node="client", path="answer.txt", operator="collect", field_type="size")
        for results, contents, expected in [([result_definition()], b"correct", "PASS"),
                                           ([result_definition()], b"wrong", "FAIL"),
                                           ([result_definition()], b"\xff", "ERROR"),
                                           ([collected], b"ungraded", "COLLECTED"),
                                           ([], None, "NO_CRITERIA")]:
            with self.subTest(status=expected):
                report = evaluate(session_for(lab_document(results)), workspace(contents))
                report.update(id="f" * 32, created_at="2026-11-24T00:00:00Z")
                self.assertEqual(report["status"], expected)
                self.assertEqual(report_summary(json.dumps(report))["status"], expected)
                self.assertEqual(public_report(report)["status"], expected)
                self.assertIn(f"<p>{expected} -", html_report(report))
                reviewed = review_submissions([("fixture.zip", submission_archive(report))])
                self.assertTrue(reviewed["items"][0]["valid"], reviewed)
                self.assertEqual(reviewed["items"][0]["status"], expected)
                self.assertEqual(reviewed["summary"]["passed"], int(expected == "PASS"))


class CaptureServiceChecks(unittest.TestCase):
    def engine(self, document):
        temporary = tempfile.TemporaryDirectory(prefix="cyberlab-checkwork-regression-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        package = root / "catalog" / "fixture"
        package.mkdir(parents=True)
        (package / "lab.yaml").write_text(json.dumps(document), encoding="utf-8")
        engine = Engine(package.parent, RuntimePolicy(frozenset({"busybox:1.37.0"})),
                        MemoryRuntime(), PracticeStore(root / "practice.sqlite3"))
        session = engine.start("fixture", 1234)
        return engine, session

    def test_capture_reads_each_referenced_node_once_and_skips_unreferenced_nodes(self):
        document = lab_document([result_definition()], artifacts=[dict(id="evidence", node="client", path="answer.txt")])
        document["nodes"].append(dict(document["nodes"][0], id="unused"))
        engine, session = self.engine(document)
        engine.runtime.files[session.id]["client"]["answer.txt"] = b"correct"
        with patch.object(engine.runtime, "workspace", wraps=engine.runtime.workspace) as capture:
            report = engine.checkwork(session.id, 1234)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual([call.args[1].id for call in capture.call_args_list], ["client"])
        self.assertEqual(report["artifacts"][0]["status"], "COLLECTED")
        self.assertNotIn("content_b64", report["artifacts"][0]["entries"][0])

    def test_capture_failures_are_reported_and_retry_does_not_reuse_old_evidence(self):
        document = lab_document([result_definition()], [dict(id="goal", results=["answer"])])
        engine, session = self.engine(document)
        with patch.object(engine.runtime, "workspace", side_effect=RuntimeFailure("capture unavailable")):
            failed = engine.checkwork(session.id, 1234)
        self.assertEqual(failed["status"], "ERROR")
        self.assertEqual(failed["results"][0]["message"], "capture unavailable")
        self.assertNotIn(session.id, engine._checking)
        reports = [failed]
        for contents, expected in [(b"wrong", "FAIL"), (b"correct", "PASS"), (None, "FAIL")]:
            if contents is None:
                engine.runtime.files[session.id]["client"].pop("answer.txt")
            else:
                engine.runtime.files[session.id]["client"]["answer.txt"] = contents
            report = engine.checkwork(session.id, 1234)
            self.assertEqual(report["status"], expected)
            reports.append(report)
        self.assertEqual(len({report["id"] for report in reports}), 4)
        self.assertEqual(len(engine.check_reports(1234, session.id)), 4)
        self.assertEqual(engine.check_report(failed["id"], 1234), dict(failed, owner=1234))
        self.assertEqual(engine.check_reports(5678, session.id), [])

    def test_no_criteria_does_not_capture_or_claim_pass(self):
        engine, session = self.engine(lab_document())
        with patch.object(engine.runtime, "workspace", side_effect=AssertionError("unexpected capture")):
            self.assertEqual(engine.checkwork(session.id, 1234)["status"], "NO_CRITERIA")

    def test_goal_dependencies_flow_through_existing_capture_and_storage(self):
        document = lab_document([result_definition()], [
            dict(id="first", results=["answer"]),
            dict(id="group", results=["first"]),
            dict(id="count", type="count", operator="count_greater", threshold=0, results=["group"]),
            dict(id="last", type="boolean", expression="count")])
        engine, session = self.engine(document)
        for contents, expected in [(b"correct", "PASS"), (b"wrong", "FAIL"), (b"\xff", "ERROR")]:
            with self.subTest(expected=expected):
                engine.runtime.files[session.id]["client"]["answer.txt"] = contents
                report = engine.checkwork(session.id, 1234)
                self.assertEqual(report["status"], expected)
                self.assertEqual([goal["status"] for goal in report["goals"]], [expected] * 4)
                self.assertEqual(engine.check_report(report["id"], 1234), dict(report, owner=1234))

    def test_collection_only_status_survives_storage(self):
        result = dict(id="answer", node="client", path="answer.txt", operator="collect", field_type="size")
        engine, session = self.engine(lab_document([result]))
        engine.runtime.files[session.id]["client"]["answer.txt"] = b"wrong"
        report = engine.checkwork(session.id, 1234)
        self.assertEqual(report["status"], "COLLECTED")
        self.assertEqual(engine.check_report(report["id"], 1234), dict(report, owner=1234))

    def test_deadline_failure_does_not_save_report_and_releases_capture_guard(self):
        engine, session = self.engine(lab_document([result_definition()]))
        with patch("cyberlab.service.monotonic", side_effect=[0, 121, 121]):
            with self.assertRaisesRegex(RuntimeFailure, "deadline"):
                engine.checkwork(session.id, 1234)
        self.assertEqual(engine.check_reports(1234, session.id), [])
        self.assertNotIn(session.id, engine._checking)
        self.assertEqual(engine.checkwork(session.id, 1234)["status"], "FAIL")

    def test_unexpected_capture_exception_propagates_without_a_report(self):
        engine, session = self.engine(lab_document([result_definition()]))
        with patch.object(engine.runtime, "workspace", side_effect=RuntimeError("unexpected failure")):
            with self.assertRaisesRegex(RuntimeError, "unexpected failure"):
                engine.checkwork(session.id, 1234)
        self.assertEqual(engine.check_reports(1234, session.id), [])
        self.assertNotIn(session.id, engine._checking)

    def test_disabled_checkwork_rejects_capture(self):
        document = lab_document([result_definition()])
        document["settings"]["checkwork"] = False
        engine, session = self.engine(document)
        with patch.object(engine.runtime, "workspace", side_effect=AssertionError("unexpected capture")):
            with self.assertRaisesRegex(RuntimeFailure, "not enabled"):
                engine.checkwork(session.id, 1234)
        self.assertEqual(engine.check_reports(1234, session.id), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
