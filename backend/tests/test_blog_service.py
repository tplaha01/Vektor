from app.fund import blog_service as blog_module


def test_ensure_unique_slug_appends_suffix_when_slug_exists(monkeypatch):
    existing = {"market-update", "market-update-2"}

    def _fake_load_blog_post(key: str):
        return {"id": "blog-existing"} if key in existing else None

    monkeypatch.setattr(blog_module.storage_db, "load_blog_post", _fake_load_blog_post)

    slug = blog_module._ensure_unique_slug("Market Update")
    assert slug == "market-update-3"
