import boa

NAMES = ["Alice", "Bob", "Charlie"]

def test_measure_gas():
    voting = boa.load("Voter.vy", NAMES)
    profiler = boa.load("GasProfiler.vy")
    
    user1 = boa.env.generate_address()
    user2 = boa.env.generate_address()
    
    voting.give_right_to_vote(user1)
    voting.give_right_to_vote(user2)
    
    # delegate user1 -> user2
    with boa.env.prank(user1):
        # We need to call via profiler, but profiler is msg.sender 
        # So we prank the profiler? Or we deploy a profiler per user
        pass
    
    # Actually, profiler calls delegate. If profiler calls it, profiler is the msg.sender!
    # Voting checks if msg.sender has right to vote.
    # So we give right to vote to the profiler contract.
    voting.give_right_to_vote(profiler.address)
    
    # Profiler delegates to user2
    gas_delegate = profiler.measure_delegate(voting.address, user2)
    
    # We still need another profiler to measure vote, since profiler just delegated and can't vote.
    profiler2 = boa.load("GasProfiler.vy")
    voting.give_right_to_vote(profiler2.address)
    gas_vote = profiler2.measure_vote(voting.address, 1)
    
    # measure winning proposal (view function)
    gas_winning = profiler.measure_winning_proposal(voting.address)
    
    print("\n" + "="*40)
    print(f"Функция | Затраты газа")
    print("-" * 40)
    print(f"delegate          | {gas_delegate}")
    print(f"vote              | {gas_vote}")
    print(f"winning_proposal  | {gas_winning}")
    print("="*40 + "\n")
