import subprocess
import unittest
import pipeline_probe as probe


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.hashes = ("a" * 64, "b" * 64, "c" * 64)
        self.lines = [
            "negative=class_not_found",
            "handler=io.netty.handler.codec.spdy.SpdyFrameCodec",
            "channel=io.netty.channel.embedded.EmbeddedChannel",
            "pipeline=io.netty.channel.embedded.EmbeddedChannel$EmbeddedChannelPipeline",
            "registration=identity_matched_and_removed",
            "handler_code_source_sha256=" + self.hashes[0],
            "handler_class_resource_sha256=" + self.hashes[1],
            "pipeline_code_source_sha256=" + self.hashes[2],
            "cleanup=no_queued_messages",
        ]

    def parse(self, lines):
        result = subprocess.CompletedProcess(["private-command"], 0, "\n".join(lines) + "\n", "")
        return probe.parse_output(result, *self.hashes)

    def test_exact_protocol(self):
        result = self.parse(self.lines)
        self.assertEqual(result["registration"], "identity_matched_and_removed")
        self.assertEqual(result["pipeline_code_source_sha256"], self.hashes[2])

    def test_reject_mutations(self):
        for lines in ([], self.lines[:-1], list(reversed(self.lines)), self.lines + ["extra"],
                      self.lines[:3] + ["pipeline=other.Class"] + self.lines[4:],
                      self.lines[:7] + ["pipeline_code_source_sha256=wrong"] + self.lines[8:],
                      self.lines[:-1] + ["cleanup=messages_present"]):
            with self.subTest(lines=lines):
                with self.assertRaisesRegex(probe.common.ProbeError, "unexpected pipeline observation output"):
                    self.parse(lines)

    def test_bounded_diagnostics(self):
        with self.assertRaises(probe.common.ProbeError) as failure:
            self.parse(["::error::fixture", "x" * 5000 + "hidden-tail"])
        self.assertIn("(truncated)", str(failure.exception))
        self.assertNotIn("\n", str(failure.exception))
        self.assertNotIn("hidden-tail", str(failure.exception))
        self.assertNotIn("private-command", str(failure.exception))


if __name__ == "__main__":
    unittest.main()
