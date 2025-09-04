"""Tests for helpers.py."""
import os
import tempfile
import json
from unittest.mock import patch

import pytest

from ckanext.cataloginventory.helpers import get_export_map_json


class TestGetExportMapJson:
    """Test the get_export_map_json function."""

    def test_get_export_map_json_success(self):
        """Test reading a JSON file with the actual expected structure."""
        # Create a temporary JSON file with the expected structure
        test_data = {
            "dataset_fields_map": [
                {"field_name": "title", "label": "Title"},
                {"field_name": "name", "label": "Dataset ID"},
                {"field_name": "notes", "label": "Description"},
                {"field_name": "tag_string", "label": "Tags"},
                {"field_name": "license_id", "label": "License"},
                {"field_name": "owner_org", "label": "Organization"},
                {"field_name": "group", "label": "Groups"},
                {"field_name": "url", "label": "Source"},
                {"field_name": "version", "label": "Version"},
                {"field_name": "author", "label": "Author"},
                {"field_name": "author_email", "label": "Author Email"},
                {"field_name": "maintainer", "label": "Maintainer"},
                {"field_name": "maintainer_email", "label": "Maintainer Email"}
            ],
            "ordered_fields": [
                {"id": "Title"},
                {"id": "Description"},
                {"id": "Dataset ID"},
                {"id": "Tags"},
                {"id": "License"},
                {"id": "Organization"},
                {"id": "Groups"},
                {"id": "Source"},
                {"id": "Version"},
                {"id": "Author"},
                {"id": "Author Email"},
                {"id": "Maintainer"},
                {"id": "Maintainer Email"},
                {"id": "Created"},
                {"id": "Last Updated"},
                {"id": "Topic"},
                {"id": "Dataset URL"}
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(test_data, temp_file)
            temp_file_path = temp_file.name

        try:
            # Mock the os.path.join to return our temporary file
            with patch('ckanext.cataloginventory.helpers.os.path.join') as mock_join:
                mock_join.return_value = temp_file_path

                result = get_export_map_json('test.map.json')

                # Verify the structure
                assert 'dataset_fields_map' in result
                assert 'ordered_fields' in result
                assert len(result['dataset_fields_map']) == 13
                assert len(result['ordered_fields']) == 17

                # Verify some specific fields
                assert result['dataset_fields_map'][0]['field_name'] == 'title'
                assert result['dataset_fields_map'][0]['label'] == 'Title'
                assert result['ordered_fields'][0]['id'] == 'Title'
        finally:
            # Clean up the temporary file
            os.unlink(temp_file_path)

    def test_get_export_map_json_file_not_found_falls_back_to_default(self):
        """Test fallback to default file when specified file is not found."""
        default_data = {
            "dataset_fields_map": [{"field_name": "title", "label": "Title"}],
            "ordered_fields": [{"id": "Title"}]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            json.dump(default_data, temp_file)
            default_file_path = temp_file.name

        try:
            with patch('ckanext.cataloginventory.helpers.os.path.join') as mock_join:
                mock_join.side_effect = ['/path/to/nonexistent/file.json', default_file_path]

                with patch('ckanext.cataloginventory.helpers.os.path.isfile') as mock_isfile:
                    mock_isfile.side_effect = [False, True]
                    result = get_export_map_json('nonexistent.map.json')
                    assert result == default_data
        finally:
            os.unlink(default_file_path)

    def test_get_export_map_json_invalid_json(self):
        """Test handling of invalid JSON content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_file.write('{"invalid": json content}')
            temp_file_path = temp_file.name

        try:
            with patch('ckanext.cataloginventory.helpers.os.path.join') as mock_join:
                mock_join.return_value = temp_file_path
                
                with pytest.raises(Exception) as exc_info:
                    get_export_map_json('invalid.map.json')
                    # Check that it's a JSON decode error
                    assert 'JSONDecodeError' in str(type(exc_info.value))
        finally:
            os.unlink(temp_file_path)
