"""
V8 Hybrid Guild Tests — titanoboa (boa)

Tests for the Hybrid Guilds module:
  - create_guild
  - distribute_guild_reward        (50/50 model)
  - create_distribution_proposal   (internal DAO + 0G Storage)
  - sign_proposal                  (100% consensus auto-execute)
  - raise_dispute                  (vault freeze)
  - resolve_dispute                (arbitration + 10% penalty)
  - batch_import_legacy_xp         (data migration)
  - get_guild_members              (view)
  - get_guild_vault_balance        (view)
"""
import pytest
import boa


# ── Constants ──────────────────────────────────────────────────────────────────

INITIAL_SUPPLY = 1_000_000 * 10**18
PROPOSAL_NAMES = ["Quest A", "Quest B"]
DUMMY_AI_HASH  = b"\xab" * 32   # 32-byte placeholder for AI proof hash


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def token():
    """Deploy the SGC ERC-20 token. Deployer becomes owner."""
    return boa.load("contracts/Token.vy")


@pytest.fixture
def chairperson(token):
    """Default deployer account — becomes chairperson & wallet."""
    return boa.env.eoa


@pytest.fixture
def dao(token, chairperson):
    """Deploy ClassroomDAO with the token address."""
    return boa.load("ClassroomDAO.vy", PROPOSAL_NAMES, token.address)


@pytest.fixture
def students(token, chairperson):
    """Generate 3 student addresses funded with SGC."""
    addrs = []
    for i in range(3):
        addr = boa.env.generate_address(f"student_{i}")
        token.transfer(addr, 50_000 * 10**18, sender=chairperson)
        addrs.append(addr)
    return addrs


@pytest.fixture
def registered_dao(dao, token, chairperson, students):
    """
    Fully wired fixture:
    - 3 students registered on-chain (sending 0.01 OGI each)
    - All SGC approved for DAO spending
    """
    boa.env.set_balance(chairperson, 10**18)

    nicknames = ["Alpha", "Bravo", "Charlie"]
    for i, s in enumerate(students):
        with boa.env.prank(chairperson):
            dao.registerStudent(s, nicknames[i], "GroupA", value=10**16)
        with boa.env.prank(s):
            token.approve(dao.address, 2**256 - 1)

    with boa.env.prank(chairperson):
        token.approve(dao.address, 2**256 - 1)

    return dao


# ── Helper ─────────────────────────────────────────────────────────────────────

def create_test_guild(dao, chairperson, guild_id, members):
    """Helper to create a guild."""
    with boa.env.prank(chairperson):
        dao.create_guild(guild_id, members)


# ── create_guild ───────────────────────────────────────────────────────────────

class TestCreateGuild:
    def test_happy_path(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        guild = registered_dao.guilds(1)
        assert guild.guild_id == 1
        assert guild.member_count == 3
        assert guild.is_active is True
        assert guild.total_xp == 0

    def test_student_bindings(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        for s in students:
            assert registered_dao.student_to_guild(s) == 1

    def test_get_guild_members_view(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        members = registered_dao.get_guild_members(1)
        assert len(members) == 3
        for s in students:
            assert s in members

    def test_event_emitted(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        logs = registered_dao.get_logs()
        created = [l for l in logs if type(l).__name__ == "GuildCreated"]
        assert len(created) == 1
        assert created[0].guild_id == 1
        assert created[0].member_count == 3

    def test_reverts_guild_id_zero(self, registered_dao, chairperson, students):
        with boa.reverts("Guild ID must be greater than 0"):
            with boa.env.prank(chairperson):
                registered_dao.create_guild(0, students)

    def test_reverts_non_chairperson(self, registered_dao, students):
        with boa.reverts("Only Game Master can create guilds"):
            with boa.env.prank(students[0]):
                registered_dao.create_guild(1, students)

    def test_reverts_duplicate_guild_id(self, registered_dao, chairperson, students, token):
        create_test_guild(registered_dao, chairperson, 1, students)

        # Create new students for second guild
        new_students = []
        for i in range(2):
            addr = boa.env.generate_address(f"new_student_{i}")
            token.transfer(addr, 10_000 * 10**18, sender=chairperson)
            boa.env.set_balance(chairperson, 10**18)
            with boa.env.prank(chairperson):
                registered_dao.registerStudent(addr, f"New{i}", "GroupB", value=10**16)
            with boa.env.prank(addr):
                token.approve(registered_dao.address, 2**256 - 1)
            new_students.append(addr)

        with boa.reverts("Guild with this ID already exists"):
            with boa.env.prank(chairperson):
                registered_dao.create_guild(1, new_students)

    def test_reverts_unregistered_member(self, registered_dao, chairperson):
        stranger = boa.env.generate_address("stranger")
        with boa.reverts("Member is not a registered student"):
            with boa.env.prank(chairperson):
                registered_dao.create_guild(1, [stranger])

    def test_reverts_student_already_in_guild(self, registered_dao, chairperson, students, token):
        create_test_guild(registered_dao, chairperson, 1, [students[0]])

        with boa.reverts("Student already assigned to a guild"):
            with boa.env.prank(chairperson):
                registered_dao.create_guild(2, [students[0], students[1]])

    def test_reverts_empty_members(self, registered_dao, chairperson):
        with boa.reverts("Guild must have 1 to 5 members"):
            with boa.env.prank(chairperson):
                registered_dao.create_guild(1, [])

    def test_single_member_guild(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, [students[0]])
        guild = registered_dao.guilds(1)
        assert guild.member_count == 1
        assert guild.is_active is True


# ── distribute_guild_reward ────────────────────────────────────────────────────

class TestDistributeGuildReward:
    def test_50_50_split(self, registered_dao, chairperson, students, token):
        create_test_guild(registered_dao, chairperson, 1, students)

        balances_before = [token.balanceOf(s) for s in students]

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 300, 90)

        # Base share = 300 // 2 = 150, per member = 150 // 3 = 50 SGC
        for i, s in enumerate(students):
            diff = token.balanceOf(s) - balances_before[i]
            assert diff == 50 * 10**18

        # Premium = 300 - 150 = 150
        assert registered_dao.guild_vaults(1) == 150

    def test_xp_distribution(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 300, 90)

        # per_member_xp = 90 // 3 = 30
        for s in students:
            assert registered_dao.students(s).academicXP == 30

        # Guild total XP
        assert registered_dao.guilds(1).total_xp == 90

    def test_odd_total_sgc(self, registered_dao, chairperson, students, token):
        """Odd total_sgc: base=150, premium=151. Per member=50 SGC."""
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 301, 0)

        # base_share = 301 // 2 = 150, premium = 301 - 150 = 151
        assert registered_dao.guild_vaults(1) == 151

    def test_vault_accumulates(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)
            registered_dao.distribute_guild_reward(1, 100, 0)

        # First: premium = 200 - 100 = 100. Second: premium = 100 - 50 = 50.
        assert registered_dao.guild_vaults(1) == 150

    def test_event_emitted(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 300, 90)

        logs = registered_dao.get_logs()
        dist = [l for l in logs if type(l).__name__ == "GuildRewardDistributed"]
        assert len(dist) == 1
        assert dist[0].guild_id == 1
        assert dist[0].total_sgc == 300
        assert dist[0].total_xp == 90

    def test_reverts_non_chairperson(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.reverts("Only Game Master can distribute rewards"):
            with boa.env.prank(students[0]):
                registered_dao.distribute_guild_reward(1, 100, 10)

    def test_reverts_inactive_guild(self, registered_dao, chairperson):
        with boa.reverts("Guild is not active"):
            with boa.env.prank(chairperson):
                registered_dao.distribute_guild_reward(99, 100, 10)

    def test_reverts_zero_reward(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.reverts("Reward must be non-zero"):
            with boa.env.prank(chairperson):
                registered_dao.distribute_guild_reward(1, 0, 0)

    def test_view_vault_balance(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        assert registered_dao.get_guild_vault_balance(1) == 100


# ── create_distribution_proposal ──────────────────────────────────────────────

class TestCreateProposal:
    def test_happy_path(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        vault = registered_dao.guild_vaults(1)  # 100

        # Student creates proposal to split vault
        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, [40, 30, 30], DUMMY_AI_HASH
            )

        proposal = registered_dao.guild_proposals(0)
        assert proposal.proposal_id == 0
        assert proposal.guild_id == 1
        assert proposal.ai_proof_hash == DUMMY_AI_HASH
        assert proposal.approvals_count == 0
        assert proposal.is_disputed is False
        assert proposal.is_executed is False
        assert registered_dao.next_proposal_id() == 1

    def test_event_emitted(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        vault = registered_dao.guild_vaults(1)

        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, [40, 30, 30], DUMMY_AI_HASH
            )

        logs = registered_dao.get_logs()
        created = [l for l in logs if type(l).__name__ == "GuildProposalCreated"]
        assert len(created) == 1
        assert created[0].proposal_id == 0
        assert created[0].guild_id == 1
        assert created[0].ai_proof_hash == DUMMY_AI_HASH

    def test_reverts_non_member(self, registered_dao, chairperson, students, token):
        create_test_guild(registered_dao, chairperson, 1, students[:2])

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        vault = registered_dao.guild_vaults(1)

        with boa.reverts("Not a member of this guild"):
            with boa.env.prank(students[2]):
                registered_dao.create_distribution_proposal(
                    1, students[:2], [vault // 2, vault - vault // 2], DUMMY_AI_HASH
                )

    def test_reverts_amounts_mismatch(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        # Amounts don't sum to vault balance
        with boa.reverts("Amounts must equal vault balance"):
            with boa.env.prank(students[0]):
                registered_dao.create_distribution_proposal(
                    1, students, [10, 10, 10], DUMMY_AI_HASH
                )

    def test_reverts_locked_vault(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        vault = registered_dao.guild_vaults(1)

        # Create and dispute a proposal to lock vault
        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, [40, 30, 30], DUMMY_AI_HASH
            )
            registered_dao.raise_dispute(0)

        # Now vault is locked
        with boa.reverts("Guild vault is locked (dispute in progress)"):
            with boa.env.prank(students[1]):
                registered_dao.create_distribution_proposal(
                    1, students, [40, 30, 30], DUMMY_AI_HASH
                )

    def test_reverts_length_mismatch(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        with boa.reverts("Targets and amounts length mismatch"):
            with boa.env.prank(students[0]):
                registered_dao.create_distribution_proposal(
                    1, students, [50, 50], DUMMY_AI_HASH
                )


# ── sign_proposal + auto-execute ──────────────────────────────────────────────

class TestSignProposal:
    def test_single_signature(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        vault = registered_dao.guild_vaults(1)

        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, [40, 30, 30], DUMMY_AI_HASH
            )
            registered_dao.sign_proposal(0)

        assert registered_dao.guild_proposals(0).approvals_count == 1
        assert registered_dao.proposal_signatures(0, students[0]) is True
        assert registered_dao.guild_proposals(0).is_executed is False

    def test_auto_execute_on_full_consensus(self, registered_dao, chairperson, students, token):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        vault = registered_dao.guild_vaults(1)  # 100
        amounts = [40, 30, 30]

        balances_before = [token.balanceOf(s) for s in students]

        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, amounts, DUMMY_AI_HASH
            )

        # Sign with all 3 members
        for s in students:
            with boa.env.prank(s):
                registered_dao.sign_proposal(0)

        # Proposal should be executed
        assert registered_dao.guild_proposals(0).is_executed is True
        assert registered_dao.guild_vaults(1) == 0

        # Verify token distributions
        for i, s in enumerate(students):
            diff = token.balanceOf(s) - balances_before[i]
            assert diff == amounts[i] * 10**18

    def test_event_signed_and_executed(self, registered_dao, chairperson, students, token):
        """
        Note: titanoboa's get_logs() returns logs from the LAST transaction only.
        The final sign_proposal (3rd signer) triggers both GuildProposalSigned
        and GuildProposalExecuted in a single tx, so we verify those two events.
        """
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, [40, 30, 30], DUMMY_AI_HASH
            )

        for s in students:
            with boa.env.prank(s):
                registered_dao.sign_proposal(0)

        # get_logs() captures only the last tx (3rd signer → auto-execute)
        logs = registered_dao.get_logs()
        signed = [l for l in logs if type(l).__name__ == "GuildProposalSigned"]
        assert len(signed) == 1
        assert signed[0].approvals_count == 3  # Final signature

        executed = [l for l in logs if type(l).__name__ == "GuildProposalExecuted"]
        assert len(executed) == 1
        assert executed[0].proposal_id == 0

    def test_reverts_double_sign(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, [40, 30, 30], DUMMY_AI_HASH
            )
            registered_dao.sign_proposal(0)

        with boa.reverts("Already signed this proposal"):
            with boa.env.prank(students[0]):
                registered_dao.sign_proposal(0)

    def test_reverts_non_member(self, registered_dao, chairperson, students, token):
        create_test_guild(registered_dao, chairperson, 1, students[:2])

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        vault = registered_dao.guild_vaults(1)

        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students[:2], [vault // 2, vault - vault // 2], DUMMY_AI_HASH
            )

        with boa.reverts("Not a member of this guild"):
            with boa.env.prank(students[2]):
                registered_dao.sign_proposal(0)

    def test_reverts_nonexistent_proposal(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.reverts("Proposal does not exist"):
            with boa.env.prank(students[0]):
                registered_dao.sign_proposal(999)


# ── raise_dispute ─────────────────────────────────────────────────────────────

class TestRaiseDispute:
    def test_happy_path(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, [40, 30, 30], DUMMY_AI_HASH
            )

        with boa.env.prank(students[1]):
            registered_dao.raise_dispute(0)

        assert registered_dao.guild_proposals(0).is_disputed is True
        assert registered_dao.guild_locked(1) is True

    def test_event_emitted(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, [40, 30, 30], DUMMY_AI_HASH
            )

        with boa.env.prank(students[2]):
            registered_dao.raise_dispute(0)

        logs = registered_dao.get_logs()
        disputes = [l for l in logs if type(l).__name__ == "GuildDisputeRaised"]
        assert len(disputes) == 1
        assert disputes[0].proposal_id == 0
        assert disputes[0].guild_id == 1
        assert disputes[0].disputer == students[2]

    def test_reverts_already_executed(self, registered_dao, chairperson, students, token):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, [40, 30, 30], DUMMY_AI_HASH
            )

        # Execute by consensus
        for s in students:
            with boa.env.prank(s):
                registered_dao.sign_proposal(0)

        with boa.reverts("Proposal already executed"):
            with boa.env.prank(students[0]):
                registered_dao.raise_dispute(0)

    def test_reverts_already_disputed(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, [40, 30, 30], DUMMY_AI_HASH
            )

        with boa.env.prank(students[0]):
            registered_dao.raise_dispute(0)

        with boa.reverts("Proposal already disputed"):
            with boa.env.prank(students[1]):
                registered_dao.raise_dispute(0)

    def test_sign_reverts_after_dispute(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, [40, 30, 30], DUMMY_AI_HASH
            )
            registered_dao.sign_proposal(0)

        with boa.env.prank(students[1]):
            registered_dao.raise_dispute(0)

        with boa.reverts("Proposal is under dispute"):
            with boa.env.prank(students[2]):
                registered_dao.sign_proposal(0)


# ── resolve_dispute ───────────────────────────────────────────────────────────

class TestResolveDispute:
    def test_happy_path_with_10pct_penalty(self, registered_dao, chairperson, students, token):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        vault = registered_dao.guild_vaults(1)  # 100

        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, [40, 30, 30], DUMMY_AI_HASH
            )

        with boa.env.prank(students[1]):
            registered_dao.raise_dispute(0)

        # penalty = 100 // 10 = 10, remaining = 90
        penalty = vault // 10
        remaining = vault - penalty  # 90

        balances_before = [token.balanceOf(s) for s in students]

        with boa.env.prank(chairperson):
            registered_dao.resolve_dispute(0, students, [30, 30, 30])

        # Verify distributions
        for i, s in enumerate(students):
            diff = token.balanceOf(s) - balances_before[i]
            assert diff == 30 * 10**18

        # Vault cleared, lock released
        assert registered_dao.guild_vaults(1) == 0
        assert registered_dao.guild_locked(1) is False
        assert registered_dao.guild_proposals(0).is_executed is True

    def test_event_emitted(self, registered_dao, chairperson, students, token):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, [40, 30, 30], DUMMY_AI_HASH
            )

        with boa.env.prank(students[1]):
            registered_dao.raise_dispute(0)

        with boa.env.prank(chairperson):
            registered_dao.resolve_dispute(0, students, [30, 30, 30])

        logs = registered_dao.get_logs()
        resolved = [l for l in logs if type(l).__name__ == "GuildDisputeResolved"]
        assert len(resolved) == 1
        assert resolved[0].proposal_id == 0
        assert resolved[0].guild_id == 1
        assert resolved[0].penalty_returned == 10

    def test_reverts_non_chairperson(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, [40, 30, 30], DUMMY_AI_HASH
            )
            registered_dao.raise_dispute(0)

        with boa.reverts("Only Game Master can resolve disputes"):
            with boa.env.prank(students[0]):
                registered_dao.resolve_dispute(0, students, [30, 30, 30])

    def test_reverts_not_disputed(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, [40, 30, 30], DUMMY_AI_HASH
            )

        with boa.reverts("Proposal is not under dispute"):
            with boa.env.prank(chairperson):
                registered_dao.resolve_dispute(0, students, [30, 30, 30])

    def test_reverts_wrong_final_amounts(self, registered_dao, chairperson, students):
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, [40, 30, 30], DUMMY_AI_HASH
            )
            registered_dao.raise_dispute(0)

        # 90% of 100 = 90, but we send 100 (wrong)
        with boa.reverts("Final amounts must equal 90 pct of vault after penalty"):
            with boa.env.prank(chairperson):
                registered_dao.resolve_dispute(0, students, [40, 30, 30])

    def test_can_create_proposal_after_resolution(self, registered_dao, chairperson, students, token):
        """After dispute resolved, vault is unlocked and new proposals can be created."""
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 0)

        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, [40, 30, 30], DUMMY_AI_HASH
            )
            registered_dao.raise_dispute(0)

        with boa.env.prank(chairperson):
            registered_dao.resolve_dispute(0, students, [30, 30, 30])

        # Add more rewards to vault
        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 100, 0)

        vault = registered_dao.guild_vaults(1)

        # Should succeed — vault is unlocked
        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, [vault // 3, vault // 3, vault - 2 * (vault // 3)], DUMMY_AI_HASH
            )

        assert registered_dao.guild_proposals(1).guild_id == 1


# ── batch_import_legacy_xp ────────────────────────────────────────────────────

class TestBatchImportLegacyXP:
    def test_happy_path(self, registered_dao, chairperson, students):
        xp_values = [100, 200, 300]

        with boa.env.prank(chairperson):
            registered_dao.batch_import_legacy_xp(students, xp_values)

        for i, s in enumerate(students):
            assert registered_dao.students(s).academicXP == xp_values[i]

    def test_additive(self, registered_dao, chairperson, students):
        """Importing XP should add to existing XP, not overwrite."""
        with boa.env.prank(chairperson):
            registered_dao.batch_import_legacy_xp(students, [50, 50, 50])
            registered_dao.batch_import_legacy_xp(students, [25, 25, 25])

        for s in students:
            assert registered_dao.students(s).academicXP == 75

    def test_event_emitted(self, registered_dao, chairperson, students):
        with boa.env.prank(chairperson):
            registered_dao.batch_import_legacy_xp(students, [10, 20, 30])

        logs = registered_dao.get_logs()
        imported = [l for l in logs if type(l).__name__ == "LegacyXPImported"]
        assert len(imported) == 1
        assert imported[0].student_count == 3

    def test_reverts_non_chairperson(self, registered_dao, students):
        with boa.reverts("Only Game Master can import legacy data"):
            with boa.env.prank(students[0]):
                registered_dao.batch_import_legacy_xp(students, [10, 10, 10])

    def test_reverts_length_mismatch(self, registered_dao, chairperson, students):
        with boa.reverts("Arrays length mismatch"):
            with boa.env.prank(chairperson):
                registered_dao.batch_import_legacy_xp(students, [10, 20])


# ── Full lifecycle integration test ───────────────────────────────────────────

class TestFullLifecycle:
    def test_complete_guild_workflow(self, registered_dao, chairperson, students, token):
        """
        End-to-end test: create guild → reward → propose → sign → auto-execute.
        Verifies the complete happy path from start to finish.
        """
        # 1. Create guild
        create_test_guild(registered_dao, chairperson, 1, students)

        # 2. Import legacy XP
        with boa.env.prank(chairperson):
            registered_dao.batch_import_legacy_xp(students, [100, 200, 300])

        # 3. Distribute guild reward (300 SGC, 90 XP)
        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 300, 90)

        # Verify: each member got 50 SGC base + 30 XP personal
        vault_balance = registered_dao.guild_vaults(1)
        assert vault_balance == 150  # premium 50%

        # XP: legacy + guild reward
        assert registered_dao.students(students[0]).academicXP == 130  # 100 + 30
        assert registered_dao.students(students[1]).academicXP == 230  # 200 + 30
        assert registered_dao.students(students[2]).academicXP == 330  # 300 + 30

        # 4. Create proposal to distribute premium (AI-recommended split)
        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, [80, 40, 30], DUMMY_AI_HASH
            )

        # 5. All members sign → auto-execute
        balances_before = [token.balanceOf(s) for s in students]

        for s in students:
            with boa.env.prank(s):
                registered_dao.sign_proposal(0)

        # 6. Verify execution
        assert registered_dao.guild_proposals(0).is_executed is True
        assert registered_dao.guild_vaults(1) == 0

        # Verify token distributions from premium pool
        for i, s in enumerate(students):
            diff = token.balanceOf(s) - balances_before[i]
            expected = [80, 40, 30][i] * 10**18
            assert diff == expected

    def test_dispute_lifecycle(self, registered_dao, chairperson, students, token):
        """
        End-to-end test: create guild → reward → propose → dispute → resolve.
        Verifies arbitration path with 10% penalty confiscation.
        """
        create_test_guild(registered_dao, chairperson, 1, students)

        with boa.env.prank(chairperson):
            registered_dao.distribute_guild_reward(1, 200, 60)

        vault = registered_dao.guild_vaults(1)  # 100

        # Propose split
        with boa.env.prank(students[0]):
            registered_dao.create_distribution_proposal(
                1, students, [50, 30, 20], DUMMY_AI_HASH
            )

        # Student 2 disputes
        with boa.env.prank(students[2]):
            registered_dao.raise_dispute(0)

        assert registered_dao.guild_locked(1) is True

        # Arbitrator resolves: 10% penalty = 10, remaining = 90
        penalty = vault // 10  # 10
        remaining = vault - penalty  # 90

        balances_before = [token.balanceOf(s) for s in students]

        with boa.env.prank(chairperson):
            registered_dao.resolve_dispute(0, students, [30, 30, 30])

        # Verify distributions (30 SGC each)
        for i, s in enumerate(students):
            diff = token.balanceOf(s) - balances_before[i]
            assert diff == 30 * 10**18

        # Vault cleared, unlocked
        assert registered_dao.guild_vaults(1) == 0
        assert registered_dao.guild_locked(1) is False
