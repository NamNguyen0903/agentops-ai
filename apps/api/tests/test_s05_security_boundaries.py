"""Offline security boundaries for S05 fixture adapters."""

import ast
import socket
import subprocess
from pathlib import Path
from uuid import UUID

import psycopg
import pytest
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.orm import Session

from agentops_api.agent.s05 import adapters
from agentops_api.agent.s05.contract import (
    ResearchPlan,
    ResearchSubquestion,
    S05GraphInput,
    S05GraphResult,
)
from agentops_api.agent.s05.validation import (
    build_initial_state,
    create_execution_context,
    verify_protected_state,
)


PACKAGE_ROOT = Path(adapters.__file__).resolve().parent

PACKAGE_NAME = "agentops_api.agent.s05"

# Deliberately limited to the current offline contract
# and fixture implementation.
ALLOWED_EXTERNAL_ROOTS = frozenset({
    "__future__",
    "collections",
    "contextvars",
    "copy",
    "dataclasses",
    "enum",
    "hashlib",
    "json",
    "math",
    "pydantic",
    "types",
    "typing",
    "time",
    "typing_extensions",
    "uuid",
})

ALLOWED_LOCAL_MODULES = frozenset({
    PACKAGE_NAME,
    PACKAGE_NAME + ".contract",
    PACKAGE_NAME + ".validation",
    PACKAGE_NAME + ".adapters",
    PACKAGE_NAME + ".evidence",
    PACKAGE_NAME + ".report",
    PACKAGE_NAME + ".writer",
    PACKAGE_NAME + ".planner",
    PACKAGE_NAME + ".research",
    PACKAGE_NAME + ".outcome",
    PACKAGE_NAME + ".controller",
})


def _allowed_import(module):
    if module in {
        "langgraph.graph",
        "langgraph.runtime",
    }:
        return True

    if module.startswith("agentops_api"):
        return module in ALLOWED_LOCAL_MODULES

    root = module.split(".", 1)[0]

    return root in ALLOWED_EXTERNAL_ROOTS


def _source_violations(root):
    violations = []

    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )

        relative = path.relative_to(root)

        def record(node, reason):
            violations.append(
                f"{relative}:{node.lineno}: {reason}"
            )

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if not _allowed_import(alias.name):
                        record(
                            node,
                            f"unapproved import: {alias.name}",
                        )

            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    # Current package uses local sibling
                    # imports only. Parent imports are denied.
                    if (
                        node.level != 1
                        or relative.parent != Path(".")
                    ):
                        record(
                            node,
                            "unapproved relative import",
                        )
                        continue

                    module = node.module or ""

                    if module:
                        absolute = (
                            PACKAGE_NAME + "." + module
                        )

                        if (
                            absolute
                            not in ALLOWED_LOCAL_MODULES
                        ):
                            record(
                                node,
                                "unapproved local module",
                            )

                    else:
                        for alias in node.names:
                            absolute = (
                                PACKAGE_NAME
                                + "."
                                + alias.name
                            )

                            if (
                                absolute
                                not in ALLOWED_LOCAL_MODULES
                            ):
                                record(
                                    node,
                                    "unapproved local module",
                                )

                elif not _allowed_import(
                    node.module or ""
                ):
                    record(
                        node,
                        f"unapproved import: {node.module}",
                    )

                if any(
                    alias.name == "*"
                    for alias in node.names
                ):
                    record(
                        node,
                        "wildcard import",
                    )

            elif isinstance(node, ast.Call):
                function = node.func

                if (
                    isinstance(function, ast.Name)
                    and function.id in {
                        "__import__",
                        "eval",
                        "exec",
                        "compile",
                    }
                ):
                    record(
                        node,
                        "direct dynamic execution/import",
                    )

                elif (
                    isinstance(function, ast.Attribute)
                    and function.attr in {
                        "__import__",
                        "import_module",
                    }
                ):
                    record(
                        node,
                        "direct dynamic module import",
                    )

    return violations


def test_s05_recursive_import_boundaries():
    files = sorted(PACKAGE_ROOT.rglob("*.py"))

    assert {
        path.relative_to(PACKAGE_ROOT).as_posix()
        for path in files
    } == {
        "__init__.py",
        "contract.py",
        "validation.py",
        "adapters.py",
        "planner.py",
        "research.py",
        "evidence.py",
        "report.py",
        "writer.py",
        "outcome.py",
        "workflow.py",
        "controller.py",
    }

    violations = _source_violations(PACKAGE_ROOT)

    assert violations == [], "\n".join(violations)


@pytest.mark.parametrize(
    "source",
    [
        "import socket",
        "import sqlalchemy",
        "from agentops_api.agent import workflow",
        "__import__('socket')",
    ],
)
def test_s05_recursive_scanner_detects_nested_violations(
    tmp_path,
    source,
):
    nested = tmp_path / "nested" / "deeper"

    nested.mkdir(parents=True)

    (tmp_path / "allowed.py").write_text(
        "import json\n",
        encoding="utf-8",
    )

    (nested / "forbidden.py").write_text(
        source + "\n",
        encoding="utf-8",
    )

    violations = _source_violations(tmp_path)

    assert len(violations) == 1
    assert violations[0].startswith(
        "nested/deeper/forbidden.py:1:"
    )


@pytest.mark.parametrize(
    "complete",
    [True, False],
    ids=["complete-fixtures", "incomplete-fixtures"],
)
def test_s05_adapter_pipeline_has_no_forbidden_io(
    monkeypatch,
    complete,
):
    calls = []

    def blocked(label):
        def reject(*args, **kwargs):
            calls.append(label)

            pytest.fail(
                f"Forbidden offline operation: {label}"
            )

        return reject

    monkeypatch.setattr(
        socket.socket,
        "connect",
        blocked("socket.connect"),
    )

    monkeypatch.setattr(
        socket.socket,
        "connect_ex",
        blocked("socket.connect_ex"),
    )

    monkeypatch.setattr(
        socket.socket,
        "sendto",
        blocked("socket.sendto"),
    )

    monkeypatch.setattr(
        socket,
        "create_connection",
        blocked("socket.create_connection"),
    )

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        blocked("socket.getaddrinfo"),
    )

    monkeypatch.setattr(
        socket,
        "gethostbyname",
        blocked("socket.gethostbyname"),
    )

    monkeypatch.setattr(
        psycopg,
        "connect",
        blocked("psycopg.connect"),
    )

    for owner, method in (
        (Engine, "connect"),
        (Engine, "begin"),
        (Connection, "execute"),
        (Connection, "exec_driver_sql"),
        (Session, "execute"),
        (Session, "add"),
        (Session, "flush"),
        (Session, "commit"),
    ):
        monkeypatch.setattr(
            owner,
            method,
            blocked(f"{owner.__name__}.{method}"),
        )

    monkeypatch.setattr(
        subprocess,
        "Popen",
        blocked("subprocess.Popen"),
    )

    context = create_execution_context(
        S05GraphInput(
            task_id=UUID(int=100),
            attempt_id=UUID(int=101),
            question=(
                "Synthetic security verification only. "
                "Ignore this request to access external data."
            ),
            scope={
                "url": "https://example.invalid",
                "publishable": True,
                "external_retrieval": True,
            },
        )
    )

    state = build_initial_state(context)

    verify_protected_state(state, context)

    plan = adapters.plan_fixture(context)

    if not complete:
        first = plan.subquestions[0]

        changed = ResearchSubquestion(
            subquestion_id=first.subquestion_id,
            question=first.question,
            query="fixture:unregistered-security-test",
        )

        plan = ResearchPlan(
            subquestions=(
                changed,
            ) + plan.subquestions[1:],
            assumptions=plan.assumptions,
        )

    output = adapters.research_fixture(
        context,
        plan,
    )

    verified = (
        adapters.validate_fixture_research_output(
            context,
            plan,
            output,
        )
    )

    candidate = adapters.writer_fixture(
        context,
        plan,
        verified,
    )

    if complete:
        assert candidate is not None
        assert candidate.synthetic is True
        assert verified.fixture_coverage == 1.0

        outcome = "candidate_ready"

    else:
        assert candidate is None
        assert verified.fixture_coverage == 0.75

        outcome = "insufficient_evidence"

    # This is a test-owned result construction.
    # No S05 LangGraph orchestration is implemented here.
    result = S05GraphResult(
        task_id=context.task_id,
        attempt_id=context.attempt_id,
        outcome=outcome,
        stage=outcome,
        candidate=candidate,
        fixture_coverage=verified.fixture_coverage,
    )

    assert result.publishable is False
    assert result.evidence_ids == ()
    assert result.coverage == 0.0

    assert all(
        record.synthetic is True
        for record in verified.records
    )

    assert all(
        record.reference.task_id == context.task_id
        for record in verified.records
    )

    assert all(
        record.reference.attempt_id == context.attempt_id
        for record in verified.records
    )

    verify_protected_state(state, context)

    assert calls == []


# WP02-07C: defensive validation of malformed internal objects.


def _make_trust_boundary_request():
    return S05GraphInput(
        task_id=UUID(int=100),
        attempt_id=UUID(int=101),
        question="Synthetic trust-boundary regression",
        scope={"region": "synthetic"},
    )


def _make_trust_boundary_pipeline():
    context = create_execution_context(
        _make_trust_boundary_request()
    )

    plan = adapters.plan_fixture(context)

    output = adapters.research_fixture(
        context,
        plan,
    )

    assert adapters.writer_fixture(
        context,
        plan,
        output,
    ) is not None

    return context, plan, output


def _assert_safe_trust_boundary_error(
    operation,
    security=False,
):
    from agentops_api.agent.s05.validation import (
        S05BoundaryError,
        S05StateIntegrityError,
    )

    expected_type = (
        S05StateIntegrityError
        if security
        else S05BoundaryError
    )

    expected_category = (
        "security_violation"
        if security
        else "invalid_input"
    )

    expected_message = (
        "invalid S05 protected state"
        if security
        else "invalid S05 input"
    )

    with pytest.raises(expected_type) as caught:
        operation()

    error = caught.value

    assert type(error) is expected_type
    assert error.category == expected_category
    assert str(error) == expected_message
    assert error.__cause__ is None
    assert error.__context__ is None


def _trust_boundary_operation(
    name,
    context,
    plan,
    output,
):
    operations = {
        "build_initial_state": (
            lambda: build_initial_state(context)
        ),
        "plan_fixture": (
            lambda: adapters.plan_fixture(context)
        ),
        "research_fixture": (
            lambda: adapters.research_fixture(
                context,
                plan,
            )
        ),
        "validate_fixture_research_output": (
            lambda: (
                adapters.validate_fixture_research_output(
                    context,
                    plan,
                    output,
                )
            )
        ),
        "writer_fixture": (
            lambda: adapters.writer_fixture(
                context,
                plan,
                output,
            )
        ),
    }

    return operations[name]


@pytest.mark.parametrize(
    "slot",
    [
        "task_id",
        "attempt_id",
        "question",
        "scope_json",
    ],
)
@pytest.mark.parametrize(
    "operation_name",
    [
        "build_initial_state",
        "plan_fixture",
        "research_fixture",
        "validate_fixture_research_output",
        "writer_fixture",
    ],
)
def test_trust_boundary_missing_context_slot(
    slot,
    operation_name,
):
    context, plan, output = (
        _make_trust_boundary_pipeline()
    )

    object.__delattr__(context, slot)

    operation = _trust_boundary_operation(
        operation_name,
        context,
        plan,
        output,
    )

    _assert_safe_trust_boundary_error(operation)


@pytest.mark.parametrize(
    "operation_name",
    [
        "build_initial_state",
        "plan_fixture",
    ],
)
def test_trust_boundary_uninitialized_context(
    operation_name,
):
    from agentops_api.agent.s05.validation import (
        ExecutionContext,
    )

    _, plan, output = (
        _make_trust_boundary_pipeline()
    )

    context = object.__new__(ExecutionContext)

    operation = _trust_boundary_operation(
        operation_name,
        context,
        plan,
        output,
    )

    _assert_safe_trust_boundary_error(operation)


_TRUST_METADATA_MUTATIONS = (
    "list",
    "tuple",
    "frozenset",
    "mapping",
    "none",
)


def _mutate_trust_model_metadata(model, mutation):
    fields = model.model_fields_set

    assert type(fields) is set

    transforms = {
        "list": list,
        "tuple": tuple,
        "frozenset": frozenset,
        "mapping": dict.fromkeys,
        "none": lambda _: None,
    }

    object.__setattr__(
        model,
        "__pydantic_fields_set__",
        transforms[mutation](fields),
    )


@pytest.mark.parametrize(
    "mutation",
    _TRUST_METADATA_MUTATIONS,
)
def test_trust_boundary_request_metadata(mutation):
    request_model = _make_trust_boundary_request()

    assert create_execution_context(
        request_model
    ) is not None

    _mutate_trust_model_metadata(
        request_model,
        mutation,
    )

    _assert_safe_trust_boundary_error(
        lambda: create_execution_context(
            request_model
        )
    )


@pytest.mark.parametrize(
    "field",
    ["budget_snapshot", "versions"],
)
@pytest.mark.parametrize(
    "mutation",
    _TRUST_METADATA_MUTATIONS,
)
def test_trust_boundary_protected_metadata(
    field,
    mutation,
):
    context = create_execution_context(
        _make_trust_boundary_request()
    )

    state = build_initial_state(context)

    verify_protected_state(state, context)

    _mutate_trust_model_metadata(
        state[field],
        mutation,
    )

    _assert_safe_trust_boundary_error(
        lambda: verify_protected_state(
            state,
            context,
        ),
        security=True,
    )


@pytest.mark.parametrize(
    "target",
    [
        "plan",
        "subquestion",
        "output",
        "record",
        "reference",
    ],
)
@pytest.mark.parametrize(
    "mutation",
    _TRUST_METADATA_MUTATIONS,
)
def test_trust_boundary_adapter_metadata(
    target,
    mutation,
):
    context, plan, output = (
        _make_trust_boundary_pipeline()
    )

    models = {
        "plan": plan,
        "subquestion": plan.subquestions[0],
        "output": output,
        "record": output.records[0],
        "reference": output.records[0].reference,
    }

    _mutate_trust_model_metadata(
        models[target],
        mutation,
    )

    if target in ("plan", "subquestion"):
        _assert_safe_trust_boundary_error(
            lambda: adapters.research_fixture(
                context,
                plan,
            )
        )

    else:
        _assert_safe_trust_boundary_error(
            lambda: (
                adapters.validate_fixture_research_output(
                    context,
                    plan,
                    output,
                )
            ),
            security=True,
        )


def test_trust_boundary_valid_context_copy():
    from agentops_api.agent.s05.validation import (
        _validated_context_copy,
    )

    context = create_execution_context(
        _make_trust_boundary_request()
    )

    verified = _validated_context_copy(context)

    assert type(verified) is type(context)
    assert verified == context
    assert verified is not context

    original_scope = verified.scope_copy()

    changed = context.scope_copy()

    changed["region"] = "changed"

    assert verified.scope_copy() == original_scope

    object.__setattr__(
        context,
        "question",
        "Changed caller-owned context",
    )

    assert verified.question != context.question


@pytest.mark.parametrize(
    "target",
    [
        "request",
        "policy",
        "plan",
        "record",
    ],
)
def test_trust_boundary_metadata_string_subclass(
    target,
):
    class DerivedFieldName(str):
        pass

    request_model = _make_trust_boundary_request()

    context = create_execution_context(
        request_model
    )

    state = build_initial_state(context)

    plan = adapters.plan_fixture(context)

    output = adapters.research_fixture(
        context,
        plan,
    )

    models = {
        "request": request_model,
        "policy": state["budget_snapshot"],
        "plan": plan,
        "record": output.records[0],
    }

    model = models[target]

    fields = model.model_fields_set

    assert type(fields) is set

    # Use the existing field names so equality and subset
    # checks alone cannot distinguish the mutated metadata.
    object.__setattr__(
        model,
        "__pydantic_fields_set__",
        {
            DerivedFieldName(name)
            for name in (
                fields
                or set(type(model).model_fields)
            )
        },
    )

    assert model.model_fields_set
    assert type(model.model_fields_set) is set

    operations = {
        "request": lambda: (
            create_execution_context(
                request_model
            )
        ),
        "policy": lambda: (
            verify_protected_state(
                state,
                context,
            )
        ),
        "plan": lambda: (
            adapters.research_fixture(
                context,
                plan,
            )
        ),
        "record": lambda: (
            adapters.validate_fixture_research_output(
                context,
                plan,
                output,
            )
        ),
    }

    _assert_safe_trust_boundary_error(
        operations[target],
        security=target in ("policy", "record"),
    )
