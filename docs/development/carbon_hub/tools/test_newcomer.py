"""Contract checks for the newcomer-first static Development Hub."""

from __future__ import annotations

import re
import unittest

import render_hub


class NewcomerProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = render_hub.load_json(render_hub.DATA_PATH)
        cls.events = render_hub.load_json(render_hub.EVENTS_PATH)["events"]
        cls.projection = render_hub.load_newcomer_projection(cls.data)
        cls.exam = render_hub.load_validator_exam_map()
        cls.output = render_hub.render_static(
            cls.data, cls.events, cls.projection, cls.exam
        )

    def test_projection_exactly_covers_canonical_records(self) -> None:
        self.assertEqual(
            set(self.projection["waves"]),
            {str(item["id"]) for item in self.data["waves"]},
        )
        self.assertEqual(
            set(self.projection["tickets"]),
            {str(item["id"]) for item in self.data["tickets"]},
        )

    def test_every_wave_leads_with_newcomer_questions_and_keeps_detail(self) -> None:
        for question in (
            "What are we building?",
            "Why does Carbon need it?",
            "What will be true when it is done?",
            "What is still not true yet?",
        ):
            expected = len(self.data["waves"]) + (
                0 if question == "What will be true when it is done?" else 1
            )
            self.assertEqual(
                self.output.count(f"<strong>{question}</strong>"),
                expected,
            )
        for wave in self.data["waves"]:
            self.assertIn(f'id="wave-{wave["id"]}"', self.output)
            self.assertIn(
                f'Canonical Wave:</strong> Wave {wave["id"]}: '
                f'{render_hub.esc(wave["title"])}',
                self.output,
            )

    def test_every_ticket_leads_with_newcomer_questions_and_keeps_detail(self) -> None:
        for question in (
            "What are we doing?",
            "Why does it matter?",
            "What changes when this is finished?",
            "What does this ticket not do?",
        ):
            self.assertEqual(
                self.output.count(f"<strong>{question}</strong>"),
                len(self.data["tickets"]) + 1,
            )
        for ticket in self.data["tickets"]:
            self.assertIn(f'id="ticket-{ticket["id"]}"', self.output)
            self.assertIn(
                f'Canonical ticket:</strong> {ticket["id"]}: '
                f'{render_hub.esc(ticket["title"])}',
                self.output,
            )
            self.assertIn(
                render_hub.esc(render_hub.ceiling(self.data, ticket, "ticket")),
                self.output,
            )

    def test_plain_status_labels_do_not_replace_canonical_status(self) -> None:
        for record in [*self.data["waves"], *self.data["tickets"]]:
            status = str(record["status"])
            self.assertIn(render_hub.NEWCOMER_STATUS_LABELS[status], self.output)
            self.assertIn(f"Exact canonical status:</strong> {status}", self.output)

    def test_current_stage_preserves_active_ticket_boundary(self) -> None:
        stage = self.projection["tickets"][str(self.data["current"]["ticket"])].get(
            "current_stage_plain"
        )
        self.assertTrue(stage)
        self.assertIn(
            f"<strong>Current stage:</strong> {render_hub.esc(stage)}", self.output
        )
        self.assertIn(
            "Score Pack binding remains pending", self.output
        )
        self.assertIn("no real scientific value is selected", self.output)

    def test_primary_page_is_static_and_has_no_remote_autoload(self) -> None:
        self.assertIsNone(re.search(r"<script\b", self.output, flags=re.IGNORECASE))
        self.assertIsNone(
            re.search(
                r"<(?:img|iframe|link|script|audio|video|source)\b[^>]+"
                r"(?:src|href)=[\"']https?://",
                self.output,
                flags=re.IGNORECASE,
            )
        )
        self.assertIn('<main id="main-content">', self.output)
        self.assertIn("Technical detail", self.output)

    def test_exam_map_is_one_ordered_process_with_all_explanation_depths(self) -> None:
        steps = [step for layer in self.exam["layers"] for step in layer["steps"]]
        self.assertEqual(
            [step["id"] for step in steps],
            [f"Q{index}" for index in range(1, 6)]
            + [f"R{index}" for index in range(1, 16)],
        )
        for step in steps:
            self.assertEqual(self.output.count(f'id="exam-{step["id"]}"'), 1)
            for heading in (
                "Input",
                "Validator / Carbon action",
                "Output",
                "Who controls it:",
                "Why it exists:",
                "Failure or indeterminate states:",
                "Investor explanation",
                "Engineer explanation",
                "CFD explanation",
                "Physics PhD explanation",
                "Maturity / authority note:",
                "Technical authority",
            ):
                self.assertIn(heading, self.output)

    def test_exam_map_preserves_current_maturity_and_science_boundary(self) -> None:
        for phrase in (
            "Target-state orientation only",
            "currently in Wave B authoring work",
            "planned for Wave C1",
            "Burgers v1 remains PRE-LIVE",
            "Science ends at R14",
            "separate network and economic policy",
        ):
            self.assertIn(phrase, self.output)


if __name__ == "__main__":
    unittest.main()
