import json

from djangoapp.models import User, UserHistory
from djangoapp.tests.query_budget import (
    QueryBudgetInertiaTestCase,
    QueryBudgetTestCase,
)


class UserListViewTests(QueryBudgetInertiaTestCase):
    """/users/list superuser gate.

    The list endpoint exposes all users (with descriptions) only to
    superusers; anonymous and non-superuser requests get 404.

    - test_list_anonymous_404, anonymous request returns 404
    - test_list_non_superuser_404, authenticated non-superuser returns 404
    - test_list_superuser_ok, superuser gets 200 rendering the UserList component
    - test_list_includes_admin_fields, superuser sees email/public/staff/superuser/active per row
    - test_list_pagination, list paginates 25-per-page (orphans 5) across two pages
    - test_list_select_count_does_not_scale_with_row_count, SELECT count flat across rows (no N+1)
    """

    def setUp(self) -> None:
        self.superuser = User.objects.create_user(
            username="root",
            password="pass",
            is_staff=True,
            is_superuser=True,
        )
        self.regular = User.objects.create_user(username="peon", password="pass")
        self.public_user = User.objects.create_user(
            username="pub",
            password="pass",
            first_name="Pub",
            last_name="Lic",
            email="pub@example.com",
            has_public_profile=True,
            is_staff=True,
            description="<p>about me</p>",
        )
        super().setUp()

    def test_list_anonymous_404(self) -> None:
        """Anonymous request returns 404."""
        response = self.client.get("/users/list")
        self.assertEqual(response.status_code, 404)

    def test_list_non_superuser_404(self) -> None:
        """Authenticated non-superuser returns 404."""
        self.client.force_login(self.regular)
        response = self.client.get("/users/list")
        self.assertEqual(response.status_code, 404)

    def test_list_superuser_ok(self) -> None:
        self.allow_more_queries(9)  # frozen baseline incl. auth/session overhead
        "superuser gets 200 rendering the UserList component"
        self.client.force_login(self.superuser)
        self.client.get("/users/list")
        self.assertComponentUsed("UserList")

    def test_list_includes_admin_fields(self) -> None:
        self.allow_more_queries(9)  # frozen baseline incl. auth/session overhead
        "superuser sees email/public/staff/superuser/active in each list row"
        self.client.force_login(self.superuser)
        self.client.get("/users/list")
        users = {u["public_id"]: u for u in self.props()["props"]["users"]}
        pub = users[self.public_user.public_id]
        self.assertEqual(pub["email"], "pub@example.com")
        self.assertTrue(pub["has_public_profile"])
        self.assertTrue(pub["is_staff"])
        self.assertFalse(pub["is_superuser"])
        self.assertTrue(pub["is_active"])
        self.assertNotIn("description", pub)

    def test_list_pagination(self) -> None:
        self.allow_more_queries(14)  # frozen baseline incl. auth/session overhead
        "paginated list reports total_count/total_pages and slices per page (25/5)"
        for i in range(31):
            User.objects.create_user(username=f"user{i:02d}", password="pass")
        self.client.force_login(self.superuser)
        self.client.get("/users/list")
        p1 = self.props()["props"]
        self.assertEqual(p1["pagination"]["total_count"], 34)
        self.assertEqual(p1["pagination"]["total_pages"], 2)
        self.assertEqual(p1["pagination"]["page"], 1)
        self.assertEqual(len(p1["users"]), 25)
        self.client.get("/users/list?page=2")
        p2 = self.props()["props"]
        self.assertEqual(p2["pagination"]["page"], 2)
        self.assertEqual(len(p2["users"]), 9)

    def test_list_select_count_does_not_scale_with_row_count(self) -> None:
        """List SELECT count must not scale with row count (catches per-row N+1)."""
        self.allow_more_queries(45)  # three list requests; an N+1 would exceed this
        self.client.force_login(self.superuser)
        few = self.select_count(lambda: self.client.get("/users/list"))
        for i in range(50):
            User.objects.create_user(username=f"bulk-user-{i:02d}", password="pass")
        # Confirm the many-rows list actually renders (guards against a vacuous pass).
        self.assertEqual(self.client.get("/users/list").status_code, 200)
        many = self.select_count(lambda: self.client.get("/users/list"))
        self.assertEqual(few, many)


class UserSearchViewTests(QueryBudgetTestCase):
    """/users/api/search superuser-only username search.

    Feeds the list page's jump-to-profile multiselect: returns up to 20
    users (public_id, username, title) matching the trigram query, with no
    primary-key leak.

    - test_search_anonymous_404, anonymous request returns 404
    - test_search_non_superuser_404, authenticated non-superuser returns 404
    - test_search_empty_returns_all, empty query returns users ordered by username
    - test_search_by_username, query filters to the matching username
    - test_search_item_shape, each item has public_id/username/title and no id key
    """

    def setUp(self) -> None:
        self.superuser = User.objects.create_user(
            username="root",
            password="pass",
            is_staff=True,
            is_superuser=True,
        )
        self.regular = User.objects.create_user(username="peon", password="pass")
        self.alice = User.objects.create_user(
            username="alice",
            password="pass",
            first_name="Alice",
            last_name="Smith",
        )

    def test_search_anonymous_404(self) -> None:
        """Anonymous request returns 404."""
        response = self.client.get("/users/api/search?q=alice")
        self.assertEqual(response.status_code, 404)

    def test_search_non_superuser_404(self) -> None:
        """Authenticated non-superuser returns 404."""
        self.client.force_login(self.regular)
        response = self.client.get("/users/api/search?q=alice")
        self.assertEqual(response.status_code, 404)

    def test_search_empty_returns_all(self) -> None:
        """Empty query returns all users ordered by username, capped at 20."""
        self.client.force_login(self.superuser)
        response = self.client.get("/users/api/search")
        self.assertEqual(response.status_code, 200)
        usernames = [u["username"] for u in json.loads(response.content)["users"]]
        self.assertIn("alice", usernames)
        self.assertIn("peon", usernames)
        self.assertEqual(usernames, sorted(usernames))

    def test_search_by_username(self) -> None:
        """Query filters to the matching username, excluding non-matches."""
        self.client.force_login(self.superuser)
        response = self.client.get("/users/api/search?q=alice")
        self.assertEqual(response.status_code, 200)
        usernames = [u["username"] for u in json.loads(response.content)["users"]]
        self.assertIn("alice", usernames)
        self.assertNotIn("peon", usernames)

    def test_search_item_shape(self) -> None:
        """Each item exposes public_id/username/title and no pk id key."""
        self.client.force_login(self.superuser)
        response = self.client.get("/users/api/search?q=alice")
        self.assertEqual(response.status_code, 200)
        item = json.loads(response.content)["users"][0]
        self.assertEqual(set(item.keys()), {"public_id", "username", "title"})
        self.assertEqual(item["public_id"], self.alice.public_id)
        self.assertEqual(item["title"], "Alice Smith")


class UserDetailsViewTests(QueryBudgetInertiaTestCase):
    """/users/id/<public_id> public access with description gating.

    Anyone (including anonymous) can view first/last name; description and
    username are shown only when has_public_profile is set, even for the owner.

    - test_details_anonymous_ok, anonymous can view a profile (200)
    - test_details_public_shows_description, public profile includes description and username
    - test_details_private_hides_extras, private profile omits description and username
    - test_details_owner_gated_by_own_flag, owner of a private profile sees no description
    - test_details_shared_is_superuser_true, superuser viewer sets the shared flag True
    - test_details_shared_is_superuser_false, others get the shared flag False
    - test_details_admin_attrs_for_superuser, superuser sees target email/flags + history_count
    - test_details_admin_attrs_hidden_for_anonymous, anonymous viewer gets no real email (None)
    - test_details_missing_404, unknown public_id returns 404
    """

    def setUp(self) -> None:
        self.superuser = User.objects.create_user(
            username="root",
            password="pass",
            is_staff=True,
            is_superuser=True,
        )
        self.public_user = User.objects.create_user(
            username="pub",
            password="pass",
            first_name="Pub",
            last_name="Lic",
            email="pub@example.com",
            has_public_profile=True,
            description="<p>about me</p>",
        )
        self.private_user = User.objects.create_user(
            username="priv",
            password="pass",
            first_name="Pri",
            last_name="Vate",
            has_public_profile=False,
            description="<p>secret</p>",
        )
        super().setUp()

    def test_details_anonymous_ok(self) -> None:
        """Anonymous can view a profile (200)."""
        response = self.client.get(f"/users/id/{self.public_user.public_id}")
        self.assertEqual(response.status_code, 200)

    def test_details_public_shows_description(self) -> None:
        """Public profile includes description and username."""
        self.client.get(f"/users/id/{self.public_user.public_id}")
        props = self.props()["props"]
        self.assertEqual(props["description"], "<p>about me</p>")
        self.assertEqual(props["username"], "pub")
        self.assertEqual(props["first_name"], "Pub")
        self.assertEqual(props["last_name"], "Lic")

    def test_details_private_hides_extras(self) -> None:
        """Private profile omits description and username, keeps first/last name."""
        self.client.get(f"/users/id/{self.private_user.public_id}")
        props = self.props()["props"]
        self.assertIsNone(props["description"])
        self.assertIsNone(props["username"])
        self.assertEqual(props["first_name"], "Pri")
        self.assertEqual(props["last_name"], "Vate")

    def test_details_owner_gated_by_own_flag(self) -> None:
        """Owner of a private profile sees no description (gated by own flag)."""
        self.client.force_login(self.private_user)
        self.client.get(f"/users/id/{self.private_user.public_id}")
        props = self.props()["props"]
        self.assertTrue(props["is_owner"])
        self.assertIsNone(props["description"])
        self.assertIsNone(props["username"])

    def test_details_shared_is_superuser_true(self) -> None:
        self.allow_more_queries(9)  # frozen baseline incl. auth/session overhead
        "superuser viewer sets the shared viewer_is_superuser flag (gates admin UI)"
        self.client.force_login(self.superuser)
        self.client.get(f"/users/id/{self.public_user.public_id}")
        self.assertTrue(self.props()["viewer_is_superuser"])

    def test_details_shared_is_superuser_false(self) -> None:
        """non-superuser/anonymous viewer gets the shared viewer_is_superuser False."""
        self.client.get(f"/users/id/{self.public_user.public_id}")
        self.assertFalse(self.props()["viewer_is_superuser"])

    def test_details_admin_attrs_for_superuser(self) -> None:
        self.allow_more_queries(9)  # frozen baseline incl. auth/session overhead
        "superuser sees the target's admin attributes and history count"
        self.public_user.update(
            first_name=self.public_user.first_name,
            last_name=self.public_user.last_name,
            email=self.public_user.email,
            description=self.public_user.description,
            has_public_profile=self.public_user.has_public_profile,
            is_active=self.public_user.is_active,
            is_staff=True,
            is_superuser=self.public_user.is_superuser,
            user=self.superuser,
        )
        self.client.force_login(self.superuser)
        self.client.get(f"/users/id/{self.public_user.public_id}")
        props = self.props()["props"]
        self.assertEqual(props["email"], "pub@example.com")
        self.assertTrue(props["has_public_profile"])
        self.assertTrue(props["is_active"])
        self.assertEqual(props["history_count"], 1)

    def test_details_admin_attrs_hidden_for_anonymous(self) -> None:
        """Anonymous viewer gets no real email (None) and history_count 0."""
        self.client.get(f"/users/id/{self.public_user.public_id}")
        props = self.props()["props"]
        self.assertIsNone(props["email"])
        # Admin gating now comes from the shared flag, not a page prop.
        self.assertFalse(self.props()["viewer_is_superuser"])
        self.assertEqual(props["history_count"], 0)

    def test_details_missing_404(self) -> None:
        """Unknown public_id returns 404."""
        response = self.client.get("/users/id/does-not-exist")
        self.assertEqual(response.status_code, 404)


class UserEditViewTests(QueryBudgetInertiaTestCase):
    """/users/edit/<public_id> superuser-only edit form + submit.

    Only superusers can open the edit form or POST changes; others get 404.
    Edits update the 8 editable fields, leave username untouched, sanitize the
    rich-text description, and record a UserHistory "edited" entry.

    - test_edit_anonymous_404, anonymous GET on the edit form returns 404
    - test_edit_non_superuser_404, non-superuser GET on the edit form returns 404
    - test_edit_superuser_ok, superuser GET renders the UserEdit form with target fields
    - test_edit_missing_404, unknown public_id returns 404
    - test_edit_submit_updates_fields, POST updates editable fields and returns the public id
    - test_edit_submit_cannot_change_username, POST has no username field; username is unchanged
    - test_edit_submit_sanitizes_description, a <script> in description is stripped on save
    - test_edit_submit_records_history, POST creates a UserHistory edited entry for the change
    - test_edit_submit_blocks_self_demotion, POST clearing own superuser/active returns 400
    - test_edit_submit_rejects_invalid_email, malformed email returns 422, target unchanged
    """

    def setUp(self) -> None:
        self.superuser = User.objects.create_user(
            username="root",
            password="pass",
            is_staff=True,
            is_superuser=True,
        )
        self.regular = User.objects.create_user(username="peon", password="pass")
        self.target = User.objects.create_user(
            username="target",
            password="pass",
            first_name="Old",
            last_name="Name",
            email="old@example.com",
            description="<p>old</p>",
            has_public_profile=False,
        )
        super().setUp()

    def _payload(self) -> dict[str, object]:
        return {
            "first_name": "New",
            "last_name": "Handle",
            "email": "new@example.com",
            "description": "<p>new</p>",
            "has_public_profile": True,
            "is_active": True,
            "is_staff": True,
            "is_superuser": False,
        }

    def _submit(self, payload: dict[str, object]) -> None:
        # ninja parses the pydantic UserUpdateSchema from a JSON body.
        self.client.post(
            f"/users/edit/{self.target.public_id}",
            data=payload,
            content_type="application/json",
        )

    def test_edit_anonymous_404(self) -> None:
        """Anonymous GET on the edit form returns 404."""
        response = self.client.get(f"/users/edit/{self.target.public_id}")
        self.assertEqual(response.status_code, 404)

    def test_edit_non_superuser_404(self) -> None:
        """non-superuser GET on the edit form returns 404."""
        self.client.force_login(self.regular)
        response = self.client.get(f"/users/edit/{self.target.public_id}")
        self.assertEqual(response.status_code, 404)

    def test_edit_superuser_ok(self) -> None:
        """Superuser GET renders the UserEdit form with the target's editable fields."""
        self.client.force_login(self.superuser)
        self.client.get(f"/users/edit/{self.target.public_id}")
        self.assertComponentUsed("UserEdit")
        target = self.props()["props"]["target"]
        self.assertEqual(target["username"], "target")
        self.assertEqual(target["first_name"], "Old")
        self.assertFalse(target["has_public_profile"])

    def test_edit_missing_404(self) -> None:
        """Unknown public_id returns 404."""
        self.client.force_login(self.superuser)
        response = self.client.get("/users/edit/does-not-exist")
        self.assertEqual(response.status_code, 404)

    def test_edit_submit_updates_fields(self) -> None:
        self.allow_more_queries(9)  # frozen baseline incl. auth/session overhead
        "POST updates editable fields and returns the target public id"
        self.client.force_login(self.superuser)
        response = self.client.post(
            f"/users/edit/{self.target.public_id}",
            data=self._payload(),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.target.public_id)
        self.target.refresh_from_db()
        self.assertEqual(self.target.first_name, "New")
        self.assertEqual(self.target.email, "new@example.com")
        self.assertTrue(self.target.has_public_profile)
        self.assertTrue(self.target.is_staff)

    def test_edit_submit_cannot_change_username(self) -> None:
        self.allow_more_queries(9)  # frozen baseline incl. auth/session overhead
        "POST has no username field; the target username is unchanged"
        self.client.force_login(self.superuser)
        payload = self._payload()
        payload["username"] = "hijacked"
        self._submit(payload)
        self.target.refresh_from_db()
        self.assertEqual(self.target.username, "target")

    def test_edit_submit_sanitizes_description(self) -> None:
        self.allow_more_queries(9)  # frozen baseline incl. auth/session overhead
        "a <script> tag in the description is stripped on save (nh3 whitelist)"
        self.client.force_login(self.superuser)
        payload = self._payload()
        payload["description"] = "<p>ok</p><script>alert(1)</script>"
        self._submit(payload)
        self.target.refresh_from_db()
        self.assertEqual(self.target.description, "<p>ok</p>")

    def test_edit_submit_records_history(self) -> None:
        self.allow_more_queries(10)  # frozen baseline incl. auth/session overhead
        "POST creates a UserHistory edited entry capturing the changed fields"
        self.client.force_login(self.superuser)
        self._submit(self._payload())
        entries = UserHistory.objects.filter(target_user=self.target)
        self.assertEqual(entries.count(), 1)
        entry = entries.get()
        self.assertEqual(entry.action, "edited")
        self.assertEqual(entry.user_id, self.superuser.pk)
        changes = entry._changes
        self.assertEqual(changes["first_name"], {"old": "Old", "new": "New"})
        self.assertNotIn("username", changes)

    def test_edit_submit_blocks_self_demotion(self) -> None:
        self.allow_more_queries(9)  # frozen baseline incl. auth/session overhead
        "POST clearing the viewer's own superuser/active flag returns 400"
        self.client.force_login(self.superuser)
        payload = self._payload()
        payload["is_superuser"] = False
        payload["is_active"] = False
        response = self.client.post(
            f"/users/edit/{self.superuser.public_id}",
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_superuser)
        self.assertTrue(self.superuser.is_active)

    def test_edit_submit_rejects_invalid_email(self) -> None:
        """POST with a malformed email returns 422 and leaves the target unchanged."""
        self.client.force_login(self.superuser)
        payload = self._payload()
        payload["email"] = "not-an-email"
        response = self.client.post(
            f"/users/edit/{self.target.public_id}",
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.target.refresh_from_db()
        self.assertEqual(self.target.email, "old@example.com")


class UserHistoryViewTests(QueryBudgetInertiaTestCase):
    """/users/history/<public_id> superuser-only history timeline.

    Only superusers can view a user's edit history; others get 404. The
    timeline renders UserHistoryEntryItem rows produced by User.update.

    - test_history_anonymous_404, anonymous GET returns 404
    - test_history_non_superuser_404, non-superuser GET returns 404
    - test_history_missing_404, unknown public_id returns 404
    - test_history_superuser_shows_entries, after an edit, the entry appears in props
    """

    def setUp(self) -> None:
        self.superuser = User.objects.create_user(
            username="root",
            password="pass",
            is_staff=True,
            is_superuser=True,
        )
        self.regular = User.objects.create_user(username="peon", password="pass")
        self.target = User.objects.create_user(username="target", password="pass", first_name="Old")
        super().setUp()

    def test_history_anonymous_404(self) -> None:
        """Anonymous GET returns 404."""
        response = self.client.get(f"/users/history/{self.target.public_id}")
        self.assertEqual(response.status_code, 404)

    def test_history_non_superuser_404(self) -> None:
        """non-superuser GET returns 404."""
        self.client.force_login(self.regular)
        response = self.client.get(f"/users/history/{self.target.public_id}")
        self.assertEqual(response.status_code, 404)

    def test_history_missing_404(self) -> None:
        """Unknown public_id returns 404."""
        self.client.force_login(self.superuser)
        response = self.client.get("/users/history/does-not-exist")
        self.assertEqual(response.status_code, 404)

    def test_history_superuser_shows_entries(self) -> None:
        self.allow_more_queries(9)  # frozen baseline incl. auth/session overhead
        "after an edit, the superuser timeline includes the edited entry"
        self.target.update(
            first_name="New",
            last_name=self.target.last_name,
            email=self.target.email,
            description=self.target.description,
            has_public_profile=self.target.has_public_profile,
            is_active=self.target.is_active,
            is_staff=True,
            is_superuser=self.target.is_superuser,
            user=self.superuser,
        )
        self.client.force_login(self.superuser)
        self.client.get(f"/users/history/{self.target.public_id}")
        self.assertComponentUsed("UserHistory")
        props = self.props()["props"]
        self.assertEqual(props["target_public_id"], self.target.public_id)
        entries = props["entries"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["action"], "edited")
        self.assertEqual(entries[0]["changes"]["is_staff"], {"old": False, "new": True})
