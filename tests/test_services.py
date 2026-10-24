import tempfile
import unittest
from pathlib import Path

from piv_manager.db import initialize_database, transaction
from piv_manager.auth import create_user
from piv_manager.services import (
    approve_validation,
    backup_database,
    create_action,
    create_non_conformity,
    create_project,
    create_test,
    get_readiness,
    reschedule_test,
    set_checklist_item,
    update_action,
    update_non_conformity,
    update_test_status,
)


class CoreServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.sqlite3"
        initialize_database(self.database_path)
        self.project_id = create_project(self.database_path, name="EV platform")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_rejects_invalid_project_date(self):
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            create_project(self.database_path, name="Bad date", start_date="24/10/2026")

    def test_failed_test_requires_linked_nc_or_disposition(self):
        test_id = create_test(
            self.database_path,
            project_id=self.project_id,
            description="Thermal cycling",
            category="Environmental test",
        )
        with self.assertRaisesRegex(ValueError, "requires a linked non-conformity"):
            update_test_status(self.database_path, test_id, status="Failed")

        update_test_status(
            self.database_path,
            test_id,
            status="Failed",
            justified_disposition="Deviation accepted by design authority; approval ref DA-12.",
        )
        with transaction(self.database_path) as connection:
            test = connection.execute("SELECT * FROM tests WHERE id=?", (test_id,)).fetchone()
            history_count = connection.execute(
                "SELECT COUNT(*) FROM test_history WHERE test_id=?", (test_id,)
            ).fetchone()[0]
        self.assertEqual(test["status"], "Failed")
        self.assertIn("DA-12", test["justified_disposition"])
        self.assertEqual(history_count, 2)

    def test_action_requires_iso_due_date(self):
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            create_action(
                self.database_path,
                project_id=self.project_id,
                description="Review report",
                owner="Validation pilot",
                due_date="next Friday",
            )

    def test_non_conformity_cannot_close_with_open_action(self):
        nc_id = create_non_conformity(
            self.database_path,
            project_id=self.project_id,
            description="Connector seal damaged",
            detected_date="2026-10-24",
        )
        action_id = create_action(
            self.database_path,
            project_id=self.project_id,
            description="Replace seal and inspect stock",
            owner="Supplier quality",
            due_date="2026-11-01",
            nc_id=nc_id,
        )
        with self.assertRaisesRegex(ValueError, "Close all linked corrective actions"):
            update_non_conformity(
                self.database_path,
                nc_id,
                status="Closed",
                effectiveness_verification="No recurrence in follow-up lot",
                effectiveness_verified=True,
                closure_approved_by="Quality lead",
            )
        update_action(self.database_path, action_id, status="Closed", evidence="Inspection report R-1")
        with self.assertRaisesRegex(ValueError, "Final approval is blocked"):
            approve_validation(
                self.database_path,
                project_id=self.project_id,
                approver="Approver",
                approver_user_id=create_user(
                    self.database_path, username="approver", display_name="Approver",
                    password="Strong approval password!", role="approver", first_account=True,
                ),
            )

    def test_readiness_requires_recorded_tests_and_checklist_evidence(self):
        readiness = get_readiness(self.database_path, self.project_id)
        self.assertFalse(readiness["ready"])
        self.assertIn("Mandatory tests completed and passed", readiness["pending"])
        self.assertIn("Required reviews and approvals recorded", readiness["pending"])

    def test_backup_is_integrity_checked_and_never_overwritten(self):
        backup_path = self.database_path.parent / "backup.sqlite3"
        backup_database(self.database_path, backup_path)
        with self.assertRaises(FileExistsError):
            backup_database(self.database_path, backup_path)

    def test_rescheduling_preserves_original_planned_dates(self):
        test_id = create_test(
            self.database_path,
            project_id=self.project_id,
            description="Vibration endurance",
            category="Durability test",
            planned_start="2026-11-01",
            planned_end="2026-11-05",
        )
        reschedule_test(self.database_path, test_id, planned_start="2026-11-08",
                        planned_end="2026-11-12", reason="Lab capacity")
        reschedule_test(self.database_path, test_id, planned_start="2026-11-10",
                        planned_end="2026-11-14", reason="Sample delay")
        with transaction(self.database_path) as connection:
            record = connection.execute("SELECT * FROM tests WHERE id=?", (test_id,)).fetchone()
            changes = connection.execute(
                "SELECT COUNT(*) FROM schedule_history WHERE entity_type='test' AND entity_id=?",
                (test_id,),
            ).fetchone()[0]
        self.assertEqual(record["original_planned_start"], "2026-11-01")
        self.assertEqual(record["original_planned_end"], "2026-11-05")
        self.assertEqual(record["planned_start"], "2026-11-10")
        self.assertEqual(changes, 2)

    def test_retest_keeps_original_result_and_links_previous_test(self):
        original_id = create_test(
            self.database_path,
            project_id=self.project_id,
            description="Ingress test",
            category="Environmental test",
        )
        update_test_status(self.database_path, original_id, status="Failed", result="Water ingress",
                           justified_disposition="Investigate with repeat test")
        retest_id = create_test(
            self.database_path,
            project_id=self.project_id,
            description="Ingress test retest",
            category="Environmental test",
            original_test_id=original_id,
        )
        with transaction(self.database_path) as connection:
            original = connection.execute("SELECT * FROM tests WHERE id=?", (original_id,)).fetchone()
            retest = connection.execute("SELECT * FROM tests WHERE id=?", (retest_id,)).fetchone()
        self.assertEqual(original["status"], "Retest Required")
        self.assertEqual(original["result"], "Water ingress")
        self.assertEqual(retest["original_test_id"], original_id)

    def test_closure_and_readiness_checklist_require_evidence(self):
        action_id = create_action(
            self.database_path,
            project_id=self.project_id,
            description="Approve report",
            owner="Validation",
            due_date="2026-11-01",
        )
        with self.assertRaisesRegex(ValueError, "Closure evidence is required"):
            update_action(self.database_path, action_id, status="Closed")
        with self.assertRaisesRegex(ValueError, "evidence reference"):
            set_checklist_item(self.database_path, project_id=self.project_id,
                               criterion="Required reviews and approvals recorded",
                               category="Review", satisfied=True)

    def test_approver_can_approve_when_all_readiness_criteria_are_evidenced(self):
        create_user(self.database_path, username="admin", display_name="Admin",
                    password="Strong admin password!", role="admin", first_account=True)
        approver_id = create_user(self.database_path, username="approver", display_name="Quality Approver",
                                  password="Strong approval password!", role="approver")
        test_id = create_test(
            self.database_path,
            project_id=self.project_id,
            description="Bench validation",
            category="Bench test",
        )
        update_test_status(self.database_path, test_id, status="Passed", result="Pass",
                   report_reference="REPORT-100", sample_available=True)
        criteria = [
            "Mandatory test reports received and approved",
            "Required samples and documents available",
            "Supplier conformity confirmed",
            "Required reviews and approvals recorded",
        ]
        for criterion in criteria:
            set_checklist_item(self.database_path, project_id=self.project_id,
                               criterion=criterion, category="Evidence", satisfied=True,
                               evidence=f"Verified: {criterion}")
        readiness = get_readiness(self.database_path, self.project_id)
        self.assertTrue(readiness["ready"])
        approval_id = approve_validation(
            self.database_path, project_id=self.project_id, approver="Quality Approver",
            approver_user_id=approver_id, decision="Approved",
        )
        self.assertGreater(approval_id, 0)
        with transaction(self.database_path) as connection:
            audit = connection.execute(
                "SELECT username, operation FROM audit_events "
                "WHERE entity_type='final_validation' AND entity_id=?",
                (str(self.project_id),),
            ).fetchone()
        self.assertEqual(audit["username"], "approver")
        self.assertEqual(audit["operation"], "approved")

    def test_editor_cannot_approve_by_claiming_a_role(self):
        create_user(self.database_path, username="admin", display_name="Admin",
                    password="Strong admin password!", role="admin", first_account=True)
        editor_id = create_user(self.database_path, username="editor", display_name="Editor",
                                password="Strong editor password!", role="editor")
        with self.assertRaisesRegex(PermissionError, "Only an admin or authorized approver"):
            approve_validation(
                self.database_path, project_id=self.project_id, approver="Editor",
                approver_user_id=editor_id, decision="On Hold",
            )

    def test_checklist_cannot_override_missing_test_sample(self):
        test_id = create_test(
            self.database_path,
            project_id=self.project_id,
            description="Bench validation",
            category="Bench test",
        )
        update_test_status(self.database_path, test_id, status="Passed", result="Pass",
                           report_reference="REPORT-100")
        criteria = [
            "Mandatory test reports received and approved",
            "Required samples and documents available",
            "Supplier conformity confirmed",
            "Required reviews and approvals recorded",
        ]
        for criterion in criteria:
            set_checklist_item(self.database_path, project_id=self.project_id,
                               criterion=criterion, category="Evidence", satisfied=True,
                               evidence="Reviewed evidence")
        with self.assertRaisesRegex(ValueError, "Final approval is blocked"):
            approve_validation(
                self.database_path, project_id=self.project_id, approver="Approver",
                approver_user_id=create_user(
                    self.database_path, username="approver", display_name="Approver",
                    password="Strong approval password!", role="approver", first_account=True,
                ), decision="Approved",
            )


if __name__ == "__main__":
    unittest.main()