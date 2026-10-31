"""Deterministic server-side plan guard (PRD 12.2).

Every plan - LLM output, cached fallback, or human edit - passes through this
guard before persistence and execution. The server recomputes risk from the
catalog and never trusts the model's values.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import ValidationError

from app.catalog import ACTION_CATALOG
from app.models import PlanSchema, Risk, TaskSchema


def enforce_plan(
    plan: PlanSchema,
    max_external: Optional[int] = None,
) -> Tuple[PlanSchema, List[Dict[str, Any]]]:
    """Sanitize and enforce the guard rules on a plan.

    Returns the guarded plan and a list of drop records
    ({"task_id", "action", "reason"} for each discarded task).
    """
    drops: List[Dict[str, Any]] = []
    kept: List[TaskSchema] = []
    used_ids: Set[str] = set()

    # 1. Drop unknown actions; validate params against the catalog; recompute risk.
    for raw in plan.tasks:
        action_def = ACTION_CATALOG.get(raw.action)
        if action_def is None:
            drops.append({"task_id": raw.id, "action": raw.action, "reason": "unknown_action"})
            continue

        try:
            params = action_def.params_schema.model_validate(raw.params)
        except ValidationError as exc:
            drops.append(
                {
                    "task_id": raw.id,
                    "action": raw.action,
                    "reason": "invalid_params",
                    "details": str(exc.errors()[:2]),
                }
            )
            continue

        task_id = (raw.id or "").strip() or f"t{len(kept) + 1}"
        while task_id in used_ids:
            task_id = f"{task_id}x"
        used_ids.add(task_id)

        kept.append(
            TaskSchema(
                id=task_id,
                action=raw.action,
                params=params.model_dump(),
                description=raw.description or action_def.description,
                depends_on=[d for d in raw.depends_on if d],
                risk=action_def.risk,  # Server-authoritative risk; model value ignored.
            )
        )

    # 2. Strip depends_on references to tasks that no longer exist.
    existing_ids = {t.id for t in kept}
    for task in kept:
        task.depends_on = [d for d in task.depends_on if d in existing_ids]

    # 3. Topological check (Kahn): anything unschedulable sits in (or behind) a cycle.
    remaining = {t.id: set(t.depends_on) for t in kept}
    while True:
        ready = [nid for nid, deps in remaining.items() if not deps]
        if not ready:
            break
        for nid in ready:
            remaining.pop(nid)
        for deps in remaining.values():
            deps.difference_update(ready)
    blocked: Set[str] = set(remaining.keys())
    if blocked:
        kept = [t for t in kept if t.id not in blocked]
        for task in kept:
            task.depends_on = [d for d in task.depends_on if d not in blocked]
        for task_id in blocked:
            dropped_action = next(
                (t.action for t in plan.tasks if (t.id or "") == task_id), "unknown"
            )
            drops.append({"task_id": task_id, "action": dropped_action, "reason": "dependency_cycle"})

    # 4. Every external task must be preceded (transitively) by a read or draft task.
    survivors: List[TaskSchema] = []
    for task in kept:
        if task.risk == Risk.external and not any(
            a.risk == Risk.read or a.action.startswith("draft_") for a in _ancestors(kept, task)
        ):
            drops.append({"task_id": task.id, "action": task.action, "reason": "ungrounded_external"})
            continue
        survivors.append(task)
    kept = survivors

    # 5. Enforce the per-run cap on external actions (first come, first served).
    if max_external is not None:
        external_count = 0
        capped: List[TaskSchema] = []
        for task in kept:
            if task.risk == Risk.external:
                external_count += 1
                if external_count > max_external:
                    drops.append({"task_id": task.id, "action": task.action, "reason": "external_cap"})
                    continue
            capped.append(task)
        kept = capped

    return PlanSchema(tasks=kept, clarifying_question=plan.clarifying_question), drops


def _ancestors(tasks: List[TaskSchema], target: TaskSchema) -> List[TaskSchema]:
    """Return all transitive dependency tasks of `target`."""
    by_id = {t.id: t for t in tasks}
    seen: Set[str] = set()
    frontier = [d for d in target.depends_on if d in by_id]
    result: List[TaskSchema] = []
    while frontier:
        nid = frontier.pop()
        if nid in seen:
            continue
        seen.add(nid)
        node = by_id[nid]
        result.append(node)
        frontier.extend(d for d in node.depends_on if d in by_id)
    return result
