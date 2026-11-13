from app.ai.analyzer import analyze_prompt
from app.ai.generator import generate_records
from app.domains.quality.service import evaluate_records


def test_support_prompt_becomes_typed_specification():
    spec = analyze_prompt("Generate 50 English and Hindi customer support conversations with sentiment.")
    assert spec.dataset_type == "customer_support"
    assert {column.name for column in spec.columns} >= {"customer_query", "agent_response", "sentiment"}
    assert spec.languages == ["English", "Hindi"]


def test_generated_records_pass_basic_quality_checks():
    spec = analyze_prompt("Generate customer support conversations")
    report = evaluate_records(generate_records(spec, 10), spec)
    assert report["valid_record_count"] == 10
    assert report["quality_score"] == 100

