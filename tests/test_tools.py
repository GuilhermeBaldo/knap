"""Tests for vault tools."""

from pathlib import Path

import pytest

from knap.tools.base import ToolRegistry, ToolResult
from knap.tools.daily import GetDailyNoteTool
from knap.tools.edit import EditNoteTool
from knap.tools.frontmatter import GetFrontmatterTool, SetFrontmatterTool
from knap.tools.navigate import GetBacklinksTool, ListFolderTool
from knap.tools.glob import GlobNotesTool
from knap.tools.read import GrepNotesTool, ReadNoteTool, SearchByTagTool
from knap.tools.write import AppendToNoteTool, CreateNoteTool, DeleteNoteTool, UpdateNoteTool


class TestToolResult:
    """Tests for ToolResult dataclass."""

    def test_success_result(self):
        result = ToolResult(success=True, data={"key": "value"}, message="Success")
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.message == "Success"

    def test_failure_result(self):
        result = ToolResult(success=False, data=None, message="Error")
        assert result.success is False
        assert result.data is None


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_register_and_get(self, tmp_vault: Path):
        registry = ToolRegistry()
        tool = ReadNoteTool(tmp_vault)
        registry.register(tool)

        assert registry.get("read_note") is tool
        assert registry.get("nonexistent") is None

    def test_execute_unknown_tool(self, tmp_vault: Path):
        registry = ToolRegistry()
        result = registry.execute("unknown_tool")
        assert result.success is False
        assert "Unknown tool" in result.message

    def test_get_openai_tools(self, tmp_vault: Path):
        registry = ToolRegistry()
        registry.register(ReadNoteTool(tmp_vault))
        registry.register(GrepNotesTool(tmp_vault))

        tools = registry.get_openai_tools()
        assert len(tools) == 2
        assert tools[0]["type"] == "function"
        assert "function" in tools[0]


class TestReadNoteTool:
    """Tests for ReadNoteTool."""

    def test_read_existing_note(self, tmp_vault: Path):
        tool = ReadNoteTool(tmp_vault)
        result = tool.execute(path="Note1.md")

        assert result.success is True
        # Output now includes line numbers
        assert "Note 1" in result.data
        assert "content" in result.data.lower()

    def test_read_note_without_extension(self, tmp_vault: Path):
        tool = ReadNoteTool(tmp_vault)
        result = tool.execute(path="Note1")

        assert result.success is True
        assert "Note 1" in result.data

    def test_read_nonexistent_note(self, tmp_vault: Path):
        tool = ReadNoteTool(tmp_vault)
        result = tool.execute(path="Nonexistent.md")

        assert result.success is False
        assert "not found" in result.message.lower()

    def test_read_note_in_subfolder(self, tmp_vault: Path):
        tool = ReadNoteTool(tmp_vault)
        result = tool.execute(path="Inbox/Task.md")

        assert result.success is True
        assert "Buy groceries" in result.data

    def test_read_note_with_offset_and_limit(self, tmp_vault: Path):
        # Create a note with multiple lines
        (tmp_vault / "MultiLine.md").write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5")

        tool = ReadNoteTool(tmp_vault)
        result = tool.execute(path="MultiLine.md", offset=2, limit=2)

        assert result.success is True
        assert "Line 2" in result.data
        assert "Line 3" in result.data
        assert "Line 1" not in result.data
        assert "lines 2-3 of 5" in result.message


class TestGlobNotesTool:
    """Tests for GlobNotesTool."""

    def test_glob_all_notes(self, tmp_vault: Path):
        tool = GlobNotesTool(tmp_vault)
        result = tool.execute(pattern="**/*.md")

        assert result.success is True
        assert len(result.data) >= 3  # At least Note1, Note2, Task

    def test_glob_specific_folder(self, tmp_vault: Path):
        tool = GlobNotesTool(tmp_vault)
        result = tool.execute(pattern="Inbox/*.md")

        assert result.success is True
        assert any("Task.md" in p for p in result.data)

    def test_glob_by_name_pattern(self, tmp_vault: Path):
        tool = GlobNotesTool(tmp_vault)
        result = tool.execute(pattern="*Note*.md")

        assert result.success is True
        assert len(result.data) >= 2

    def test_glob_no_match(self, tmp_vault: Path):
        tool = GlobNotesTool(tmp_vault)
        result = tool.execute(pattern="*nonexistent*.md")

        assert result.success is True
        assert result.data == []


class TestGrepNotesTool:
    """Tests for GrepNotesTool."""

    def test_grep_files_with_matches(self, tmp_vault: Path):
        tool = GrepNotesTool(tmp_vault)
        result = tool.execute(pattern="content", output_mode="files_with_matches")

        assert result.success is True
        assert len(result.data) >= 1
        assert isinstance(result.data[0], str)  # Just paths

    def test_grep_content_mode(self, tmp_vault: Path):
        tool = GrepNotesTool(tmp_vault)
        result = tool.execute(pattern="content", output_mode="content")

        assert result.success is True
        assert len(result.data) >= 1
        assert "path" in result.data[0]
        assert "matches" in result.data[0]

    def test_grep_count_mode(self, tmp_vault: Path):
        tool = GrepNotesTool(tmp_vault)
        result = tool.execute(pattern="content", output_mode="count")

        assert result.success is True
        assert len(result.data) >= 1
        assert "path" in result.data[0]
        assert "count" in result.data[0]

    def test_grep_no_match(self, tmp_vault: Path):
        tool = GrepNotesTool(tmp_vault)
        result = tool.execute(pattern="xyznonexistent123")

        assert result.success is True
        assert result.data == []

    def test_grep_case_insensitive(self, tmp_vault: Path):
        tool = GrepNotesTool(tmp_vault)
        result = tool.execute(pattern="NOTE", case_insensitive=True)

        assert result.success is True
        assert len(result.data) >= 1

    def test_grep_max_results(self, tmp_vault: Path):
        tool = GrepNotesTool(tmp_vault)
        result = tool.execute(pattern=".", max_results=1)  # Match anything

        assert result.success is True
        assert len(result.data) <= 1

    def test_grep_with_glob_filter(self, tmp_vault: Path):
        tool = GrepNotesTool(tmp_vault)
        result = tool.execute(pattern=".", glob="Inbox/*")  # Only search Inbox

        assert result.success is True
        # Should only find notes in Inbox
        for path in result.data:
            assert "Inbox" in path

    def test_grep_regex_pattern(self, tmp_vault: Path):
        tool = GrepNotesTool(tmp_vault)
        result = tool.execute(pattern=r"#\w+")  # Match tags

        assert result.success is True
        assert len(result.data) >= 1


class TestSearchByTagTool:
    """Tests for SearchByTagTool."""

    def test_search_inline_tag(self, tmp_vault: Path):
        tool = SearchByTagTool(tmp_vault)
        result = tool.execute(tag="tag1")

        assert result.success is True
        assert len(result.data) >= 1
        assert "Note1.md" in result.data

    def test_search_tag_with_hash(self, tmp_vault: Path):
        tool = SearchByTagTool(tmp_vault)
        result = tool.execute(tag="#tag1")

        assert result.success is True
        assert len(result.data) >= 1

    def test_search_frontmatter_tag(self, tmp_vault: Path):
        tool = SearchByTagTool(tmp_vault)
        result = tool.execute(tag="project")

        assert result.success is True
        assert "Note2.md" in result.data

    def test_search_nonexistent_tag(self, tmp_vault: Path):
        tool = SearchByTagTool(tmp_vault)
        result = tool.execute(tag="nonexistenttag")

        assert result.success is True
        assert result.data == []


class TestCreateNoteTool:
    """Tests for CreateNoteTool."""

    def test_create_note(self, tmp_vault: Path):
        tool = CreateNoteTool(tmp_vault)
        result = tool.execute(path="NewNote.md", content="New content")

        assert result.success is True
        assert (tmp_vault / "NewNote.md").exists()
        assert (tmp_vault / "NewNote.md").read_text() == "New content"

    def test_create_note_in_subfolder(self, tmp_vault: Path):
        tool = CreateNoteTool(tmp_vault)
        result = tool.execute(path="NewFolder/SubNote.md", content="Sub content")

        assert result.success is True
        assert (tmp_vault / "NewFolder" / "SubNote.md").exists()

    def test_create_existing_note_fails(self, tmp_vault: Path):
        tool = CreateNoteTool(tmp_vault)
        result = tool.execute(path="Note1.md", content="New content")

        assert result.success is False
        assert "already exists" in result.message.lower()


class TestUpdateNoteTool:
    """Tests for UpdateNoteTool."""

    def test_update_note(self, tmp_vault: Path):
        tool = UpdateNoteTool(tmp_vault)
        result = tool.execute(path="Note1.md", content="Updated content")

        assert result.success is True
        assert (tmp_vault / "Note1.md").read_text() == "Updated content"

    def test_update_nonexistent_note_fails(self, tmp_vault: Path):
        tool = UpdateNoteTool(tmp_vault)
        result = tool.execute(path="Nonexistent.md", content="Content")

        assert result.success is False
        assert "not found" in result.message.lower()


class TestAppendToNoteTool:
    """Tests for AppendToNoteTool."""

    def test_append_to_note(self, tmp_vault: Path):
        tool = AppendToNoteTool(tmp_vault)
        original = (tmp_vault / "Note1.md").read_text()
        result = tool.execute(path="Note1.md", content="\nAppended text")

        assert result.success is True
        new_content = (tmp_vault / "Note1.md").read_text()
        assert original in new_content
        assert "Appended text" in new_content

    def test_append_to_nonexistent_note_fails(self, tmp_vault: Path):
        tool = AppendToNoteTool(tmp_vault)
        result = tool.execute(path="Nonexistent.md", content="Content")

        assert result.success is False


class TestDeleteNoteTool:
    """Tests for DeleteNoteTool."""

    def test_delete_note(self, tmp_vault: Path):
        tool = DeleteNoteTool(tmp_vault)
        assert (tmp_vault / "Note1.md").exists()

        result = tool.execute(path="Note1.md")

        assert result.success is True
        assert not (tmp_vault / "Note1.md").exists()

    def test_delete_nonexistent_note_fails(self, tmp_vault: Path):
        tool = DeleteNoteTool(tmp_vault)
        result = tool.execute(path="Nonexistent.md")

        assert result.success is False


class TestEditNoteTool:
    """Tests for EditNoteTool."""

    def test_edit_note(self, tmp_vault: Path):
        tool = EditNoteTool(tmp_vault)
        result = tool.execute(
            path="Inbox/Task.md", old_string="- [ ] Buy groceries", new_string="- [x] Buy groceries"
        )

        assert result.success is True
        content = (tmp_vault / "Inbox" / "Task.md").read_text()
        assert "- [x] Buy groceries" in content

    def test_edit_text_not_found(self, tmp_vault: Path):
        tool = EditNoteTool(tmp_vault)
        result = tool.execute(path="Note1.md", old_string="nonexistent text", new_string="new text")

        assert result.success is False
        assert "could not find" in result.message.lower()

    def test_edit_nonexistent_note(self, tmp_vault: Path):
        tool = EditNoteTool(tmp_vault)
        result = tool.execute(path="Nonexistent.md", old_string="old", new_string="new")

        assert result.success is False

    def test_edit_fails_on_multiple_matches(self, tmp_vault: Path):
        # Create a note with duplicate text
        (tmp_vault / "Dupe.md").write_text("hello world\nhello world")

        tool = EditNoteTool(tmp_vault)
        result = tool.execute(path="Dupe.md", old_string="hello", new_string="hi")

        assert result.success is False
        assert "2 occurrences" in result.message

    def test_edit_replace_all(self, tmp_vault: Path):
        # Create a note with duplicate text
        (tmp_vault / "Dupe2.md").write_text("hello world\nhello world")

        tool = EditNoteTool(tmp_vault)
        result = tool.execute(
            path="Dupe2.md", old_string="hello", new_string="hi", replace_all=True
        )

        assert result.success is True
        content = (tmp_vault / "Dupe2.md").read_text()
        assert content == "hi world\nhi world"
        assert result.data["count"] == 2

    def test_edit_same_string_fails(self, tmp_vault: Path):
        tool = EditNoteTool(tmp_vault)
        result = tool.execute(path="Note1.md", old_string="same", new_string="same")

        assert result.success is False
        assert "must be different" in result.message


class TestListFolderTool:
    """Tests for ListFolderTool."""

    def test_list_root(self, tmp_vault: Path):
        tool = ListFolderTool(tmp_vault)
        result = tool.execute(path="")

        assert result.success is True
        note_paths = [n["path"] for n in result.data["notes"]]
        assert "Note1.md" in note_paths
        assert "Inbox" in result.data["folders"]

    def test_list_subfolder(self, tmp_vault: Path):
        tool = ListFolderTool(tmp_vault)
        result = tool.execute(path="Inbox")

        assert result.success is True
        note_paths = [n["path"] for n in result.data["notes"]]
        assert "Inbox/Task.md" in note_paths

    def test_list_nonexistent_folder(self, tmp_vault: Path):
        tool = ListFolderTool(tmp_vault)
        result = tool.execute(path="NonexistentFolder")

        assert result.success is False


class TestGetBacklinksTool:
    """Tests for GetBacklinksTool."""

    def test_get_backlinks(self, tmp_vault: Path):
        # Create a note that links to Note1
        (tmp_vault / "Linking.md").write_text("This links to [[Note1]]")

        tool = GetBacklinksTool(tmp_vault)
        result = tool.execute(path="Note1.md")

        assert result.success is True
        assert "Linking.md" in result.data

    def test_no_backlinks(self, tmp_vault: Path):
        tool = GetBacklinksTool(tmp_vault)
        result = tool.execute(path="Note2.md")

        assert result.success is True
        assert result.data == []


class TestGetFrontmatterTool:
    """Tests for GetFrontmatterTool."""

    def test_get_frontmatter(self, tmp_vault: Path):
        tool = GetFrontmatterTool(tmp_vault)
        result = tool.execute(path="Note2.md")

        assert result.success is True
        assert result.data["title"] == "Custom Title"
        assert "project" in result.data["tags"]

    def test_no_frontmatter(self, tmp_vault: Path):
        tool = GetFrontmatterTool(tmp_vault)
        result = tool.execute(path="Note1.md")

        assert result.success is True
        assert result.data == {}


class TestSetFrontmatterTool:
    """Tests for SetFrontmatterTool."""

    def test_set_frontmatter(self, tmp_vault: Path):
        tool = SetFrontmatterTool(tmp_vault)
        result = tool.execute(path="Note1.md", frontmatter={"status": "active"})

        assert result.success is True
        content = (tmp_vault / "Note1.md").read_text()
        assert "status: active" in content

    def test_update_existing_frontmatter(self, tmp_vault: Path):
        tool = SetFrontmatterTool(tmp_vault)
        result = tool.execute(path="Note2.md", frontmatter={"title": "New Title"})

        assert result.success is True
        content = (tmp_vault / "Note2.md").read_text()
        assert "title: New Title" in content


class TestGetDailyNoteTool:
    """Tests for GetDailyNoteTool."""

    def test_get_daily_note_creates_if_missing(self, tmp_vault: Path):
        tool = GetDailyNoteTool(tmp_vault)
        result = tool.execute()

        assert result.success is True
        assert "path" in result.data
        # Check that a daily note was created
        daily_folder = tmp_vault / "Daily Notes"
        assert any(daily_folder.iterdir())

    def test_get_daily_note_returns_existing(self, tmp_vault: Path):
        # Create today's daily note
        from datetime import date

        daily_folder = tmp_vault / "Daily Notes"
        today = date.today().isoformat()
        daily_note = daily_folder / f"{today}.md"
        daily_note.write_text("Existing daily note")

        tool = GetDailyNoteTool(tmp_vault)
        result = tool.execute()

        assert result.success is True
        assert result.data["content"] == "Existing daily note"


class TestPathSecurity:
    """Tests for path traversal security."""

    def test_path_escape_blocked(self, tmp_vault: Path):
        tool = ReadNoteTool(tmp_vault)

        with pytest.raises(ValueError, match="escapes vault"):
            tool._validate_path("../../../etc/passwd")

    def test_absolute_path_normalized(self, tmp_vault: Path):
        tool = ReadNoteTool(tmp_vault)
        result = tool._validate_path("/Note1.md")

        assert result == tmp_vault / "Note1.md"
