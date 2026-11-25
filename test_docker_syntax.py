from importlib.util import find_spec
import unittest

from comment_policy import prohibited_comments


@unittest.skipUnless(find_spec("tree_sitter_dockerfile"), "Dockerfile grammar unavailable")
class DockerfileTests(unittest.TestCase):
    def test_copy_heredoc_is_data_and_directives_are_preserved(self):
        source = ("# syntax=docker/dockerfile:1\nFROM scratch\n"
                  "COPY <<'MESSAGE' /message\n# this is written to a file\nMESSAGE\n"
                  "# outside the heredoc\n")
        for name in ("Dockerfile", "container/Dockerfile.build", "release.dockerfile"):
            with self.subTest(name=name):
                self.assertEqual(list(prohibited_comments(name, source)), [(6, 6)])

    def test_quoted_markers_and_standalone_comments(self):
        source = 'FROM busybox\nRUN echo "# output"\n# describe the build\n'
        self.assertEqual(list(prohibited_comments("Dockerfile", source)), [(3, 3)])
