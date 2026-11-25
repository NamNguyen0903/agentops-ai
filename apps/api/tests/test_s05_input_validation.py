"""Input snapshot and mutation detection tests for S05."""

import json
from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest

from agentops_api.agent.s05.contract import (
    S05GraphInput,
    S05GraphState,
)
from agentops_api.agent.s05.validation import (
    ExecutionContext,
    S05BoundaryError,
    S05StateIntegrityError,
    build_initial_state,
    create_execution_context,
    verify_protected_state,
)


TASK_ID = UUID("00000000-0000-4000-8000-000000000001")
ATTEMPT_ID = UUID("00000000-0000-4000-8000-000000000002")
OTHER_ID = UUID("00000000-0000-4000-8000-000000000003")


def make_request():
    return S05GraphInput(
        task_id=TASK_ID,
        attempt_id=ATTEMPT_ID,
        question="Compare synthetic competitors",
        scope={
            "market": {
                "segments": ["synthetic"],
            },
        },
    )


def assert_integrity_rejected(request):
    with pytest.raises(
        ValueError,
        match=r"^invalid input integrity$",
    ) as caught:
        request.verified_input_snapshot()

    assert caught.value.__cause__ is None


def test_valid_request_has_immutable_snapshot():
    request = make_request()

    snapshot = request.verified_input_snapshot()

    assert type(snapshot) is tuple
    assert len(snapshot) == 4
    assert snapshot[0] == TASK_ID
    assert snapshot[1] == ATTEMPT_ID
    assert snapshot[2] == request.question
    assert type(snapshot[3]) is str

    assert json.loads(snapshot[3]) == request.scope


def test_snapshot_is_not_public_input_field():
    request = make_request()

    assert "_input_snapshot" not in request.model_dump()
    assert "_input_snapshot" not in S05GraphInput.model_fields


def test_snapshot_contains_no_nested_mutable_values():
    request = make_request()

    snapshot = request.verified_input_snapshot()

    assert all(
        type(value) in (UUID, str, type(None))
        for value in snapshot
    )


def test_original_scope_mutation_does_not_change_request():
    original = {
        "market": {
            "segments": ["synthetic"],
        },
    }

    request = S05GraphInput(
        task_id=TASK_ID,
        question="Offline fixture comparison",
        scope=original,
    )

    before = request.verified_input_snapshot()

    original["market"]["segments"].append("modified")

    assert request.verified_input_snapshot() == before

    assert request.scope == {
        "market": {
            "segments": ["synthetic"],
        },
    }


def test_valid_nested_scope_mutation_is_rejected():
    request = make_request()

    request.verified_input_snapshot()

    request.scope["market"]["segments"].append("changed")

    assert_integrity_rejected(request)


def test_invalid_nested_scope_mutation_is_rejected():
    request = make_request()

    request.verified_input_snapshot()

    request.scope["market"]["value"] = float("nan")

    assert_integrity_rejected(request)


def test_nested_type_change_is_rejected():
    request = make_request()

    request.scope["market"]["value"] = True

    assert_integrity_rejected(request)


def test_equal_numeric_values_with_different_types_rejected():
    request = S05GraphInput(
        task_id=TASK_ID,
        question="Synthetic fixture comparison",
        scope={"value": 1},
    )

    request.verified_input_snapshot()

    request.scope["value"] = 1.0

    assert_integrity_rejected(request)


def test_canonical_scope_ignores_dictionary_key_order():
    request = S05GraphInput(
        task_id=TASK_ID,
        question="Synthetic fixture comparison",
        scope={"b": 2, "a": 1},
    )

    before = request.verified_input_snapshot()

    value = request.scope.pop("a")
    request.scope["a"] = value

    assert request.verified_input_snapshot() == before


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_id", OTHER_ID),
        ("attempt_id", OTHER_ID),
        ("attempt_id", None),
        ("question", "Changed valid question"),
        ("question", ""),
        ("question", " "),
        ("question", 123),
        ("question", "x" * 4001),
        ("scope", {"market": "changed"}),
        ("scope", []),
        ("scope", {"value": float("inf")}),
        ("scope", {"value": "x" * 8192}),
    ],
)
def test_model_copy_update_cannot_bypass_integrity(
    field,
    value,
):
    request = make_request()

    before = request.verified_input_snapshot()

    modified = request.model_copy(
        update={field: value},
    )

    assert_integrity_rejected(modified)

    assert request.verified_input_snapshot() == before


def test_valid_model_copy_preserves_snapshot():
    request = make_request()

    copied = request.model_copy(deep=True)

    assert copied.verified_input_snapshot() == (
        request.verified_input_snapshot()
    )


def test_deep_copy_nested_mutation_preserves_original():
    request = make_request()
    before = request.verified_input_snapshot()

    copied = request.model_copy(deep=True)

    copied.scope["market"]["segments"].append("changed")

    assert_integrity_rejected(copied)

    assert request.verified_input_snapshot() == before


def test_model_construct_without_validation_is_rejected():
    request = make_request()

    constructed = S05GraphInput.model_construct(
        **request.model_dump(),
    )

    assert_integrity_rejected(constructed)


def test_missing_snapshot_is_rejected():
    request = make_request()

    request._input_snapshot = None

    assert_integrity_rejected(request)


def test_canonical_snapshot_is_independent_from_scope():
    request = make_request()

    snapshot = request.verified_input_snapshot()

    decoded = json.loads(snapshot[3])
    decoded["market"]["segments"].append("external-change")

    assert request.verified_input_snapshot() == snapshot

    assert request.scope["market"]["segments"] == [
        "synthetic",
    ]


def test_integrity_error_does_not_expose_input_values():
    request = make_request()

    marker = "synthetic-private-marker-do-not-expose"

    modified = request.model_copy(
        update={"question": marker},
    )

    with pytest.raises(ValueError) as caught:
        modified.verified_input_snapshot()

    assert str(caught.value) == "invalid input integrity"
    assert marker not in str(caught.value)
    assert marker not in repr(caught.value)


def assert_boundary_rejected(request):
    with pytest.raises(
        S05BoundaryError,
        match=r"^invalid S05 input$",
    ) as caught:
        create_execution_context(request)

    assert caught.value.category == "invalid_input"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_execution_context_accepts_valid_request():
    request = make_request()

    context = create_execution_context(request)

    assert type(context) is ExecutionContext
    assert context.task_id == TASK_ID
    assert context.attempt_id == ATTEMPT_ID
    assert context.question == request.question
    assert context.scope_copy() == request.scope

    assert context.policy.publishable is False
    assert context.policy.max_adapter_invocations == 4
    assert context.versions.graph == "s05-specialized-agent-v1"


def test_execution_context_supports_optional_attempt():
    request = S05GraphInput(
        task_id=TASK_ID,
        question="Offline comparison",
    )

    context = create_execution_context(request)

    assert context.attempt_id is None
    assert context.scope_copy() == {}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_id", OTHER_ID),
        ("attempt_id", OTHER_ID),
        ("question", "Changed question"),
        ("scope_json", '{"changed":true}'),
    ],
)
def test_execution_context_fields_are_frozen(field, value):
    context = create_execution_context(make_request())

    with pytest.raises(FrozenInstanceError):
        setattr(context, field, value)


def test_execution_context_has_no_instance_dictionary():
    context = create_execution_context(make_request())

    assert not hasattr(context, "__dict__")


def test_execution_context_scope_copy_is_independent():
    context = create_execution_context(make_request())

    first = context.scope_copy()
    second = context.scope_copy()

    assert first == second
    assert first is not second

    first["market"]["segments"].append("modified")

    assert context.scope_copy() == second

    assert second["market"]["segments"] == [
        "synthetic",
    ]


def test_context_does_not_alias_original_request():
    request = make_request()

    context = create_execution_context(request)
    original_scope = context.scope_copy()

    request.scope["market"]["segments"].append("modified")

    assert context.scope_copy() == original_scope
    assert_boundary_rejected(request)


def test_context_policy_objects_are_independent():
    context = create_execution_context(make_request())

    first = context.policy
    second = context.policy

    assert first == second
    assert first is not second

    modified = first.model_copy(
        update={"max_adapter_invocations": 100},
    )

    assert modified.max_adapter_invocations == 100
    assert context.policy.max_adapter_invocations == 4


def test_context_version_objects_are_independent():
    context = create_execution_context(make_request())

    first = context.versions
    second = context.versions

    assert first == second
    assert first is not second

    modified = first.model_copy(
        update={"model": "unapproved-live-model"},
    )

    assert modified.model == "unapproved-live-model"
    assert context.versions.model == "none"


def test_boundary_rejects_valid_nested_mutation():
    request = make_request()

    create_execution_context(request)

    request.scope["market"]["segments"].append("changed")

    assert_boundary_rejected(request)


def test_boundary_rejects_invalid_nested_mutation():
    request = make_request()

    create_execution_context(request)

    request.scope["market"]["value"] = float("nan")

    assert_boundary_rejected(request)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_id", OTHER_ID),
        ("attempt_id", OTHER_ID),
        ("attempt_id", None),
        ("question", "Changed valid question"),
        ("question", 123),
        ("scope", {"valid": "but changed"}),
    ],
)
def test_boundary_rejects_model_copy_mutations(
    field,
    value,
):
    request = make_request()

    create_execution_context(request)

    modified = request.model_copy(
        update={field: value},
    )

    assert_boundary_rejected(modified)


@pytest.mark.parametrize(
    "field",
    [
        "policy",
        "versions",
        "allowed_tools",
        "publishable",
        "budget",
    ],
)
def test_boundary_rejects_model_copy_extra_fields(field):
    request = make_request()

    create_execution_context(request)

    modified = request.model_copy(
        update={field: {}},
    )

    assert_boundary_rejected(modified)


def test_boundary_rejects_constructed_request():
    request = make_request()

    constructed = S05GraphInput.model_construct(
        **request.model_dump(),
    )

    assert_boundary_rejected(constructed)


def test_boundary_rejects_missing_input_snapshot():
    request = make_request()

    request._input_snapshot = None

    assert_boundary_rejected(request)


@pytest.mark.parametrize("invalid_request", [
    None,
    {},
    [],
    "not a request",
])
def test_boundary_rejects_unexpected_request_types(invalid_request):
    assert_boundary_rejected(invalid_request)


def test_boundary_rejects_request_subclass():
    class DerivedRequest(S05GraphInput):
        pass

    request = DerivedRequest(
        task_id=TASK_ID,
        question="Valid but unexpected model class",
    )

    assert_boundary_rejected(request)


def test_boundary_accepts_independent_valid_copy():
    request = make_request()

    copied = request.model_copy(deep=True)

    original_context = create_execution_context(request)
    copied_context = create_execution_context(copied)

    assert copied_context == original_context
    assert copied_context is not original_context


def test_boundary_checks_snapshot_before_revalidation(
    monkeypatch,
):
    request = make_request()

    request.scope["market"]["segments"].append("changed")

    def forbidden_revalidation(*args, **kwargs):
        pytest.fail(
            "Revalidation happened before integrity rejection"
        )

    monkeypatch.setattr(
        S05GraphInput,
        "__init__",
        forbidden_revalidation,
    )

    assert_boundary_rejected(request)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_id", "invalid-uuid"),
        ("attempt_id", "invalid-uuid"),
        ("question", ""),
        ("question", " "),
        ("question", "x" * 4001),
        ("scope_json", "{} "),
        ("scope_json", "[]"),
        ("scope_json", '{"x":NaN}'),
        ("scope_json", '{"b":2,"a":1}'),
        ("scope_json", '{"value":"' + "x" * 8192 + '"}'),
    ],
)
def test_direct_context_construction_rejects_invalid_data(
    field,
    value,
):
    valid = {
        "task_id": TASK_ID,
        "attempt_id": ATTEMPT_ID,
        "question": "Offline comparison",
        "scope_json": "{}",
    }

    ExecutionContext(**valid)

    valid[field] = value

    with pytest.raises(S05BoundaryError) as caught:
        ExecutionContext(**valid)

    assert caught.value.category == "invalid_input"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_safe_boundary_error_does_not_expose_input():
    request = make_request()

    marker = "synthetic-private-boundary-marker"

    modified = request.model_copy(
        update={"question": marker},
    )

    with pytest.raises(S05BoundaryError) as caught:
        create_execution_context(modified)

    assert marker not in str(caught.value)
    assert marker not in repr(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_context_repr_redacts_sensitive_fields():
    marker = "synthetic-context-private-marker"

    request = S05GraphInput(
        task_id=TASK_ID,
        attempt_id=ATTEMPT_ID,
        question=marker,
        scope={"private": marker},
    )

    context = create_execution_context(request)

    representation = repr(context)

    assert marker not in representation
    assert str(TASK_ID) not in representation
    assert str(ATTEMPT_ID) not in representation
    assert representation == "ExecutionContext(<redacted>)"


def make_context_and_state():
    context = create_execution_context(make_request())
    state = build_initial_state(context)

    verify_protected_state(state, context)

    return context, state


def assert_state_rejected(state, context):
    with pytest.raises(
        S05StateIntegrityError,
        match=r"^invalid S05 protected state$",
    ) as caught:
        verify_protected_state(state, context)

    assert caught.value.category == "security_violation"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_initial_state_has_all_seventeen_channels():
    context, state = make_context_and_state()

    assert len(state) == 17
    assert set(state) == set(S05GraphState.__annotations__)

    assert state["task_id"] == str(context.task_id)
    assert state["attempt_id"] == str(context.attempt_id)
    assert state["question"] == context.question
    assert state["scope"] == context.scope_copy()


def test_initial_state_has_safe_defaults():
    _, state = make_context_and_state()

    assert state["stage"] == "pending"
    assert state["plan"] is None
    assert state["research_output"] is None
    assert state["draft_report"] is None
    assert state["result"] is None
    assert state["error_category"] is None

    assert state["evidence_ids"] == ()
    assert state["coverage"] == 0.0
    assert state["fixture_coverage"] == 0.0
    assert state["repair_used"] is False

    assert state["counters"].adapter_invocations == 0
    assert state["counters"].repair_attempts == 0
    assert state["budget_snapshot"].publishable is False


def test_initial_state_preserves_optional_attempt():
    context = create_execution_context(
        S05GraphInput(
            task_id=TASK_ID,
            question="Offline fixture comparison",
        )
    )

    state = build_initial_state(context)

    assert state["attempt_id"] is None

    verify_protected_state(state, context)


def test_initial_state_instances_are_independent():
    context, first = make_context_and_state()
    second = build_initial_state(context)

    assert first == second
    assert first is not second

    for name in (
        "scope",
        "budget_snapshot",
        "versions",
        "counters",
    ):
        assert first[name] is not second[name]

    first["scope"]["market"]["segments"].append(
        "unauthorized mutation"
    )

    assert second["scope"] == context.scope_copy()

    verify_protected_state(second, context)
    assert_state_rejected(first, context)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_id", str(OTHER_ID)),
        ("attempt_id", str(OTHER_ID)),
        ("attempt_id", None),
        ("question", "Changed valid question"),
        ("scope", {"changed": True}),
        ("evidence_ids", ("fabricated-evidence",)),
        ("evidence_ids", []),
        ("coverage", 0.5),
        ("coverage", 0),
        ("coverage", False),
        ("coverage", float("nan")),
    ],
)
def test_protected_state_rejects_single_field_mutation(
    field,
    value,
):
    context, state = make_context_and_state()

    state[field] = value

    assert_state_rejected(state, context)


def test_protected_state_rejects_nested_scope_mutation():
    context, state = make_context_and_state()

    state["scope"]["market"]["segments"].append("changed")

    assert_state_rejected(state, context)


def test_protected_state_rejects_numeric_type_coercion():
    context = create_execution_context(
        S05GraphInput(
            task_id=TASK_ID,
            question="Synthetic comparison",
            scope={"value": 1},
        )
    )

    state = build_initial_state(context)

    verify_protected_state(state, context)

    state["scope"]["value"] = True

    assert_state_rejected(state, context)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_adapter_invocations", 5),
        ("max_repair_attempts", True),
        ("paid_cost_usd", False),
        ("live_model_calls", 1),
        ("publishable", True),
        ("publishable", 0),
        ("unexpected_tool", "live-search"),
    ],
)
def test_protected_state_rejects_policy_bypass(field, value):
    context, state = make_context_and_state()

    state["budget_snapshot"] = (
        state["budget_snapshot"].model_copy(
            update={field: value}
        )
    )

    assert_state_rejected(state, context)

    assert context.policy.publishable is False
    assert context.policy.live_model_calls == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("graph", "s04-single-agent-v1"),
        ("model", "unapproved-model"),
        ("prompt", "unapproved-prompt"),
        ("fixture", "unapproved-fixture"),
        ("unexpected_version", "arbitrary"),
    ],
)
def test_protected_state_rejects_version_bypass(
    field,
    value,
):
    context, state = make_context_and_state()

    state["versions"] = state["versions"].model_copy(
        update={field: value}
    )

    assert_state_rejected(state, context)


def test_protected_state_rejects_missing_channel():
    context, state = make_context_and_state()

    del state["scope"]

    assert_state_rejected(state, context)


def test_protected_state_rejects_unknown_channel():
    context, state = make_context_and_state()

    state["allowed_tools"] = ("web-search",)

    assert_state_rejected(state, context)


def test_protected_state_rejects_other_task_context():
    context, state = make_context_and_state()

    other_context = create_execution_context(
        S05GraphInput(
            task_id=OTHER_ID,
            attempt_id=context.attempt_id,
            question=context.question,
            scope=context.scope_copy(),
        )
    )

    assert_state_rejected(state, other_context)


def test_protected_state_accepts_mutable_workflow_channels():
    context, state = make_context_and_state()

    state["stage"] = "planned"

    # This validator checks protected fields only.
    # Plan and stage consistency belong to WP03-WP04.
    verify_protected_state(state, context)


def test_protected_state_error_redacts_mutation():
    context, state = make_context_and_state()

    marker = "synthetic-sensitive-state-marker"

    state["question"] = marker

    with pytest.raises(S05StateIntegrityError) as caught:
        verify_protected_state(state, context)

    assert marker not in str(caught.value)
    assert marker not in repr(caught.value)
    assert caught.value.__context__ is None


def test_initial_state_rejects_unexpected_context_type():
    with pytest.raises(S05BoundaryError) as caught:
        build_initial_state({})

    assert caught.value.category == "invalid_input"


# Signed-zero integrity verification.


@pytest.mark.parametrize("original_zero", [0.0, -0.0])
def test_signed_zero_unchanged_scope_is_accepted(original_zero):
    context = create_execution_context(
        S05GraphInput(
            task_id=TASK_ID,
            question="Synthetic signed-zero scope",
            scope={"nested": {"value": original_zero}},
        )
    )

    state = build_initial_state(context)

    assert state["scope"]["nested"]["value"].hex() == (
        original_zero.hex()
    )

    verify_protected_state(state, context)


@pytest.mark.parametrize("original_zero", [0.0, -0.0])
def test_signed_zero_scope_mutation_is_rejected(original_zero):
    context = create_execution_context(
        S05GraphInput(
            task_id=TASK_ID,
            question="Synthetic signed-zero mutation",
            scope={"nested": {"value": original_zero}},
        )
    )

    state = build_initial_state(context)

    verify_protected_state(state, context)

    changed = -original_zero

    assert changed == original_zero
    assert changed.hex() != original_zero.hex()

    state["scope"]["nested"]["value"] = changed

    assert_state_rejected(state, context)


def test_signed_zero_real_coverage_mutation_is_rejected():
    context, state = make_context_and_state()

    assert state["coverage"].hex() == (0.0).hex()

    state["coverage"] = -0.0

    assert_state_rejected(state, context)


@pytest.mark.parametrize(
    ("actual", "expected", "valid"),
    [
        (0.0, 0.0, True),
        (-0.0, -0.0, True),
        (0.0, -0.0, False),
        (-0.0, 0.0, False),
        (0.25, 0.25, True),
        (0.25, 0.5, False),
        (1, 1.0, False),
        (True, 1, False),
        (float("nan"), float("nan"), False),
    ],
)
def test_signed_zero_strict_comparison_semantics(
    actual,
    expected,
    valid,
):
    from agentops_api.agent.s05.validation import (
        _strict_equal,
    )

    assert _strict_equal(actual, expected) is valid
