# @version ^0.4.3

greeting: public(String[100])

@deploy
def __init__():
    self.greeting = "Hello, Antigravity!"

@external
def set_greeting(_new_greeting: String[100]):
    self.greeting = _new_greeting
    

