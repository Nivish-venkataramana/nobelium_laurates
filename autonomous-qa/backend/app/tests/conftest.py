import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg2://qa_user:qa_password@localhost:5432/autonomous_qa_test"
)
os.environ.setdefault("GROQ_API_KEY", "test-key-not-real")
os.environ.setdefault("ALLOW_PRIVATE_NETWORK_TARGETS", "false")

import pytest  # noqa: E402


def make_element(id: str, tag: str, text: str, role: str | None = None, page_url: str = "http://x/"):
    from app.schemas.discovery import ElementModel, Locator, LocatorStrategy

    return ElementModel(
        id=id,
        tag=tag,
        role=role,
        text=text,
        page_url=page_url,
        locators=Locator(primary=LocatorStrategy(strategy="text", value=text)),
    )


@pytest.fixture
def element_factory():
    return make_element
