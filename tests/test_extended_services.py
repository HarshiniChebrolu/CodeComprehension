import pytest
from ai.factory import get_ai_provider
from ai.offline_provider import OfflineProvider
from ai.gemini_provider import GeminiProvider
from ai.openai_provider import OpenAIProvider
from analyzer.ast_analyzer import analyze_ast
from analyzer.optimizer import analyze_optimization
from analyzer.visualizer import generate_visualization_frames
from analyzer.execution_sandbox import execute_user_code, run_test_cases_safely


def test_ai_offline_provider():
    provider = OfflineProvider()
    assert "Offline" in provider.name
    res = provider.generate_explanation("def add(a, b): return a + b", "python")
    assert res.provider == provider.name
    assert len(res.key_functions) > 0
    assert len(res.step_by_step) > 0


def test_ai_provider_factory():
    p_off = get_ai_provider("offline")
    assert isinstance(p_off, OfflineProvider)
    p_gem = get_ai_provider("gemini")
    assert isinstance(p_gem, GeminiProvider)
    p_oai = get_ai_provider("openai")
    assert isinstance(p_oai, OpenAIProvider)
    p_unknown = get_ai_provider("unknown_llm")
    assert isinstance(p_unknown, OfflineProvider)


def test_ast_analyzer():
    code = """def calc(a, b):
    if a > 0:
        return a + b
    return b
"""
    res = analyze_ast(code, "python")
    assert "flow_nodes" in res
    assert "flow_chain" in res
    assert len(res["flow_chain"]) > 0


def test_optimizer_engine():
    code = """def find_pairs(nums, target):
    for i in range(len(nums)):
        for j in range(len(nums)):
            if nums[i] + nums[j] == target:
                return [i, j]
"""
    res = analyze_optimization(code, "python")
    assert res.get("has_optimization") is True
    assert "current_approach" in res
    assert "diff" in res


def test_visualizer_engine():
    code = """arr = [5, 2, 8, 1]
arr.sort()
"""
    frames = generate_visualization_frames(code, "python")
    assert "frames" in frames
    assert len(frames["frames"]) > 0


def test_api_execution_endpoint(client):
    code = "print('Hello from test execution')"
    resp = client.post("/api/v1/execute", json={"code": code, "language": "python"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "Hello from test execution" in data["stdout"]


def test_api_visualization_endpoint(client):
    code = "x = [3, 1, 2]\nx.sort()"
    resp = client.post("/api/v1/visualize", json={"code": code, "language": "python"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "visualization" in data


def test_api_history_delete_all(client):
    # Ensure there's a record to delete
    client.post("/api/v1/review", json={"code": "y = 20", "language": "python"})

    # Call bulk delete
    resp = client.delete("/api/v1/history")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "deleted_count" in data

    # Verify history is now empty
    r_hist = client.get("/api/v1/history")
    assert r_hist.status_code == 200
    assert len(r_hist.get_json()["history"]) == 0
