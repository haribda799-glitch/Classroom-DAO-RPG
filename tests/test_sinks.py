"""
V7 Token Sink Tests — titanoboa (boa)

Tests for the three new token sink functions:
  - activate_consumable_item (type 1)
  - recycle_item             (type 2)
  - transform_item_to_xp    (type 3)
"""
import pytest
import boa


# ── Constants ──────────────────────────────────────────────────────────────────

INITIAL_SUPPLY = 1_000_000 * 10**18
ITEM_PRICE     = 100          # SGC (without decimals)
ITEM_PRICE_WEI = ITEM_PRICE * 10**18

PROPOSAL_NAMES = ["Quest A", "Quest B"]


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def token():
    """Deploy the SGC ERC-20 token. Deployer becomes owner."""
    return boa.load("contracts/Token.vy")


@pytest.fixture
def chairperson(token):
    """Default account used for deploying — becomes chairperson & wallet."""
    return boa.env.eoa


@pytest.fixture
def student(token, chairperson):
    """A freshly generated student address funded with plenty of SGC."""
    addr = boa.env.generate_address("student")
    # Give the student enough tokens for purchases
    token.transfer(addr, 10_000 * 10**18, sender=chairperson)
    return addr


@pytest.fixture
def dao(token, chairperson):
    """Deploy ClassroomDAO with the token address."""
    return boa.load("ClassroomDAO.vy", PROPOSAL_NAMES, token.address)


@pytest.fixture
def registered_dao(dao, token, chairperson, student):
    """
    Fully wired fixture:
    - Student registered on-chain (sending 0.01 OGI)
    - Student's SGC approved for DAO spending (max allowance)
    - Chairperson's SGC approved for DAO spending (for recycle refunds)
    """
    # Fund chairperson with native ETH so they can send 0.01 OGI in registerStudent
    boa.env.set_balance(chairperson, 10**18)  # 1 ETH plenty for gas + value

    # Register student (requires 0.01 OGI = 10**16 wei)
    with boa.env.prank(chairperson):
        dao.registerStudent(student, "TestHero", "Group1", value=10**16)

    # Student approves DAO to spend SGC
    with boa.env.prank(student):
        token.approve(dao.address, 2**256 - 1)

    # Chairperson approves DAO to pull refunds / rewards from their wallet
    with boa.env.prank(chairperson):
        token.approve(dao.address, 2**256 - 1)

    return dao


# ── Helper ─────────────────────────────────────────────────────────────────────

def add_item(dao, chairperson, item_type, refund_percent=0, xp_bonus=0):
    """Add a market item and return its ID."""
    item_id = dao.marketItemCount()
    with boa.env.prank(chairperson):
        dao.addMarketItem(
            "Test Item",
            ITEM_PRICE,
            item_type,
            refund_percent,
            xp_bonus,
        )
    return item_id


# ── addMarketItem V7 ───────────────────────────────────────────────────────────

class TestAddMarketItem:
    def test_new_fields_stored_correctly(self, registered_dao, chairperson):
        item_id = add_item(registered_dao, chairperson, item_type=2, refund_percent=40)
        item = registered_dao.marketItems(item_id)
        assert item.item_type == 2
        assert item.refund_percent == 40
        assert item.xp_bonus == 0
        assert item.price == ITEM_PRICE
        assert item.isActive is True

    def test_xp_item_fields_stored(self, registered_dao, chairperson):
        item_id = add_item(registered_dao, chairperson, item_type=3, xp_bonus=75)
        item = registered_dao.marketItems(item_id)
        assert item.item_type == 3
        assert item.xp_bonus == 75
        assert item.refund_percent == 0

    def test_invalid_type_reverts(self, registered_dao, chairperson):
        with boa.reverts("Invalid item type"):
            with boa.env.prank(chairperson):
                registered_dao.addMarketItem("Bad", 100, 0, 0, 0)

    def test_refund_over_100_reverts(self, registered_dao, chairperson):
        with boa.reverts("Refund percent must be 0-100"):
            with boa.env.prank(chairperson):
                registered_dao.addMarketItem("Bad", 100, 2, 101, 0)


# ── buyItem V7 ────────────────────────────────────────────────────────────────

class TestBuyItemV7:
    def test_buy_increments_item_count(self, registered_dao, chairperson, student):
        item_id = add_item(registered_dao, chairperson, item_type=1)

        with boa.env.prank(student):
            registered_dao.buyItem(item_id)

        assert registered_dao.student_item_count(student, item_id) == 1

    def test_buy_twice_increments_count(self, registered_dao, chairperson, student):
        item_id = add_item(registered_dao, chairperson, item_type=1)

        with boa.env.prank(student):
            registered_dao.buyItem(item_id)
            registered_dao.buyItem(item_id)

        assert registered_dao.student_item_count(student, item_id) == 2


# ── activate_consumable_item ───────────────────────────────────────────────────

class TestActivateConsumable:
    def test_happy_path(self, registered_dao, chairperson, student, token):
        item_id = add_item(registered_dao, chairperson, item_type=1)

        with boa.env.prank(student):
            registered_dao.buyItem(item_id)
            registered_dao.activate_consumable_item(item_id)

        # Quantity must drop to 0
        assert registered_dao.student_item_count(student, item_id) == 0

    def test_event_emitted(self, registered_dao, chairperson, student):
        item_id = add_item(registered_dao, chairperson, item_type=1)

        with boa.env.prank(student):
            registered_dao.buyItem(item_id)
            registered_dao.activate_consumable_item(item_id)

        logs = registered_dao.get_logs()
        consumed = [l for l in logs if type(l).__name__ == "ConsumableActivated"]
        assert len(consumed) == 1
        assert consumed[0].student == student
        assert consumed[0].item_id == item_id

    def test_reverts_when_not_owned(self, registered_dao, chairperson, student):
        item_id = add_item(registered_dao, chairperson, item_type=1)

        with boa.reverts("You don't own this item"):
            with boa.env.prank(student):
                registered_dao.activate_consumable_item(item_id)

    def test_reverts_after_count_zero(self, registered_dao, chairperson, student):
        item_id = add_item(registered_dao, chairperson, item_type=1)

        with boa.env.prank(student):
            registered_dao.buyItem(item_id)
            registered_dao.activate_consumable_item(item_id)
            # Second activation must revert — count is now 0
            with boa.reverts("You don't own this item"):
                registered_dao.activate_consumable_item(item_id)

    def test_wrong_type_reverts(self, registered_dao, chairperson, student):
        item_id = add_item(registered_dao, chairperson, item_type=2, refund_percent=50)

        with boa.env.prank(student):
            registered_dao.buyItem(item_id)
            with boa.reverts("Item is not a consumable"):
                registered_dao.activate_consumable_item(item_id)

    def test_not_registered_reverts(self, registered_dao, chairperson, token):
        item_id = add_item(registered_dao, chairperson, item_type=1)
        stranger = boa.env.generate_address("stranger")

        with boa.reverts("Not a registered student"):
            with boa.env.prank(stranger):
                registered_dao.activate_consumable_item(item_id)


# ── recycle_item ──────────────────────────────────────────────────────────────

class TestRecycleItem:
    def test_happy_path_refund(self, registered_dao, chairperson, student, token):
        """40% refund on a 100 SGC item => 40 SGC returned."""
        item_id = add_item(registered_dao, chairperson, item_type=2, refund_percent=40)

        balance_before = token.balanceOf(student)

        with boa.env.prank(student):
            registered_dao.buyItem(item_id)
            registered_dao.recycle_item(item_id)

        balance_after = token.balanceOf(student)
        # Net cost = 100 - 40 = 60 SGC
        expected_net_cost = 60 * 10**18
        assert balance_before - balance_after == expected_net_cost

    def test_count_decrements(self, registered_dao, chairperson, student, token):
        item_id = add_item(registered_dao, chairperson, item_type=2, refund_percent=50)

        with boa.env.prank(student):
            registered_dao.buyItem(item_id)
            registered_dao.recycle_item(item_id)

        assert registered_dao.student_item_count(student, item_id) == 0

    def test_event_emitted_with_correct_refund(self, registered_dao, chairperson, student, token):
        item_id = add_item(registered_dao, chairperson, item_type=2, refund_percent=50)

        with boa.env.prank(student):
            registered_dao.buyItem(item_id)
            registered_dao.recycle_item(item_id)

        logs = registered_dao.get_logs()
        recycled = [l for l in logs if type(l).__name__ == "ItemRecycled"]
        assert len(recycled) == 1
        assert recycled[0].student == student
        assert recycled[0].item_id == item_id
        assert recycled[0].sgc_refund == 50 * 10**18  # 50% of 100 SGC

    def test_reverts_when_not_owned(self, registered_dao, chairperson, student):
        item_id = add_item(registered_dao, chairperson, item_type=2, refund_percent=40)

        with boa.reverts("You don't own this item"):
            with boa.env.prank(student):
                registered_dao.recycle_item(item_id)

    def test_wrong_type_reverts(self, registered_dao, chairperson, student):
        item_id = add_item(registered_dao, chairperson, item_type=1)

        with boa.env.prank(student):
            registered_dao.buyItem(item_id)
            with boa.reverts("Item is not recyclable"):
                registered_dao.recycle_item(item_id)

    def test_zero_refund_percent_no_transfer(self, registered_dao, chairperson, student, token):
        """0% refund should not crash, just no tokens returned."""
        item_id = add_item(registered_dao, chairperson, item_type=2, refund_percent=0)

        balance_before = token.balanceOf(student)
        with boa.env.prank(student):
            registered_dao.buyItem(item_id)
            registered_dao.recycle_item(item_id)

        balance_after = token.balanceOf(student)
        # Full 100 SGC spent, 0 returned
        assert balance_before - balance_after == ITEM_PRICE_WEI


# ── transform_item_to_xp ──────────────────────────────────────────────────────

class TestTransformItemToXP:
    def test_happy_path_xp_gain(self, registered_dao, chairperson, student):
        item_id = add_item(registered_dao, chairperson, item_type=3, xp_bonus=50)

        xp_before = registered_dao.students(student).academicXP

        with boa.env.prank(student):
            registered_dao.buyItem(item_id)
            registered_dao.transform_item_to_xp(item_id)

        xp_after = registered_dao.students(student).academicXP
        assert xp_after - xp_before == 50

    def test_count_decrements(self, registered_dao, chairperson, student):
        item_id = add_item(registered_dao, chairperson, item_type=3, xp_bonus=25)

        with boa.env.prank(student):
            registered_dao.buyItem(item_id)
            registered_dao.transform_item_to_xp(item_id)

        assert registered_dao.student_item_count(student, item_id) == 0

    def test_event_emitted_with_correct_xp(self, registered_dao, chairperson, student):
        item_id = add_item(registered_dao, chairperson, item_type=3, xp_bonus=100)

        with boa.env.prank(student):
            registered_dao.buyItem(item_id)
            registered_dao.transform_item_to_xp(item_id)

        logs = registered_dao.get_logs()
        transformed = [l for l in logs if type(l).__name__ == "ItemTransformedToXP"]
        assert len(transformed) == 1
        assert transformed[0].student == student
        assert transformed[0].item_id == item_id
        assert transformed[0].xp_gained == 100

    def test_multiple_transforms_accumulate_xp(self, registered_dao, chairperson, student):
        item_id = add_item(registered_dao, chairperson, item_type=3, xp_bonus=50)

        with boa.env.prank(student):
            registered_dao.buyItem(item_id)
            registered_dao.buyItem(item_id)
            registered_dao.transform_item_to_xp(item_id)
            registered_dao.transform_item_to_xp(item_id)

        xp = registered_dao.students(student).academicXP
        assert xp == 100  # 50 + 50

    def test_reverts_when_not_owned(self, registered_dao, chairperson, student):
        item_id = add_item(registered_dao, chairperson, item_type=3, xp_bonus=50)

        with boa.reverts("You don't own this item"):
            with boa.env.prank(student):
                registered_dao.transform_item_to_xp(item_id)

    def test_wrong_type_reverts(self, registered_dao, chairperson, student):
        item_id = add_item(registered_dao, chairperson, item_type=1)

        with boa.env.prank(student):
            registered_dao.buyItem(item_id)
            with boa.reverts("Item is not an XP transform item"):
                registered_dao.transform_item_to_xp(item_id)

    def test_not_registered_reverts(self, registered_dao, chairperson):
        item_id = add_item(registered_dao, chairperson, item_type=3, xp_bonus=50)
        stranger = boa.env.generate_address("stranger2")

        with boa.reverts("Not a registered student"):
            with boa.env.prank(stranger):
                registered_dao.transform_item_to_xp(item_id)


# ── Cross-type sink security ───────────────────────────────────────────────────

class TestCrossTypeSecurity:
    """Ensure calling the wrong sink on any type fails cleanly."""

    @pytest.mark.parametrize("correct_type,wrong_sink,err", [
        (1, "recycle_item",          "Item is not recyclable"),
        (1, "transform_item_to_xp",  "Item is not an XP transform item"),
        (2, "activate_consumable_item", "Item is not a consumable"),
        (2, "transform_item_to_xp",  "Item is not an XP transform item"),
        (3, "activate_consumable_item", "Item is not a consumable"),
        (3, "recycle_item",          "Item is not recyclable"),
    ])
    def test_cross_type(
        self, registered_dao, chairperson, student, correct_type, wrong_sink, err
    ):
        item_id = add_item(
            registered_dao, chairperson,
            item_type=correct_type,
            refund_percent=50 if correct_type == 2 else 0,
            xp_bonus=50 if correct_type == 3 else 0,
        )

        with boa.env.prank(student):
            registered_dao.buyItem(item_id)
            with boa.reverts(err):
                getattr(registered_dao, wrong_sink)(item_id)
