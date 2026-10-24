import tempfile
import unittest
from pathlib import Path

from piv_manager.auth import authenticate, create_user, get_active_user, set_user_active
from piv_manager.db import initialize_database, transaction
from piv_manager.reports import REPORTS, build_report, export_csv, export_excel
from piv_manager.services import (
    create_action,
    create_project,
    create_supplier,
    create_test,
    get_dashboard_data,
    save_document,
)


class AppServiceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.database_path = self.root / "test.sqlite3"
        initialize_database(self.database_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_authentication_uses_roles_and_rejects_bad_password(self):
        create_user(self.database_path, username="admin", display_name="Quality Admin",
                password="Strong local passphrase!", role="admin", first_account=True)
        user_id = create_user(self.database_path, username="editor", display_name="Project Editor",
                      password="Another strong passphrase!", role="editor")
        self.assertIsNone(authenticate(self.database_path, "admin", "incorrect password"))
        authenticated = authenticate(self.database_path, "ADMIN", "Strong local passphrase!")
        self.assertEqual(authenticated["role"], "admin")
        self.assertEqual(authenticated["display_name"], "Quality Admin")
        set_user_active(self.database_path, user_id, False, actor="admin")
        self.assertIsNone(get_active_user(self.database_path, user_id))

    def test_report_generation_and_exports_are_data_backed(self):
        project_id = create_project(self.database_path, name="PIV report test")
        create_test(self.database_path, project_id=project_id, description="Bench run",
                    category="Bench test", status="Planned")
        frame = build_report(self.database_path, "Test status and results", project_id)
        self.assertEqual(len(frame), 1)
        self.assertEqual(frame.iloc[0]["description"], "Bench run")
        self.assertTrue(export_csv(frame).startswith(b"\xef\xbb\xbf"))
        self.assertTrue(export_excel(frame).startswith(b"PK"))

    def test_each_report_builder_returns_a_dataframe(self):
        project_id = create_project(self.database_path, name="All reports project")
        supplier_id = create_supplier(self.database_path, name="Report supplier")
        create_action(self.database_path, project_id=project_id, supplier_id=supplier_id,
                      description="Overdue follow-up", owner="SQE", due_date="2020-01-01")
        for report_name in REPORTS:
            with self.subTest(report=report_name):
                frame = build_report(self.database_path, report_name, project_id)
                self.assertIsNotNone(frame)
                self.assertTrue(hasattr(frame, "columns"))

    def test_dashboard_filters_project_and_supplier_actions(self):
        first_project = create_project(self.database_path, name="Project A")
        second_project = create_project(self.database_path, name="Project B")
        supplier_id = create_supplier(self.database_path, name="Supplier A")
        create_action(self.database_path, project_id=first_project, supplier_id=supplier_id,
                      description="Late supplier action", owner="SQE", due_date="2020-01-01")
        create_action(self.database_path, project_id=second_project, supplier_id=supplier_id,
                      description="Other late action", owner="SQE", due_date="2020-01-01")
        data = get_dashboard_data(self.database_path, project_id=first_project,
                                  supplier_id=supplier_id)
        self.assertEqual(data["overdue_actions"], 1)

    def test_document_storage_rejects_unknown_type_and_uses_unique_names(self):
        with self.assertRaisesRegex(ValueError, "type is not allowed"):
            save_document(self.database_path, content=b"bad", original_name="report.exe",
                          category="Other", documents_dir=self.root / "docs")
        project_id = create_project(self.database_path, name="Documents")
        first = save_document(self.database_path, content=b"%PDF-1", original_name="report.pdf",
                              category="Test report", documents_dir=self.root / "docs",
                              project_id=project_id)
        second = save_document(self.database_path, content=b"%PDF-2", original_name="report.pdf",
                               category="Test report", documents_dir=self.root / "docs",
                               project_id=project_id)
        with transaction(self.database_path) as connection:
            paths = connection.execute("SELECT stored_name FROM documents ORDER BY id").fetchall()
        self.assertNotEqual(paths[0]["stored_name"], paths[1]["stored_name"])
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()