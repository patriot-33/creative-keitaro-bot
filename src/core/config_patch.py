# Patch to make Google services optional
# Replace these lines in src/core/config.py:

# FROM:
google_project_id: str
google_service_account_json: str  
google_drive_root_folder_id: str
google_sheets_manifest_id: str

# TO:
google_project_id: str = "temp-project"
google_service_account_json: str = '{"type":"service_account"}'
google_drive_root_folder_id: str = "temp-folder"
google_sheets_manifest_id: str = "temp-sheet"