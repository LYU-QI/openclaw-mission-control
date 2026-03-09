from app.schemas.organizations import OrganizationInviteCreate


def test_organization_invite_create_normalizes_email_and_role() -> None:
    payload = OrganizationInviteCreate(
        invited_email="  Foo@Example.com  ",
        role="  ADMIN  ",
    )

    assert payload.invited_email == "foo@example.com"
    assert payload.role == "admin"


def test_organization_invite_create_defaults_blank_role_to_member() -> None:
    payload = OrganizationInviteCreate(
        invited_email="user@example.com",
        role="   ",
    )

    assert payload.role == "member"
