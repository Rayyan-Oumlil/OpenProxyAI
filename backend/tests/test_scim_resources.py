"""SCIM parsing rules with no database: filters, paging, user payloads, PATCH, and the error body."""

from __future__ import annotations

import pytest

from app.services.scim_errors import ERROR_SCHEMA, ScimError
from app.services.scim_resources import (
    PATCH_SCHEMA,
    normalize_email,
    page_window,
    parse_filter,
    parse_patch,
    parse_user_payload,
)
from app.services.scim_tokens import TOKEN_PREFIX, hash_token, new_token


def patch(*operations: dict) -> dict:
    return {"schemas": [PATCH_SCHEMA], "Operations": list(operations)}


def fails(callable_, scim_type: str, status: int = 400) -> ScimError:
    with pytest.raises(ScimError) as caught:
        callable_()
    assert caught.value.status == status and caught.value.scim_type == scim_type, caught.value.body()
    return caught.value


def test_error_body_has_the_scim_shape():
    body = ScimError(409, "taken", "uniqueness").body()
    assert body == {"schemas": [ERROR_SCHEMA], "status": "409", "detail": "taken", "scimType": "uniqueness"}


def test_tokens_are_long_random_prefixed_and_hashed_to_64_hex():
    first, second = new_token(), new_token()
    assert first.startswith(TOKEN_PREFIX) and first != second and len(first) >= 40
    assert len(hash_token(first)) == 64 and hash_token(first) != hash_token(second)


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, None),
        ("", None),
        ('userName eq "a@b.co"', ("userName", "a@b.co")),
        ('USERNAME EQ "A@B.CO"', ("userName", "A@B.CO")),
        ('externalId eq "x-1"', ("externalId", "x-1")),
        ('userName eq "say \\"hi\\""', ("userName", 'say "hi"')),
    ],
)
def test_filter_accepts_the_one_supported_shape(raw, expected):
    assert parse_filter(raw) == expected


@pytest.mark.parametrize("raw", ['userName co "a"', 'userName eq a', 'active eq true', 'userName eq "a" and active eq true', "emails.value eq 'x'"])
def test_filter_refuses_everything_else_instead_of_guessing(raw):
    fails(lambda: parse_filter(raw), "invalidFilter")


def test_paging_is_one_based_capped_and_validated():
    assert page_window(None, None) == (0, 100)
    assert page_window("1", "5") == (0, 5)
    assert page_window("0", "5") == (0, 5)  # below 1 means 1
    assert page_window("-4", "5") == (0, 5)
    assert page_window("11", "999999") == (10, 200)
    assert page_window("1", "0") == (0, 0)
    fails(lambda: page_window("x", "1"), "invalidValue")


def test_user_payload_lowercases_the_email_and_joins_names():
    changes = parse_user_payload(
        {"userName": " Ada@Example.COM ", "name": {"givenName": "Ada", "familyName": "Lovelace"}, "externalId": "ext-1", "active": True},
        creating=True,
    )
    assert changes.fields == {"email": "ada@example.com", "external_id": "ext-1", "name": "Ada Lovelace", "active": True}


def test_creating_defaults_active_but_a_put_without_active_leaves_it_alone():
    assert parse_user_payload({"userName": "a@b.co"}, creating=True).fields["active"] is True
    assert "active" not in parse_user_payload({"userName": "a@b.co"}, creating=False).fields


@pytest.mark.parametrize("payload", [{}, {"userName": ""}, {"userName": "not-an-email"}, {"userName": 5}, "text", []])
def test_user_payload_needs_a_real_email(payload):
    with pytest.raises(ScimError) as caught:
        parse_user_payload(payload, creating=True)
    assert caught.value.status == 400


def test_roles_can_never_be_provisioned():
    for payload in (
        {"userName": "a@b.co", "roles": [{"value": "admin"}]},
        {"userName": "a@b.co", "entitlements": [{"value": "admin"}]},
        {"userName": "a@b.co", "groups": [{"value": "g"}]},
    ):
        fails(lambda payload=payload: parse_user_payload(payload, creating=True), "invalidValue")
    assert parse_user_payload({"userName": "a@b.co", "roles": []}, creating=True).fields["email"] == "a@b.co"  # empty is not a grant


def test_overlong_values_are_refused():
    fails(lambda: parse_user_payload({"userName": "a@b.co", "externalId": "x" * 256}, creating=True), "invalidValue")


def test_normalize_email_rejects_garbage():
    assert normalize_email("A@B.co") == "a@b.co"
    with pytest.raises(ScimError):
        normalize_email("a b@c")


def test_patch_okta_style_no_path_object():
    assert parse_patch(patch({"op": "replace", "value": {"active": False}})).fields == {"active": False}


def test_patch_entra_style_path_and_string_booleans():
    changes = parse_patch(
        patch(
            {"op": "Replace", "path": "active", "value": "False"},
            {"op": "Replace", "path": "name.givenName", "value": "Ada"},
            {"op": "Add", "path": "externalId", "value": "e-9"},
        )
    )
    assert changes.fields == {"active": False, "name": "Ada", "external_id": "e-9"}


def test_patch_remove_clears_optional_attributes_but_not_required_ones():
    assert parse_patch(patch({"op": "remove", "path": "externalId"})).fields == {"external_id": None}
    assert parse_patch(patch({"op": "remove", "path": "displayName"})).fields == {"name": None}
    fails(lambda: parse_patch(patch({"op": "remove", "path": "active"})), "mutability")
    fails(lambda: parse_patch(patch({"op": "remove", "path": "userName"})), "mutability")
    fails(lambda: parse_patch(patch({"op": "remove"})), "noTarget")


def test_patch_emails_only_change_is_accepted_and_changes_nothing():
    assert parse_patch(patch({"op": "replace", "path": 'emails[type eq "work"].value', "value": "x@y.co"})).fields == {}


def test_patch_refuses_roles_and_unknown_paths_and_bad_shapes():
    fails(lambda: parse_patch(patch({"op": "replace", "path": "roles", "value": "admin"})), "invalidValue")
    fails(lambda: parse_patch(patch({"op": "add", "value": {"roles": [{"value": "admin"}]}})), "invalidValue")
    fails(lambda: parse_patch(patch({"op": "replace", "path": "manager", "value": "x"})), "invalidPath")
    fails(lambda: parse_patch(patch({"op": "move", "path": "active", "value": True})), "invalidSyntax")
    fails(lambda: parse_patch({"schemas": [PATCH_SCHEMA], "Operations": []}), "invalidSyntax")
    fails(lambda: parse_patch({"Operations": [{"op": "replace", "path": "active", "value": True}]}), "invalidSyntax")
    fails(lambda: parse_patch(patch({"op": "replace", "path": "active", "value": "maybe"})), "invalidValue")
