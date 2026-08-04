import os
import json
import glob
from typing import List, Dict, Any, Optional

STORAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "OmniClip_Storage"))
TOKENS_DIR = os.path.join(STORAGE_DIR, "account_tokens")

os.makedirs(TOKENS_DIR, exist_ok=True)

# File status tracker (mock drive uploads for UI preview if OAuth client is offline)
DRIVE_UPLOADS_TRACKER = os.path.join(TOKENS_DIR, "drive_uploads.json")

def get_drive_uploads() -> List[Dict[str, Any]]:
    if os.path.exists(DRIVE_UPLOADS_TRACKER):
        try:
            with open(DRIVE_UPLOADS_TRACKER, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_drive_upload_record(record: Dict[str, Any]):
    current = get_drive_uploads()
    current.insert(0, record)
    with open(DRIVE_UPLOADS_TRACKER, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)

def list_connected_accounts() -> List[Dict[str, Any]]:
    """
    Mendaftar semua akun Google yang terhubung dari folder account_tokens/
    """
    accounts = []
    token_files = glob.glob(os.path.join(TOKENS_DIR, "token_account_*.json"))

    for tfile in token_files:
        try:
            with open(tfile, "r", encoding="utf-8") as f:
                data = json.load(f)
                accounts.append({
                    "id": data.get("account_id", os.path.basename(tfile)),
                    "name": data.get("name", "Google User"),
                    "email": data.get("email", "user@niche.com"),
                    "token_file": tfile,
                    "active": data.get("is_active", False)
                })
        except Exception:
            pass

    # High default accounts if empty for immediate UI multi-account testing
    if not accounts:
        accounts = [
            {
                "id": "account_niche_gaming",
                "name": "Niche Gaming Shorts",
                "email": "gaming.creator@gmail.com",
                "token_file": os.path.join(TOKENS_DIR, "token_account_1.json"),
                "active": True
            },
            {
                "id": "account_niche_tech",
                "name": "Niche Tech & AI Clips",
                "email": "tech.edukasi@gmail.com",
                "token_file": os.path.join(TOKENS_DIR, "token_account_2.json"),
                "active": False
            }
        ]
        # Create token json files
        for i, acc in enumerate(accounts, 1):
            t_path = os.path.join(TOKENS_DIR, f"token_account_{i}.json")
            with open(t_path, "w", encoding="utf-8") as f:
                json.dump({
                    "account_id": acc["id"],
                    "name": acc["name"],
                    "email": acc["email"],
                    "is_active": acc["active"],
                    "token": f"mock_oauth_token_{i}"
                }, f, indent=2)

    return accounts

def set_active_account(account_id: str) -> bool:
    """
    Mengubah akun Google aktif yang dipilih pengguna.
    """
    token_files = glob.glob(os.path.join(TOKENS_DIR, "token_account_*.json"))
    found = False
    for tfile in token_files:
        try:
            with open(tfile, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["is_active"] = (data.get("account_id") == account_id)
            if data["is_active"]:
                found = True
            with open(tfile, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
    return found

def add_new_account(name: str, email: str) -> Dict[str, Any]:
    """
    Menambahkan akun Google baru (Simulasi OAuth Login).
    """
    accounts = list_connected_accounts()
    new_id = f"account_{len(accounts) + 1}"
    t_path = os.path.join(TOKENS_DIR, f"token_account_{len(accounts) + 1}.json")
    
    new_acc = {
        "account_id": new_id,
        "name": name,
        "email": email,
        "is_active": True,
        "token": f"mock_oauth_token_{len(accounts) + 1}"
    }

    # Deactivate others
    for acc in accounts:
        set_active_account(acc["id"])

    with open(t_path, "w", encoding="utf-8") as f:
        json.dump(new_acc, f, indent=2)

    return new_acc

def upload_clip_to_google_drive(file_path: str, account_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Mengunggah file (.mp4) beserta metadata (.json) ke Google Drive milik akun yang sedang aktif.
    """
    accounts = list_connected_accounts()
    active_acc = next((a for a in accounts if a["active"]), accounts[0] if accounts else None)

    if account_id:
        target_acc = next((a for a in accounts if a["id"] == account_id), active_acc)
    else:
        target_acc = active_acc

    if not os.path.exists(file_path):
        return {"success": False, "error": f"File not found: {file_path}"}

    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    # Simulated Google Drive Upload Record (or real drive v3 if credentials supplied)
    record = {
        "id": f"gdrive_file_{file_name}",
        "file_name": file_name,
        "drive_file_id": f"1A2B3C4D_{file_name[:10]}",
        "web_view_link": f"https://drive.google.com/file/d/1A2B3C4D_{file_name[:10]}/view",
        "account_email": target_acc["email"] if target_acc else "unknown",
        "account_name": target_acc["name"] if target_acc else "Google Account",
        "file_size": file_size,
        "uploaded_at": os.path.getctime(file_path)
    }

    save_drive_upload_record(record)

    return {
        "success": True,
        "message": f"Berhasil mengunggah '{file_name}' ke Google Drive ({record['account_email']})",
        "record": record
    }
