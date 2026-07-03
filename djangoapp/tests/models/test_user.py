from django.test import TestCase

from djangoapp.models import User, UserHistory, UserSnapshot


class UserModelTests(TestCase):
    """Custom User model behaviour.

    Verifies public_id auto-generation, the has_public_profile default, the
    display_name property, and the trigram-backed search_users ranking (best
    match first, pg_trgm).

    - test_public_id_auto_generated_on_create_user, create_user sets a uuid7 public_id
    - test_public_id_unique_across_users, two users get distinct public_ids
    - test_public_id_format_is_uuid, public_id is a 36-char hyphenated string
    - test_has_public_profile_defaults_false, new user has has_public_profile False
    - test_display_name_combines_first_and_last_name, full name wins over username
    - test_display_name_strips_whitespace_when_partial, a lone first_name has no trailing space
    - test_display_name_falls_back_to_username, missing names fall back to username
    - test_search_users_ranks_by_best_match, best trigram match ranks first
    - test_search_users_empty_returns_all, empty query returns all users ordered by username
    - test_search_users_no_match_returns_empty, unrelated query returns no users
    """

    def test_public_id_auto_generated_on_create_user(self) -> None:
        """create_user sets a uuid7 public_id."""
        user = User.objects.create_user(username="alpha", password="pass")
        self.assertTrue(user.public_id)

    def test_public_id_unique_across_users(self) -> None:
        """Two users get distinct public_ids."""
        u1 = User.objects.create_user(username="alpha", password="pass")
        u2 = User.objects.create_user(username="beta", password="pass")
        self.assertNotEqual(u1.public_id, u2.public_id)

    def test_public_id_format_is_uuid(self) -> None:
        """public_id is a 36-char hyphenated uuid string."""
        user = User.objects.create_user(username="alpha", password="pass")
        self.assertEqual(len(user.public_id), 36)
        self.assertEqual(user.public_id.count("-"), 4)

    def test_has_public_profile_defaults_false(self) -> None:
        """A freshly created user has has_public_profile False."""
        user = User.objects.create_user(username="alpha", password="pass")
        self.assertFalse(user.has_public_profile)

    def test_display_name_combines_first_and_last_name(self) -> None:
        """Both names present returns First Last, ignoring the username."""
        user = User.objects.create_user(
            username="alpha", password="pass", first_name="Alpha", last_name="Beta"
        )
        self.assertEqual(user.display_name, "Alpha Beta")

    def test_display_name_strips_whitespace_when_partial(self) -> None:
        """Only first_name set returns it with no trailing space."""
        user = User.objects.create_user(
            username="alpha", password="pass", first_name="Alpha", last_name=""
        )
        self.assertEqual(user.display_name, "Alpha")

    def test_display_name_falls_back_to_username(self) -> None:
        """Empty first/last names fall back to the username."""
        user = User.objects.create_user(username="alpha", password="pass")
        self.assertEqual(user.display_name, "alpha")

    def test_search_users_ranks_by_best_match(self) -> None:
        """Best trigram match ranks first across username/name fields."""
        User.objects.create_user(username="alice", password="pass")
        User.objects.create_user(username="alicia", password="pass")
        result = list(User.search_users("alice").values_list("username", flat=True))
        self.assertEqual(result[0], "alice")
        self.assertIn("alicia", result)
        self.assertLess(result.index("alice"), result.index("alicia"))

    def test_search_users_empty_returns_all(self) -> None:
        """Empty query returns all users ordered by username."""
        User.objects.create_user(username="zoe", password="pass")
        User.objects.create_user(username="amy", password="pass")
        result = list(User.search_users("").values_list("username", flat=True))
        self.assertEqual(result, ["amy", "zoe"])

    def test_search_users_no_match_returns_empty(self) -> None:
        """Unrelated query returns an empty queryset."""
        User.objects.create_user(username="alice", password="pass")
        result = list(User.search_users("zzznomatch").values_list("username", flat=True))
        self.assertEqual(result, [])


class UserHistoryModelTests(TestCase):
    """User.update history recording and snapshot diffing.

    Verifies that User.update applies only the 8 editable fields (never
    username/public_id), records exactly one UserHistory "edited" entry, and
    that the snapshot diff omits unchanged fields.

    - test_update_records_edited_history, update writes one edited history row
    - test_update_leaves_username_and_public_id_unchanged, identity fields are immutable
    - test_difference_only_includes_changed_fields, snapshot diff omits unchanged fields
    - test_update_noop_skips_history, a no-op update records no history row
    - test_record_created_snapshots_all_fields, created entry captures every field
    """

    def setUp(self) -> None:
        self.actor = User.objects.create_user(username="root", password="pass")
        self.user = User.objects.create_user(
            username="target",
            password="pass",
            first_name="Old",
            last_name="Name",
            email="old@example.com",
            has_public_profile=False,
        )

    def test_update_records_edited_history(self) -> None:
        """Update writes exactly one edited history row attributed to the actor."""
        self.user.update(
            first_name="New",
            last_name=self.user.last_name,
            email=self.user.email,
            description=self.user.description,
            has_public_profile=True,
            is_active=self.user.is_active,
            is_staff=self.user.is_staff,
            is_superuser=self.user.is_superuser,
            user=self.actor,
        )
        entries = UserHistory.objects.filter(target_user=self.user)
        self.assertEqual(entries.count(), 1)
        entry = entries.get()
        self.assertEqual(entry.action, "edited")
        self.assertEqual(entry.user_id, self.actor.pk)
        self.assertEqual(entry._changes["first_name"], {"old": "Old", "new": "New"})

    def test_update_leaves_username_and_public_id_unchanged(self) -> None:
        """Username and public_id are immutable through update."""
        original_public_id = self.user.public_id
        self.user.update(
            first_name="New",
            last_name=self.user.last_name,
            email=self.user.email,
            description=self.user.description,
            has_public_profile=self.user.has_public_profile,
            is_active=self.user.is_active,
            is_staff=self.user.is_staff,
            is_superuser=self.user.is_superuser,
            user=self.actor,
        )
        self.assertEqual(self.user.username, "target")
        self.assertEqual(self.user.public_id, original_public_id)

    def test_difference_only_includes_changed_fields(self) -> None:
        """The edited diff marks unchanged fields as null."""
        self.user.update(
            first_name=self.user.first_name,
            last_name=self.user.last_name,
            email="changed@example.com",
            description=self.user.description,
            has_public_profile=self.user.has_public_profile,
            is_active=self.user.is_active,
            is_staff=self.user.is_staff,
            is_superuser=self.user.is_superuser,
            user=self.actor,
        )
        changes = UserHistory.objects.get(target_user=self.user)._changes
        self.assertEqual(changes["email"], {"old": "old@example.com", "new": "changed@example.com"})
        self.assertIsNone(changes["first_name"])
        self.assertIsNone(changes["last_name"])
        self.assertNotIn("username", changes)

    def test_update_noop_skips_history(self) -> None:
        """A no-op update (all values unchanged) records no history row."""
        self.user.update(
            first_name=self.user.first_name,
            last_name=self.user.last_name,
            email=self.user.email,
            description=self.user.description,
            has_public_profile=self.user.has_public_profile,
            is_active=self.user.is_active,
            is_staff=self.user.is_staff,
            is_superuser=self.user.is_superuser,
            user=self.actor,
        )
        self.assertEqual(UserHistory.objects.filter(target_user=self.user).count(), 0)

    def test_record_created_snapshots_all_fields(self) -> None:
        """record_created captures every editable field as new (old==new)."""
        snapshot = UserSnapshot(
            first_name=self.user.first_name,
            last_name=self.user.last_name,
            email=self.user.email,
            description=self.user.description,
            has_public_profile=self.user.has_public_profile,
            is_active=self.user.is_active,
            is_staff=self.user.is_staff,
            is_superuser=self.user.is_superuser,
        )
        UserHistory.record_created(self.user, self.actor, snapshot)
        entry = UserHistory.objects.get(target_user=self.user, action="created")
        self.assertEqual(entry._changes["has_public_profile"], {"old": False, "new": False})
        self.assertEqual(
            entry._changes["email"], {"old": "old@example.com", "new": "old@example.com"}
        )
