import os
import pytest
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings

client = TestClient(app)

@pytest.fixture
def temp_vault():
    with tempfile.TemporaryDirectory() as temp_dir:
        vault_path = Path(temp_dir)
        
        (vault_path / "test_note.md").write_text("""---
title: Test Note
tags:
  - test
---

# Test Note

This is a test note content.

## Section 1

Content of section 1.

## Section 2

Content of section 2.
""", encoding="utf-8")
        
        (vault_path / "folder").mkdir()
        (vault_path / "folder" / "nested_note.md").write_text("""# Nested Note

This is a nested note.
""", encoding="utf-8")
        
        yield vault_path

@pytest.fixture
def api_key():
    return "test-api-key"

@pytest.fixture(autouse=True)
def mock_settings(temp_vault, api_key, monkeypatch):
    # Resolve the temporary vault path to handle symlinks
    resolved_vault = temp_vault.resolve()
    # Mock all the modules that import settings
    monkeypatch.setattr('app.config.settings.vault_root', str(resolved_vault))
    monkeypatch.setattr('app.config.settings.api_key', api_key)
    monkeypatch.setattr('app.security.settings.api_key', api_key)
    monkeypatch.setattr('app.main.VAULT_ROOT', resolved_vault)
    yield

class TestHealthEndpoint:
    def test_health_endpoint(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert data["ok"] is True
        assert "vault_root" in data

class TestFilesEndpoint:
    def test_files_without_api_key(self):
        response = client.get("/files")
        assert response.status_code == 401
    
    def test_files_with_api_key(self, api_key):
        headers = {"X-API-Key": api_key}
        response = client.get("/files", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert len(data["files"]) >= 2
        file_names = [f.split('/')[-1] for f in data["files"]]  # Get just filenames
        assert "test_note.md" in file_names
        assert "nested_note.md" in file_names

class TestSearchEndpoint:
    def test_search_without_api_key(self):
        response = client.get("/search?q=test")
        assert response.status_code == 401
    
    def test_search_with_api_key(self, api_key):
        headers = {"X-API-Key": api_key}
        response = client.get("/search?q=test", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "q" in data
        assert "hits" in data
        assert data["q"] == "test"
    
    def test_search_empty_query(self, api_key):
        headers = {"X-API-Key": api_key}
        response = client.get("/search?q=", headers=headers)
        assert response.status_code == 422
    
    def test_search_with_limit(self, api_key):
        headers = {"X-API-Key": api_key}
        response = client.get("/search?q=note&limit=5", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["hits"]) <= 5

class TestNoteEndpoint:
    def test_note_without_api_key(self):
        response = client.get("/note?path=test_note.md")
        assert response.status_code == 401
    
    def test_note_with_api_key(self, api_key):
        headers = {"X-API-Key": api_key}
        response = client.get("/note?path=test_note.md", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "path" in data
        assert "text" in data
        assert "frontmatter" in data
        assert data["path"] == "test_note.md"
        assert "Test Note" in data["text"]
    
    def test_note_without_frontmatter(self, api_key):
        headers = {"X-API-Key": api_key}
        response = client.get("/note?path=test_note.md&with_frontmatter=false", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "frontmatter" not in data
    
    def test_note_with_section(self, api_key):
        headers = {"X-API-Key": api_key}
        response = client.get("/note?path=test_note.md&section=Section 1", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "Content of section 1" in data["text"]
    
    def test_note_not_found(self, api_key):
        headers = {"X-API-Key": api_key}
        response = client.get("/note?path=nonexistent.md", headers=headers)
        assert response.status_code == 404
    
    def test_note_section_not_found(self, api_key):
        headers = {"X-API-Key": api_key}
        response = client.get("/note?path=test_note.md&section=Nonexistent Section", headers=headers)
        assert response.status_code == 404

class TestResolveEndpoint:
    def test_resolve_without_api_key(self):
        response = client.get("/resolve?q=test")
        assert response.status_code == 401
    
    def test_resolve_with_api_key(self, api_key):
        headers = {"X-API-Key": api_key}
        response = client.get("/resolve?q=test", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "found" in data

class TestOpenEndpoint:
    def test_open_without_api_key(self):
        response = client.get("/open?q=test&vault=TestVault")
        assert response.status_code == 401
    
    def test_open_with_api_key(self, api_key):
        headers = {"X-API-Key": api_key}
        response = client.get("/open?q=test&vault=TestVault", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "found" in data
        if data["found"]:
            assert "obsidian_url" in data
            assert "obsidian://" in data["obsidian_url"]

class TestAssistantEndpoint:
    def test_assistant_without_api_key(self):
        response = client.get("/assistant?q=test&vault=TestVault")
        assert response.status_code == 401
    
    def test_assistant_with_api_key(self, api_key):
        headers = {"X-API-Key": api_key}
        response = client.get("/assistant?q=test&vault=TestVault", headers=headers)
        assert response.status_code == 200

class TestSecurity:
    def test_invalid_api_key(self):
        headers = {"X-API-Key": "invalid-key"}
        response = client.get("/files", headers=headers)
        assert response.status_code == 401
    
    def test_missing_api_key_header(self):
        response = client.get("/files")
        assert response.status_code == 401

if __name__ == "__main__":
    pytest.main([__file__, "-v"])