#!/usr/bin/env python3
"""Isolated shared-image storage accounting checks; never connects to Docker."""
import unittest
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))

from docker.errors import DockerException
from cyberlab.runtime import RuntimeFailure
from cyberlab.runtime.image_storage import ImageStorage


def image(identifier, layers, sizes):
    return SimpleNamespace(id=identifier, attrs={'Size': sum(sizes), 'RootFS': {'Layers': layers}},
                           history=Mock(return_value=[{'Size': size} for size in reversed(sizes)]))


class ImageStorageChecks(unittest.TestCase):
    def setUp(self):
        self.storage = ImageStorage()

    def test_shared_base_is_counted_once(self):
        first = image('first', ['ubuntu', 'app-a'], [1000, 100])
        second = image('second', ['ubuntu', 'app-b'], [1000, 200])
        self.assertEqual(self.storage.total([first, second]), 1300)
        self.assertEqual(self.storage.total([first, second, first]), 1300)

    def test_metadata_only_layers_and_identical_filesystems_do_not_add_storage(self):
        first = image('first', ['ubuntu', 'app'], [1000, 100])
        second = image('second', ['ubuntu', 'app'], [1000, 100])
        first.history.return_value.insert(0, {'Size': 0})
        self.assertEqual(self.storage.total([first, second]), 1100)

    def test_same_diff_on_different_parent_chains_is_not_deduplicated(self):
        first = image('first', ['base-a', 'app'], [1000, 100])
        second = image('second', ['base-b', 'app'], [2000, 100])
        self.assertEqual(self.storage.total([first, second]), 3200)

    def test_incomplete_history_falls_back_to_full_image_size(self):
        first = image('first', ['ubuntu', 'app-a'], [1000, 100])
        second = image('second', ['ubuntu', 'app-b'], [1000, 200])
        second.history.return_value = [{'Size': 200}]
        self.assertEqual(self.storage.total([first, second]), 2300)

    def test_unavailable_history_falls_back_without_undercounting(self):
        first = image('first', ['ubuntu'], [1000])
        first.history.side_effect = DockerException('unavailable')
        self.assertEqual(self.storage.total([first, first]), 1000)

    def test_mismatched_history_total_falls_back(self):
        first = image('first', ['ubuntu'], [1000])
        first.history.return_value = [{'Size': 10}]
        self.assertEqual(self.storage.total([first]), 1000)

    def test_missing_or_invalid_image_size_is_not_treated_as_zero(self):
        for size in (None, -1, '1000', True):
            with self.subTest(size=size), self.assertRaises(RuntimeFailure):
                self.storage.total([SimpleNamespace(id='invalid', attrs={'Size': size})])

    def test_immutable_history_is_cached_but_removed_images_are_not_retained(self):
        first = image('first', ['ubuntu'], [1000])
        self.assertEqual(self.storage.total([first]), 1000)
        first.history.side_effect = AssertionError('history should be reused')
        self.assertEqual(self.storage.total([first]), 1000)
        self.assertEqual(self.storage.total([]), 0)
        first.history.side_effect = None
        first.history.return_value = [{'Size': 1000}]
        self.assertEqual(self.storage.total([first]), 1000)


if __name__ == '__main__':
    unittest.main(verbosity=2)
