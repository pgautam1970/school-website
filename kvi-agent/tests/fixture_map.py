"""Synthetic fixture registry (no side effects — safe to import from scripts)."""

GROUPS = [
    # name, category, class_level, method
    ("Class 5 Science", "Class Group", "Class 5", "export_upload"),
    ("Class 5 Parents Notice", "Parent-Teacher Group", "Class 5", "export_upload"),
    ("Class 8 Parents", "Parent-Teacher Group", "Class 8", "export_upload"),
    ("Class 9 Parents", "Parent-Teacher Group", "Class 9", "export_upload"),
    ("Class 1 Maths", "Class Group", "Class 1", "export_upload"),
    ("Class 10 Maths", "Subject Teachers", "Class 10", "export_upload"),
    ("Teachers Academic Coordination", "Academic Coordination", "", "export_upload"),
    ("Class 4 Parents", "Parent-Teacher Group", "Class 4", "export_upload"),  # deliberately never imported
    ("Malformed Test Group", "Other", "", "export_upload"),
]
FILE_FOR_GROUP = {
    "Class 5 Science": "Class_5_Science.txt",
    "Class 5 Parents Notice": "Class_5_Terminal_Notice_Copy.txt",
    "Class 8 Parents": "Class_8_Parents.txt",
    "Class 9 Parents": "Class_9_Parents.txt",
    "Class 1 Maths": "Class_1_Maths.txt",
    "Class 10 Maths": "Class_10_Maths.txt",
    "Teachers Academic Coordination": "Teachers_Academic_Coordination.txt",
    "Malformed Test Group": "malformed_and_injection.txt",
}

TEST_DAY = "2026-10-10"  # all synthetic messages are dated this NPT day
