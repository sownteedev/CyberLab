"""Bounded Results collection from isolated workspace fixtures."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from hashlib import md5, sha256
from dataclasses import asdict, replace
import json
from time import monotonic
from types import SimpleNamespace
import unittest

from tools.tests.unit.check_workstations import definition, validate_lab, LabValidationError
from cyberlab.assessment_checks import check_result, assessment_status, combined_status
from cyberlab.assessment import lab_digest
from cyberlab.assessment_goals import check_goal
from cyberlab.lab.models import AssessmentGoal
from cyberlab.submission import submission_archive, html_report
from cyberlab.submission_review import review_submissions


class ResultCollectionChecks(unittest.TestCase):
    def result(self, field_type, **options):
        document = definition()
        document['assessment'] = {'results': [{
            'id': 'sample', 'node': 'client', 'path': 'answer.txt', 'operator': 'collect',
            'field_type': field_type, **options}]}
        return validate_lab(document).assessment.results[0]

    def collect(self, field_type, contents=b'alpha beta\nsecond line\n', **options):
        result = self.result(field_type, **options)
        entries = {'client': {'answer.txt': SimpleNamespace(kind='file', data=contents)}}
        return check_result(result, entries, {})

    def test_scalar_types(self):
        cases = [
            ('token', b'alpha beta', dict(field_id=2, line_type='none'), 'beta'),
            ('parens', b'a (hello)', dict(field_id=1, line_type='none'), 'hello'),
            ('quotes', b'a "hello"', dict(field_id=1, line_type='none'), 'hello'),
            ('slash', b'alpha/beta/gamma', dict(field_id=2, line_type='none'), 'beta'),
            ('line_count', b'a\nb\n', {}, 2),
            ('size', b'\xff\x00', {}, 2),
            ('checksum', b'hello', {}, md5(b'hello').hexdigest()),
            ('string_count', b'one one', dict(field_id='one'), 2),
            ('command_count', b'time sudo ls -l\necho ls\nls | grep x; ls\n', dict(field_id='ls'), 3),
            ('search', b'frame.number==42', dict(field_id='frame.number=={:d}', line_type='none'), '42'),
            ('group', b'value=42', dict(field_id=1, line_type='regex', line_id=r'value=(\d+)'), '42'),
        ]
        for field_type, contents, options, expected in cases:
            with self.subTest(field_type=field_type):
                actual = self.collect(field_type, contents, **options)
                self.assertEqual(actual['status'], 'COLLECTED', actual)
                self.assertEqual(actual['value'], expected)

    def test_boolean_results(self):
        for field_type, pattern in [('contains', 'beta'), ('file_regex', r'alpha.*\nbeta')]:
            with self.subTest(field_type=field_type):
                self.assertEqual(self.collect(field_type, b'alpha\nbeta', field_id=pattern)['status'], 'PASS')
                self.assertEqual(self.collect(field_type, b'other', field_id=pattern)['status'], 'FAIL')

    def test_line_selectors(self):
        for line_type, line_id, expected in [
            ('line', 2, 'second'), ('starts_with', 'second', 'second'),
            ('contains', 'cond', 'second'), ('regex', '^second', 'second'),
            ('previous_starts_with', 'second', 'alpha')]:
            with self.subTest(line_type=line_type):
                self.assertEqual(self.collect('token', field_id=1, line_type=line_type, line_id=line_id)['value'], expected)

    def test_param_from_explicit_stdin_capture(self):
        result = self.result('param', field_id=2)
        entries = {'client': {'answer.txt': SimpleNamespace(kind='file', data=b'PROGRAM_ARGUMENTS (-p 22 host)\n')}}
        self.assertEqual(check_result(result, entries, {})['value'], '22')

    def test_timestamp_instances(self):
        text = b'2026-11-21T10:00:00Z ready\n2026-11-21T10:01:00Z FAIL\n2026-11-21T10:02:00Z FAIL\n2026-11-21T10:03:00Z done\n'
        report = self.collect('contains', text, field_id='FAIL', timestamp_type='log_ts')
        self.assertEqual(report['status'], 'COLLECTED')
        self.assertEqual(len(report['instances']), 2)
        self.assertNotIn('value', report)
        ranges = self.collect('contains', text, field_id='FAIL', timestamp_type='log_range')
        self.assertEqual(len(ranges['instances']), 3)
        self.assertEqual(ranges['instances'][0]['start'], '2026-11-21T10:00:00+00:00')
        self.assertEqual(ranges['instances'][-1]['end'], '2026-11-21T10:03:00+00:00')

    def test_time_delim_uses_only_declared_workspace_prefix(self):
        result = self.result('time_delim')
        entries = {'client': {name: SimpleNamespace(kind='file', data=b'') for name in [
            'answer.txt.stdout.20261121100000', 'answer.txt.stdout.20261121103000',
            'unrelated.stdout.20261121090000']}}
        report = check_result(result, entries, {})
        self.assertEqual(report['status'], 'COLLECTED', report)
        self.assertEqual(len(report['instances']), 2)
        self.assertIsNone(report['instances'][-1]['end'])

    def test_invalid_combinations_rejected(self):
        for field_type, options in [
            ('size', dict(field_id=1)), ('token', dict(field_id=0, line_type='none')),
            ('group', dict(field_id=1, line_type='line', line_id=1)),
            ('contains', dict(field_id='')), ('size', dict(timestamp_type='log_ts')),
            ('search', dict(field_id='{}', line_type='line')),
            ('time_delim', dict(line_type='line', line_id=1))]:
            with self.subTest(field_type=field_type, options=options), self.assertRaises(LabValidationError):
                self.result(field_type, **options)

    def test_missing_binary_and_resource_limits(self):
        self.assertEqual(self.collect('token', b'\xff', field_id=1, line_type='none')['status'], 'ERROR')
        self.assertEqual(self.collect('line_count', b'a' * 65537)['status'], 'ERROR')
        self.assertEqual(self.collect('token', b'a', field_id=2, line_type='none')['status'], 'FAIL')
        self.assertEqual(self.collect('file_regex', b'a', field_id='(')['status'], 'ERROR')
        self.assertEqual(self.collect('contains', b'no timestamp FAIL', field_id='FAIL', timestamp_type='log_ts')['status'], 'ERROR')

    def test_ungraded_values_do_not_become_pass(self):
        collected = self.collect('size')
        self.assertEqual(assessment_status([], [collected]), 'COLLECTED')
        self.assertEqual(assessment_status([], [collected, {'status': 'FAIL'}]), 'FAIL')
        self.assertEqual(assessment_status([], [collected, {'status': 'ERROR'}]), 'ERROR')
        self.assertEqual(combined_status(['COLLECTED']), 'ERROR')
        goal = AssessmentGoal(id='goal', results=(), goal_type='compare', result='sample', operator='integer_greater', expected=0)
        self.assertEqual(check_goal(goal, {'sample': collected})['status'], 'PASS')
        timeline = self.collect('contains', b'2026-11-21T10:00:00Z OK', field_id='OK', timestamp_type='log_ts')
        self.assertEqual(check_goal(goal, {'sample': timeline})['status'], 'ERROR')

    def test_legacy_extraction_and_digest_unchanged(self):
        document = definition()
        document['assessment'] = {'results': [dict(id='old', node='client', path='answer.txt', operator='extract', field_type='slash', field_id=1, line_type='line', line_id=1)]}
        lab = validate_lab(document)
        legacy = lab.assessment.results[0]
        entries = {'client': {'answer.txt': SimpleNamespace(kind='file', data=b'alpha/beta/gamma')}}
        self.assertEqual(check_result(legacy, entries, {})['value'], 'beta')
        self.assertEqual(check_result(legacy, entries, {})['status'], 'PASS')
        original = asdict(lab)
        original["metadata"].pop("difficulty", None)
        for node in original["nodes"]:
            if node.get("setup") is None:
                node.pop("setup", None)
            if not node.get("system_seed"):
                node.pop("system_seed", None)
        original['assessment']['results'][0].pop('timestamp_type')
        digest = sha256(json.dumps(original, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(lab_digest(lab), digest)
        for fields in [dict(field_type='size'), dict(line_type='none'), dict(timestamp_type='file')]:
            document['assessment']['results'][0] = {**asdict(legacy), **fields}
            if fields.get('timestamp_type') is None:
                document['assessment']['results'][0].pop('timestamp_type')
            document['assessment']['results'][0].pop('expected')
            with self.assertRaises(LabValidationError):
                validate_lab(document)

    def test_log_bounds_and_clock_errors(self):
        for contents in [b'2026-11-21T10:00:00 FAIL', b'Nov 21 10:00:00 FAIL',
                         b'2026-02-30T10:00:00Z FAIL',
                         b'2026-11-21T10:01:00Z FAIL\n2026-11-21T10:00:00Z FAIL',
                         b'2026-11-21T10:00:00Z FAIL\n' * 129]:
            with self.subTest(contents=contents[:80]):
                self.assertEqual(self.collect('contains', contents, field_id='FAIL', timestamp_type='log_ts')['status'], 'ERROR')
        report = self.collect('contains', b'2026-11-21T10:00:00+07:00 FAIL', field_id='FAIL', timestamp_type='log_ts')
        self.assertEqual(report['instances'][0]['timestamp'], '2026-11-21T03:00:00+00:00')
        self.assertEqual(self.collect('contains', b'2026-11-21T10:00:00Z OK', field_id='FAIL', timestamp_type='log_range')['status'], 'FAIL')

    def test_search_rejects_unsupported_formats_and_limits_regex(self):
        for template in ['plain', '{name}', '{:q}', '{!r}', '{', '{}' * 17]:
            with self.subTest(template=template), self.assertRaises(LabValidationError):
                self.result('search', field_id=template, line_type='none')
        result = self.result('file_regex', field_id='(a+)+$')
        entries = {'client': {'answer.txt': SimpleNamespace(kind='file', data=b'a' * 10000 + b'!')}}
        before = monotonic()
        self.assertEqual(check_result(result, entries, {}, regex_deadline=before + 0.1)['status'], 'ERROR')
        self.assertLess(monotonic() - before, 2)
        self.assertEqual(self.collect('search', b'frame.number==0042', field_id='frame.number=={:d}', line_type='none')['value'], '42')

    def test_links_and_outside_paths_are_not_read(self):
        result = self.result('checksum')
        for kind in ['symlink', 'directory', 'hardlink']:
            entries = {'client': {'answer.txt': SimpleNamespace(kind=kind, data=b'file')}}
            self.assertEqual(check_result(result, entries, {})['status'], 'ERROR')
        for path in ['/etc/shadow', '../secret', 'folder/../../secret']:
            with self.assertRaises(LabValidationError):
                self.result('size', path=path)

    def test_param_requires_capture_and_program_name(self):
        self.assertEqual(self.collect('param', b'ls -l', field_id=1)['status'], 'ERROR')
        result = replace(self.result('param', field_id=0), path='ssh.stdin.20261121100000')
        entries = {'client': {result.path: SimpleNamespace(kind='file', data=b'PROGRAM_ARGUMENTS (-p 22 host)')}}
        self.assertEqual(check_result(result, entries, {})['value'], 'ssh')

    def test_submission_round_trip_and_tampering(self):
        result = self.collect('contains', b'2026-11-21T10:00:00Z FAIL', field_id='FAIL', timestamp_type='log_ts')
        report = dict(id='a' * 32, session_id='b' * 32, lab_id='fixture', lab_name='Fixture',
                      lab_version='1.0.0', lab_digest='c' * 64, created_at='2026-11-21T10:00:00Z',
                      format='cyberlab-checkwork/v1', status='COLLECTED', submission_ready=True,
                      results=[result], goals=[], artifacts=[])
        reviewed = review_submissions([('fixture.zip', submission_archive(report))])
        self.assertTrue(reviewed['items'][0]['valid'], reviewed)
        self.assertIn('2026-11-21T10:00:00+00:00', html_report(report))
        for corrupted in [{**result, 'instances': result['instances'] * 129},
                          {**result, 'instances': [{'timestamp': 'invalid', 'value': True}]},
                          {**result, 'value': True}, {**result, 'instances': []}]:
            report['results'] = [corrupted]
            reviewed = review_submissions([('fixture.zip', submission_archive(report))])
            self.assertFalse(reviewed['items'][0]['valid'], reviewed)


if __name__ == '__main__':
    unittest.main()
