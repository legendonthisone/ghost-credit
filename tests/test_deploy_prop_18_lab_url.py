"""The Lab, Property 16: lab_url always appends lab as a path segment."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from deploy_helpers import load_deploy_module

deploy = load_deploy_module()

hosts = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=30)
urls = st.builds(
    lambda host, region: f"https://{host}.lambda-url.{region}.on.aws",
    hosts,
    st.sampled_from(["us-east-1", "eu-west-1"]),
)


# Feature: the-lab, Property 16: lab_url always appends "lab" as a path segment
# **Validates: Requirements 9.5**
@settings(max_examples=100, deadline=None)
@given(urls, st.booleans())
def test_lab_url_adds_exactly_one_separator(base, trailing_slash) -> None:
    given_url = base + "/" if trailing_slash else base
    result = deploy.lab_url(given_url)
    assert result == base + "/lab"
    assert "//" not in result.split("://", 1)[1]
