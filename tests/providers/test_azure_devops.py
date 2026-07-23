from providers.azure_devops import url_segment


def test_url_segment_encodes_spaces():
    assert url_segment("Team Project 1") == "Team%20Project%201"


def test_url_segment_leaves_safe_characters_untouched():
    assert url_segment("my-org") == "my-org"
