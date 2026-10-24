import sqlite3
import tempfile
import unittest
from pathlib import Path

from piv_manager.db import SCHEMA_VERSION, initialize_database


class DatabaseInitializationTests(unittest.TestCase):
    def test_initializes_normalized_schema_and_foreign_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.sqlite3"
            initialize_database(database_path)
            initialize_database(database_path)

            connection = sqlite3.connect(database_path)
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            connection.execute("PRAGMA foreign_keys = ON")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO components(project_id, name, part_number, part_revision) "
                    "VALUES (999, 'Brake ECU', 'PN-1', 'A')"
                )
            connection.close()

            self.assertEqual(version, SCHEMA_VERSION)
            self.assertIn("projects", tables)
            self.assertIn("tests", tables)
            self.assertIn("non_conformities", tables)
            self.assertIn("audit_events", tables)


if __name__ == "__main__":
    unittest.main()
