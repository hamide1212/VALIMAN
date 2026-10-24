from pathlib import Path

import streamlit as st

from piv_manager.config import DOCUMENTS_DIR
from piv_manager.services import save_document
from piv_manager.ui_common import choice_options, report_error, require_editor, rows, show_rows


def render(database_path, user, can_edit):
    st.title("Documents")
    st.caption("Reports · Specifications · Supplier evidence · Approval records")
    projects = rows(database_path, "SELECT id, name FROM projects WHERE archived=0 ORDER BY name")
    project_labels, project_map = choice_options(projects)
    components = rows(database_path, """SELECT c.id, c.name || ' · ' || c.part_number || ' rev ' ||
        c.part_revision || ' · ' || p.name AS name, c.project_id FROM components c
        JOIN projects p ON p.id=c.project_id ORDER BY p.name, c.part_number""")
    component_labels, component_map = choice_options(components)
    tests = rows(database_path, """SELECT t.id, t.test_code || ' · ' || t.description ||
        ' · ' || p.name AS name, t.project_id FROM tests t JOIN projects p ON p.id=t.project_id
        ORDER BY p.name, t.test_code""")
    test_labels, test_map = choice_options(tests)
    suppliers = rows(database_path, "SELECT id, name FROM suppliers WHERE archived=0 ORDER BY name")
    supplier_labels, supplier_map = choice_options(suppliers)
    ncs = rows(database_path, """SELECT nc.id, nc.nc_code || ' · ' || nc.description ||
        ' · ' || p.name AS name, nc.project_id FROM non_conformities nc
        JOIN projects p ON p.id=nc.project_id ORDER BY p.name, nc.detected_date DESC""")
    nc_labels, nc_map = choice_options(ncs)
    actions = rows(database_path, """SELECT a.id, a.action_code || ' · ' || a.description ||
        ' · ' || p.name AS name, a.project_id FROM actions a JOIN projects p ON p.id=a.project_id
        ORDER BY p.name, a.due_date""")
    action_labels, action_map = choice_options(actions)
    with st.expander("Attach document", expanded=False):
        if project_labels and require_editor(can_edit):
            linked_type = st.selectbox("Attach to record type", [
                "Project", "Component", "Test", "Supplier", "Non-conformity", "Action", "Unlinked",
            ])
            with st.form("document_upload"):
                link_labels, link_map = {
                    "Project": (project_labels, project_map),
                    "Component": (component_labels, component_map),
                    "Test": (test_labels, test_map),
                    "Supplier": (supplier_labels, supplier_map),
                    "Non-conformity": (nc_labels, nc_map),
                    "Action": (action_labels, action_map),
                    "Unlinked": (["Unlinked"], {}),
                }[linked_type]
                linked_label = st.selectbox("Record", link_labels or ["No records available"])
                category = st.selectbox("Document category", [
                    "Test report", "Specification", "Validation plan", "Supplier document",
                    "Photograph", "Approval evidence", "Other",
                ])
                uploaded = st.file_uploader("File", accept_multiple_files=False,
                                            type=["pdf", "doc", "docx", "xls", "xlsx", "csv", "txt",
                                                  "png", "jpg", "jpeg", "tif", "tiff"])
                submit = st.form_submit_button("Store document")
            if submit:
                if uploaded is None:
                    st.error("Select a file before submitting.")
                elif linked_type != "Unlinked" and linked_label not in link_map:
                    st.error("No matching record is available for this link type.")
                else:
                    try:
                        related_id = link_map.get(linked_label)
                        related_record = None
                        source_rows = {
                            "Component": components, "Test": tests,
                            "Non-conformity": ncs, "Action": actions,
                        }.get(linked_type, [])
                        if linked_type in {"Component", "Test", "Non-conformity", "Action"}:
                            related_record = next(row for row in source_rows if row["id"] == related_id)
                        save_document(
                            database_path, content=uploaded.getvalue(), original_name=uploaded.name,
                            category=category, documents_dir=DOCUMENTS_DIR,
                            mime_type=uploaded.type or "",
                            project_id=related_id if linked_type == "Project" else
                            related_record["project_id"] if related_record else None,
                            component_id=related_id if linked_type == "Component" else None,
                            test_id=related_id if linked_type == "Test" else None,
                            supplier_id=related_id if linked_type == "Supplier" else None,
                            nc_id=related_id if linked_type == "Non-conformity" else None,
                            action_id=related_id if linked_type == "Action" else None,
                            uploaded_by=user["username"],
                        )
                        st.success("Document stored without replacing existing files.")
                        st.rerun()
                    except Exception as error:
                        report_error(error)
        elif not project_labels:
            st.info("Create a project before attaching project documents.")
    documents = rows(database_path, """SELECT d.*, p.name AS project, s.name AS supplier
        FROM documents d LEFT JOIN projects p ON p.id=d.project_id
        LEFT JOIN suppliers s ON s.id=d.supplier_id ORDER BY d.created_at DESC""")
    show_rows(documents, "No documents stored.")
    if documents:
        options = [f"{doc['original_name']} · {doc['category']} · {doc['created_at']}" for doc in documents]
        selected = st.selectbox("Document", options)
        record = documents[options.index(selected)]
        file_path = (Path(DOCUMENTS_DIR).resolve() / record["relative_path"]).resolve()
        if Path(DOCUMENTS_DIR).resolve() not in file_path.parents:
            st.error("Document path failed the storage safety check.")
        elif file_path.is_file():
            st.download_button("Download document", file_path.read_bytes(),
                               record["original_name"], record["mime_type"] or "application/octet-stream")
        else:
            st.warning("The document metadata exists, but the stored file is missing.")