# @version ^0.4.3

stored_number: public(int128)


@deploy
def __init__(_initial_number: int128):
    self.stored_number = _initial_number

@external
def update_number(_new_number: int128):
    self.stored_number = _new_number