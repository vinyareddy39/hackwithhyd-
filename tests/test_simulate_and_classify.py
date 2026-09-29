"""Tests for simulate_response bias tables, reply templates, and classify_outcome."""

import random
from config import OUTCOMES, PERSONAS, RESPONSE_OUTCOMES
import classify_outcome
import reply_templates
import simulate_response


def test_persona_bias_tables_structure():
    """Verify bias tables exist for all 4 personas with varied winning angles."""
    for persona in PERSONAS:
        assert persona in simulate_response.BIAS_TABLES
        biases = simulate_response.BIAS_TABLES[persona]
        for angle in ["referenced_metric", "referenced_opinion", "generic"]:
            assert angle in biases
            assert "interested" in biases[angle]
            assert "reply" in biases[angle]
            total_resp = biases[angle]["interested"] + biases[angle]["reply"]
            assert 0.0 <= total_resp <= 1.0


def test_simulation_persona_winning_angles():
    """Verify that Founder, Technical Buyer, HR Manager, and Student have winning angles."""
    rng = random.Random(42)
    # Founder winning angle: referenced_metric
    founder = {"persona_type": "Founder"}
    f_metric_resp = sum(
        1 for _ in range(200)
        if simulate_response.simulate(founder, "referenced_metric", rng=rng)[0] in RESPONSE_OUTCOMES
    )
    f_generic_resp = sum(
        1 for _ in range(200)
        if simulate_response.simulate(founder, "generic", rng=rng)[0] in RESPONSE_OUTCOMES
    )
    assert f_metric_resp > f_generic_resp, "Founder should respond more to referenced_metric than generic"

    # Tech Buyer winning angle: referenced_opinion
    buyer = {"persona_type": "Technical Buyer"}
    b_opinion_resp = sum(
        1 for _ in range(200)
        if simulate_response.simulate(buyer, "referenced_opinion", rng=rng)[0] in RESPONSE_OUTCOMES
    )
    b_generic_resp = sum(
        1 for _ in range(200)
        if simulate_response.simulate(buyer, "generic", rng=rng)[0] in RESPONSE_OUTCOMES
    )
    assert b_opinion_resp > b_generic_resp, "Technical Buyer should respond more to referenced_opinion than generic"


def test_reply_templates_retrieval_and_all_classify_correctly():
    """Verify 4+ templates per persona x outcome and EVERY template classifies to its intended outcome."""
    templates = reply_templates.load_templates()
    for persona in PERSONAS:
        assert persona in templates
        for outcome in OUTCOMES:
            options = templates[persona].get(outcome, [])
            assert len(options) >= 4, f"Expected 4+ templates for {persona} x {outcome}, got {len(options)}"
            for text in options:
                classified = classify_outcome.classify_outcome(text)
                assert classified == outcome, (
                    f"Template for {persona} x {outcome} classified as {classified}: '{text}'"
                )


def test_simulate_seeded_samples_match_bias_tables():
    """Verify over 2000 seeded samples that empirical rates match bias tables within 3%."""
    rng = random.Random(1337)
    n_samples = 2000

    for persona in PERSONAS:
        prospect = {"persona_type": persona}
        for angle in ["referenced_metric", "referenced_opinion", "generic"]:
            expected_interested = simulate_response.BIAS_TABLES[persona][angle]["interested"]
            expected_reply = simulate_response.BIAS_TABLES[persona][angle]["reply"]
            expected_no_reply = 1.0 - (expected_interested + expected_reply)

            counts = {"interested": 0, "reply": 0, "no_reply": 0}
            for _ in range(n_samples):
                outcome, _ = simulate_response.simulate(prospect, angle, rng=rng)
                counts[outcome] += 1

            obs_interested = counts["interested"] / n_samples
            obs_reply = counts["reply"] / n_samples
            obs_no_reply = counts["no_reply"] / n_samples

            assert abs(obs_interested - expected_interested) < 0.035, (
                f"{persona} {angle} interested: expected {expected_interested}, observed {obs_interested}"
            )
            assert abs(obs_reply - expected_reply) < 0.035, (
                f"{persona} {angle} reply: expected {expected_reply}, observed {obs_reply}"
            )
            assert abs(obs_no_reply - expected_no_reply) < 0.035, (
                f"{persona} {angle} no_reply: expected {expected_no_reply}, observed {obs_no_reply}"
            )


def test_classify_outcome_heuristics():
    """Verify outcome classifier accurately categorizes varied reply texts."""
    # Positive
    positive_samples = [
        "Let's jump on a quick call this Thursday to discuss.",
        "Can you send over your calendar link so we can schedule a demo?",
        "Sounds interesting, what is your pricing model for 20 seats?",
        "I'd be glad to learn more and connect next week.",
    ]
    for text in positive_samples:
        assert classify_outcome.classify_outcome(text) == "interested"

    # Negative / Rejection / OOO
    neutral_samples = [
        "Thanks Alex, but we are not interested right now.",
        "Automatic reply: I will be out of the office until Monday.",
        "We are under a strict budget freeze, not a fit.",
        "Please remove me from your outreach list.",
    ]
    for text in neutral_samples:
        assert classify_outcome.classify_outcome(text) == "reply"

    # No reply
    assert classify_outcome.classify_outcome("") == "no_reply"
    assert classify_outcome.classify_outcome("   ") == "no_reply"
    assert classify_outcome.classify_outcome("[no reply]") == "no_reply"
