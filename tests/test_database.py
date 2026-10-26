import pytest
import sqlite3
import database


def test_database_context_manager():
    with database.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        res = cursor.fetchone()[0]
        assert res == 1


def test_save_and_retrieve_review():
    rev_id = database.save_review(
        language="python",
        code="def foo(): pass",
        score=95,
        issue_count=0,
        time_complexity="O(1)",
        space_complexity="O(1)",
        review_data={"test_key": "test_value"},
        title="Test Record",
        ai_provider="offline"
    )
    assert rev_id is not None
    assert rev_id > 0

    record = database.get_review_by_id(rev_id)
    assert record is not None
    assert record["language"] == "python"
    assert record["score"] == 95
    assert record["review_data"]["test_key"] == "test_value"
    # Verify UTC ISO 8601 timestamp
    assert "T" in record["timestamp"]


def test_delete_existing_review():
    rev_id = database.save_review(
        language="python",
        code="x = 10",
        score=100,
        issue_count=0,
        time_complexity="O(1)",
        space_complexity="O(1)",
        review_data={}
    )
    # Deleting existing record should return True
    assert database.delete_review(rev_id) is True
    # Record should now be gone
    assert database.get_review_by_id(rev_id) is None


def test_delete_nonexistent_review_returns_false():
    # Deleting nonexistent ID should return False (mapped to 404 in API)
    assert database.delete_review(99999999) is False


def test_pagination_and_total_count():
    reviews, total_count = database.get_recent_reviews(limit=5, offset=0)
    assert isinstance(reviews, list)
    assert isinstance(total_count, int)
    assert total_count >= len(reviews)
