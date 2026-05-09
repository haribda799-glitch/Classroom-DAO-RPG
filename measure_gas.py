import boa

NAMES = ["Alice", "Bob", "Charlie", "Dave"]
voting = boa.load("Voter.vy", NAMES)

user1 = boa.env.generate_address("u1")
user2 = boa.env.generate_address("u2")

voting.give_right_to_vote(user1)
voting.give_right_to_vote(user2)

with boa.env.prank(user1):
    voting.delegate(user2)
gas_delegate = boa.env.last_tx.gas_used

with boa.env.prank(user2):
    voting.vote(1)
gas_vote = boa.env.last_tx.gas_used

print(f"DELEGATE_GAS: {gas_delegate}")
print(f"VOTE_GAS: {gas_vote}")

# For view functions, get_gas doesnt always exist or creates a tx.
# Let's try sending a tx
# Wait, we can't send a tx to a view function easily, but let's try calling it and looking at last_tx
# Or we can deploy a wrapper. But let's check what boa provides:
print("WINNING_PROPOSAL_DIR:", dir(voting.winning_proposal))

try:
    # in boa, .get_gas() is sometimes available? No, wait. 
    # Let's check computation gas.
    # Actually, we can just look at `boa.env.execute_code` ?
    pass
except Exception as e:
    pass
