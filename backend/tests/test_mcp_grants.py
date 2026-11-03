"""Per-tool grants and the narrowing header: rules, header parsing, and properties that must always hold."""

import random
import uuid

import pytest

from app.services.mcp_grants import (
	MAX_SCOPE_PATTERNS,
	REASON_DENIED,
	REASON_NOT_GRANTED,
	REASON_OUT_OF_SCOPE,
	Caller,
	GrantRule,
	ScopeHeaderError,
	ToolAccess,
	build_access,
	parse_scope_header,
)

USER_ID, TEAM_ID, KEY_ID = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
CALLER = Caller(user_id=USER_ID, role="developer", team_id=TEAM_ID, api_key_id=KEY_ID)


def rule(subject_type: str, subject_id: str, pattern: str, effect: str) -> GrantRule:
	return GrantRule(subject_type, subject_id, pattern, effect)


# -- grants -------------------------------------------------------------------------------------


def test_no_grants_means_no_restriction():
	assert build_access([], CALLER).check("github__anything").allowed


def test_allow_grants_restrict_the_subjects_they_apply_to():
	access = build_access([rule("role", "developer", "github__*", "allow")], CALLER)
	assert access.check("github__search").allowed
	verdict = access.check("jira__create_issue")
	assert not verdict.allowed and verdict.reason == REASON_NOT_GRANTED


def test_allow_grants_for_someone_else_do_not_restrict_the_caller():
	access = build_access([rule("role", "viewer", "github__*", "allow"), rule("user", str(uuid.uuid4()), "x", "allow")], CALLER)
	assert access.check("jira__create_issue").allowed


def test_deny_wins_over_allow_at_any_level():
	access = build_access([
		rule("role", "developer", "github__*", "allow"),
		rule("api_key", str(KEY_ID), "github__delete_*", "deny"),
		rule("team", str(TEAM_ID), "github__delete_repo", "allow"),
	], CALLER)
	verdict = access.check("github__delete_repo")
	assert not verdict.allowed and verdict.reason == REASON_DENIED
	assert access.check("github__search").allowed


@pytest.mark.parametrize("subject", [("role", "developer"), ("user", str(USER_ID)), ("team", str(TEAM_ID)), ("api_key", str(KEY_ID))])
def test_every_subject_type_applies(subject):
	access = build_access([rule(*subject, "jira__*", "deny")], CALLER)
	assert not access.check("jira__x").allowed


def test_a_key_without_a_team_ignores_team_grants():
	solo = Caller(user_id=USER_ID, role="developer", team_id=None, api_key_id=KEY_ID)
	assert build_access([rule("team", str(TEAM_ID), "*", "deny")], solo).check("github__x").allowed


def test_patterns_are_case_sensitive_globs_over_the_namespaced_name():
	access = build_access([rule("role", "developer", "GitHub__*", "allow")], CALLER)
	assert not access.check("github__search").allowed


# -- header -------------------------------------------------------------------------------------


def test_absent_header_means_no_scope():
	assert parse_scope_header([]) is None


def test_header_parses_trims_and_dedupes():
	assert parse_scope_header(["github__search, jira__* ,github__search"]) == ("github__search", "jira__*")


@pytest.mark.parametrize("value", ["", " ", ",", "a,,b", "a b", "../x", "[abc]", "x" * 201, "a;b", "a\tb c", "café"])
def test_malformed_header_is_rejected(value):
	with pytest.raises(ScopeHeaderError):
		parse_scope_header([value])


def test_too_many_patterns_and_repeated_headers_are_rejected():
	with pytest.raises(ScopeHeaderError):
		parse_scope_header([",".join(f"t{i}" for i in range(MAX_SCOPE_PATTERNS + 1))])
	with pytest.raises(ScopeHeaderError):
		parse_scope_header(["a", "b"])


def test_scope_narrows_and_reports_why():
	base = build_access([rule("role", "developer", "github__*", "allow")], CALLER)
	scoped = build_access([rule("role", "developer", "github__*", "allow")], CALLER, scope=("github__search",))
	assert base.check("github__read").allowed
	verdict = scoped.check("github__read")
	assert not verdict.allowed and verdict.reason == REASON_OUT_OF_SCOPE
	assert scoped.check("github__search").allowed


def test_scope_cannot_grant_what_the_grants_deny():
	scoped = build_access([rule("role", "developer", "github__*", "allow")], CALLER, scope=("*",))
	assert not scoped.check("jira__x").allowed


def test_summary_lists_applied_patterns_and_is_capped():
	rules = [rule("role", "developer", f"t{i}", "allow") for i in range(80)]
	summary = build_access(rules, CALLER, scope=("t1",)).summary()
	assert len(summary["allow"]) == 50 and summary["scope"] == ["t1"] and summary["deny"] == []


# -- properties (seeded, deterministic) ---------------------------------------------------------

SERVERS = ("github", "jira", "slack", "evil")
TOOLS = ("search", "create_issue", "delete_repo", "read", "write_file")
NAMES = [f"{s}__{t}" for s in SERVERS for t in TOOLS]
PATTERNS = NAMES + ["*", "github__*", "jira__*", "*__delete_*", "*__read", "s*", "slack__r?ad", "nomatch", "evil__*"]
SUBJECTS = [("role", "developer"), ("role", "admin"), ("user", str(USER_ID)), ("team", str(TEAM_ID)), ("api_key", str(KEY_ID)),
            ("user", str(uuid.uuid4())), ("team", str(uuid.uuid4()))]


def random_rules(rng: random.Random) -> list[GrantRule]:
	return [rule(*rng.choice(SUBJECTS), rng.choice(PATTERNS), rng.choice(("allow", "deny"))) for _ in range(rng.randint(0, 8))]


def random_scope(rng: random.Random) -> tuple[str, ...]:
	return tuple(rng.sample(PATTERNS, rng.randint(1, 4)))


def cases(n: int = 1500):
	rng = random.Random(20261103)
	for _ in range(n):
		yield rng, random_rules(rng), random_scope(rng)


def test_property_scope_never_widens():
	for _, rules, scope in cases():
		plain, scoped = build_access(rules, CALLER), build_access(rules, CALLER, scope)
		for name in NAMES:
			if scoped.check(name).allowed:
				assert plain.check(name).allowed, (rules, scope, name)


def test_property_a_larger_scope_never_allows_less_and_never_exceeds_the_grants():
	for rng, rules, scope in cases():
		bigger = scope + random_scope(rng)
		small, big, plain = (build_access(rules, CALLER, s) for s in (scope, bigger, None))
		for name in NAMES:
			if small.check(name).allowed:
				assert big.check(name).allowed
			if big.check(name).allowed:
				assert plain.check(name).allowed


def test_property_deny_always_wins():
	for _, rules, scope in cases():
		denies = [r.tool_pattern for r in rules if r.effect == "deny" and (r.subject_type, r.subject_id) in CALLER.subjects()]
		for access in (build_access(rules, CALLER), build_access(rules, CALLER, scope)):
			for name in NAMES:
				if any(ToolAccess(deny=(p,)).check(name).allowed is False for p in denies):
					assert not access.check(name).allowed, (rules, name)


def test_property_adding_a_deny_never_allows_more():
	for rng, rules, scope in cases():
		extra = rule(*rng.choice(SUBJECTS), rng.choice(PATTERNS), "deny")
		before, after = build_access(rules, CALLER, scope), build_access([*rules, extra], CALLER, scope)
		for name in NAMES:
			if after.check(name).allowed:
				assert before.check(name).allowed


def test_property_other_subjects_grants_are_irrelevant():
	for rng, rules, scope in cases():
		stranger = [rule(rng.choice(("user", "team", "api_key")), str(uuid.uuid4()), rng.choice(PATTERNS), rng.choice(("allow", "deny")))
		            for _ in range(5)]
		a, b = build_access(rules, CALLER, scope), build_access([*rules, *stranger], CALLER, scope)
		assert all(a.check(n) == b.check(n) for n in NAMES)
